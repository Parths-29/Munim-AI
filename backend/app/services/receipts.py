"""Atomic posting of a merchant-confirmed stock-inflow proposal.

One SQLite transaction appends the receipt, one stock movement per accepted
line, the supplier payable (invoice total minus explicitly entered paid-now),
and timeline events. Any failure rolls every part back. Wholesale cost is
recorded on the movement only; product rows (and any retail price) are never
updated.
"""

import sqlite3
import uuid
from datetime import datetime

from fastapi import HTTPException

from app.domain.intake import ProposalConfirm, ReceiptLineResult, ReceiptView
from app.services import events as events_service
from app.services import suppliers as suppliers_service
from app.services.database import connect, current_shop
from app.services.inventory import on_hand_quantity
from app.services.proposals import DraftContent, evaluate, load_row, now_utc
from app.services.units import normalize_invoice_number


def confirm_proposal(proposal_id: str, request: ProposalConfirm, kinds: set[str]) -> ReceiptView:
    if not request.confirmed:
        raise HTTPException(status_code=409, detail="Merchant confirmation is required before posting stock or supplier dues.")
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = load_row(connection, proposal_id, kinds)

        existing = connection.execute(
            "SELECT * FROM stock_receipts WHERE proposal_id = ? OR idempotency_key = ? LIMIT 2",
            (proposal_id, request.idempotency_key),
        ).fetchall()
        if existing:
            receipt = existing[0]
            same = (len(existing) == 1 and receipt["proposal_id"] == proposal_id
                    and receipt["idempotency_key"] == request.idempotency_key
                    and receipt["proposal_version"] == request.expected_version
                    and receipt["content_hash"] == request.content_hash
                    and receipt["paid_now_paise"] == _effective_paid_now(receipt["total_paise"], request.paid_now_paise))
            if not same:
                raise HTTPException(status_code=409, detail={
                    "code": "PROPOSAL_ALREADY_CONFIRMED" if receipt["proposal_id"] == proposal_id else "IDEMPOTENCY_KEY_REUSED",
                    "receipt_id": receipt["receipt_id"],
                })
            return receipt_view(connection, receipt, idempotent_replay=True)

        if row["status"] in {"REJECTED", "EXPIRED"}:
            raise HTTPException(status_code=409, detail={"code": f"PROPOSAL_{row['status']}"})
        if datetime.fromisoformat(row["expires_at"]) <= now_utc():
            raise HTTPException(status_code=409, detail={"code": "PROPOSAL_EXPIRED"})
        if row["version"] != request.expected_version or row["content_hash"] != request.content_hash:
            raise HTTPException(status_code=409, detail={
                "code": "STALE_PROPOSAL",
                "message": "The proposal changed after this preview. Reload it and review again before confirming.",
                "current_version": row["version"],
                "current_content_hash": row["content_hash"],
            })

        # Full server-side revalidation; nothing from the client is trusted except the explicit paid-now amount.
        view = evaluate(connection, row)
        blocking = [issue for issue in view.issues + [i for line in view.lines if line.accepted for i in line.issues]
                    if issue.severity == "blocking"]
        if blocking:
            raise HTTPException(status_code=409, detail={
                "code": "PROPOSAL_NOT_READY",
                "issues": [issue.model_dump() for issue in blocking],
            })
        if view.warnings_require_acknowledgement and not request.acknowledge_warnings:
            raise HTTPException(status_code=409, detail={
                "code": "WARNINGS_NOT_ACKNOWLEDGED",
                "message": "Review the warnings (for example total mismatches) and confirm with acknowledge_warnings=true.",
            })

        total = view.invoice.total_paise
        if total is None:
            if request.paid_now_paise not in (None, 0):
                raise HTTPException(status_code=422, detail="paid_now_paise needs a verified invoice total; add the total first.")
            paid_now = None
            amount_due = 0
        else:
            if request.paid_now_paise is None:
                raise HTTPException(status_code=422, detail={
                    "code": "PAID_NOW_REQUIRED",
                    "message": "Enter how much was paid to the supplier now (0 if nothing). It is never inferred from the bill.",
                })
            paid_now = request.paid_now_paise
            if paid_now > total:
                raise HTTPException(status_code=422, detail={"code": "PAID_NOW_EXCEEDS_TOTAL", "total_paise": total})
            amount_due = total - paid_now
        supplier_id = view.supplier.supplier_id
        if amount_due > 0 and supplier_id is None:
            raise HTTPException(status_code=409, detail={
                "code": "SUPPLIER_REQUIRED_FOR_PAYABLE",
                "message": "Select the supplier so the unpaid amount is recorded against them.",
            })

        receipt_id = f"receipt_{uuid.uuid4().hex[:12]}"
        source_event_id = f"receipt:{proposal_id}"
        created = now_utc().isoformat()
        draft = DraftContent.model_validate_json(row["draft_json"])
        source_text = {line.line_id: line.source_text for line in draft.lines}

        due_before = suppliers_service.supplier_due(connection, supplier_id) if supplier_id else None
        payable_entry_id = None
        if amount_due > 0:
            entry, _ = suppliers_service.append_payable_entry(
                connection,
                supplier_id=supplier_id,
                entry_type="INVOICE_CREDIT",
                amount_paise=amount_due,
                source_kind="invoice_receipt",
                source_document_id=receipt_id,
                note=f"Invoice {view.invoice.invoice_number}" if view.invoice.invoice_number else "Stock receipt",
                source_event_id=f"{source_event_id}:payable",
                idempotency_key=f"{request.idempotency_key}:payable",
                source_channel=request.source_channel,
                source_utterance=None,
            )
            payable_entry_id = entry["entry_id"]

        accepted = [line for line in view.lines if line.accepted]
        try:
            connection.execute(
                """INSERT INTO stock_receipts
                   (receipt_id, shop_id, proposal_id, proposal_version, content_hash, source_kind, supplier_id, supplier_label,
                    invoice_number, invoice_number_normalized, invoice_date, total_paise, paid_now_paise, payable_entry_id,
                    supplier_due_before_paise, line_count, source_channel, source_event_id, idempotency_key, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (receipt_id, current_shop(), proposal_id, row["version"], row["content_hash"], row["source_kind"], supplier_id,
                 view.supplier.label, view.invoice.invoice_number, normalize_invoice_number(view.invoice.invoice_number),
                 view.invoice.invoice_date.isoformat() if view.invoice.invoice_date else None, total, paid_now,
                 payable_entry_id, due_before, len(accepted), request.source_channel, source_event_id, request.idempotency_key, created),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail={"code": "DUPLICATE_INVOICE_ALREADY_POSTED"}) from None

        for line in accepted:
            before, _ = on_hand_quantity(connection, line.matched_product_id)
            connection.execute(
                """INSERT INTO stock_receipt_movements
                   (movement_id, shop_id, receipt_id, line_id, product_id, quantity_delta, unit, received_quantity,
                    received_unit, base_units_per_unit, unit_cost_paise, line_total_paise, source_text, on_hand_before,
                    reason, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'STOCK_RECEIPT', 'POSTED', ?)""",
                (f"rmove_{uuid.uuid4().hex[:12]}", current_shop(), receipt_id, line.line_id, line.matched_product_id,
                 line.base_quantity, line.base_unit, line.quantity, line.unit, line.conversion_factor,
                 line.unit_cost_paise, line.line_total_paise, source_text.get(line.line_id), before, created),
            )

        origin = {"invoice_image": "invoice photo", "manual_invoice": "typed invoice",
                  "voice_inward": "voice inward", "text_inward": "typed inward"}[row["source_kind"]]
        payable_text = (f" Supplier payable +{amount_due} paise." if amount_due > 0
                        else " Paid in full now." if total is not None else " No cost supplied; stock only.")
        events_service.append_event(
            connection,
            event_type="STOCK_RECEIPT_POSTED",
            entity_type="STOCK_RECEIPT",
            entity_id=receipt_id,
            source_event_id=source_event_id,
            source_channel=request.source_channel,
            source_utterance=row["source_utterance"],
            status="POSTED",
            summary=f"Stock received from {origin}: {len(accepted)} line(s).{payable_text}",
            idempotency_key=f"{request.idempotency_key}:receipt",
        )
        connection.execute(
            "UPDATE intake_proposals SET status = 'CONFIRMED', posted_receipt_id = ?, updated_at = ? WHERE proposal_id = ?",
            (receipt_id, created, proposal_id),
        )
        receipt = connection.execute("SELECT * FROM stock_receipts WHERE receipt_id = ?", (receipt_id,)).fetchone()
        return receipt_view(connection, receipt)


def _effective_paid_now(total: int | None, paid_now: int | None) -> int | None:
    return None if total is None else paid_now


def receipt_view(connection: sqlite3.Connection, receipt: sqlite3.Row, idempotent_replay: bool = False) -> ReceiptView:
    """Before/after figures are the snapshots recorded at posting time."""
    movements = connection.execute(
        """SELECT m.*, p.name AS product_name FROM stock_receipt_movements m
           JOIN products p ON p.shop_id = m.shop_id AND p.product_id = m.product_id
           WHERE m.receipt_id = ? ORDER BY m.rowid""",
        (receipt["receipt_id"],),
    ).fetchall()
    lines = [ReceiptLineResult(
        movement_id=m["movement_id"], line_id=m["line_id"], product_id=m["product_id"], product_name=m["product_name"],
        received_quantity=m["received_quantity"], received_unit=m["received_unit"], quantity_delta=m["quantity_delta"],
        unit=m["unit"], on_hand_before=m["on_hand_before"], on_hand_after=m["on_hand_before"] + m["quantity_delta"],
    ) for m in movements]
    due_before = receipt["supplier_due_before_paise"]
    due_after = None
    if receipt["payable_entry_id"]:
        payable_status = "POSTED"
        amount = connection.execute(
            "SELECT amount_paise FROM supplier_payable_entries WHERE entry_id = ?", (receipt["payable_entry_id"],)
        ).fetchone()[0]
        due_after = due_before + amount
    elif receipt["total_paise"] is not None:
        payable_status = "FULLY_PAID_NOW"
        due_after = due_before
    else:
        payable_status = "NOT_SUPPLIED"
        due_after = due_before
    return ReceiptView(
        receipt_id=receipt["receipt_id"],
        proposal_id=receipt["proposal_id"],
        proposal_version=receipt["proposal_version"],
        source_kind=receipt["source_kind"],
        supplier_id=receipt["supplier_id"],
        supplier_label=receipt["supplier_label"],
        invoice_number=receipt["invoice_number"],
        total_paise=receipt["total_paise"],
        paid_now_paise=receipt["paid_now_paise"],
        payable_entry_id=receipt["payable_entry_id"],
        payable_status=payable_status,
        supplier_due_before_paise=due_before,
        supplier_due_after_paise=due_after,
        lines=lines,
        created_at=datetime.fromisoformat(receipt["created_at"]),
        idempotent_replay=idempotent_replay,
    )


def get_receipt(receipt_id: str) -> ReceiptView:
    with connect() as connection:
        receipt = connection.execute(
            "SELECT * FROM stock_receipts WHERE shop_id = ? AND receipt_id = ?", (current_shop(), receipt_id)
        ).fetchone()
        if receipt is None:
            raise HTTPException(status_code=404, detail="Receipt not found in this demo shop.")
        return receipt_view(connection, receipt, idempotent_replay=True)
