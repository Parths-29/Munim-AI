"""Mocked payment intake with conservative, auditable ledger allocation."""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from app.domain.models import (
    PaymentAllocationCreate,
    PaymentAllocationView,
    PaymentIntakeCreate,
    PaymentIntakeView,
    PaymentReviewView,
    PayerMappingCreate,
    PayerMappingView,
)
from app.services.database import connect, current_shop
from app.services.events import append_event


def create_payer_mapping(request: PayerMappingCreate) -> PayerMappingView:
    if not request.confirmed:
        raise HTTPException(status_code=409, detail="Merchant confirmation is required before linking a synthetic payer token.")
    now = datetime.now(timezone.utc).isoformat()
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        customer = connection.execute(
            "SELECT customer_id FROM customers WHERE shop_id = ? AND customer_id = ?",
            (current_shop(), request.customer_id),
        ).fetchone()
        if customer is None:
            raise HTTPException(status_code=404, detail="Customer not found in this demo shop.")
        existing = connection.execute(
            "SELECT * FROM payer_customer_mappings WHERE idempotency_key = ? OR (shop_id = ? AND payer_token = ?) LIMIT 2",
            (request.idempotency_key, current_shop(), request.payer_token),
        ).fetchall()
        if len(existing) > 1:
            raise HTTPException(status_code=409, detail="Mapping key and payer token resolve to different records.")
        if existing:
            row = existing[0]
            if row["customer_id"] != request.customer_id or row["payer_token"] != request.payer_token:
                raise HTTPException(status_code=409, detail="Payer token or idempotency key is already mapped differently.")
            return PayerMappingView(mapping_id=row["mapping_id"], customer_id=row["customer_id"], status="MAPPED")

        mapping_id = f"mapping_{uuid.uuid4().hex[:12]}"
        connection.execute(
            "INSERT INTO payer_customer_mappings(mapping_id, shop_id, payer_token, customer_id, idempotency_key, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (mapping_id, current_shop(), request.payer_token, request.customer_id, request.idempotency_key, now),
        )
        append_event(
            connection,
            event_type="PAYER_TOKEN_MAPPED",
            entity_type="CUSTOMER",
            entity_id=request.customer_id,
            source_event_id=request.idempotency_key,
            source_channel="system",
            source_utterance=None,
            status="POSTED",
            summary="A synthetic payer token was linked to a customer after merchant confirmation.",
            idempotency_key=request.idempotency_key,
        )
    return PayerMappingView(mapping_id=mapping_id, customer_id=request.customer_id, status="MAPPED")


def intake_payment(request: PaymentIntakeCreate) -> PaymentIntakeView:
    if request.occurred_at.tzinfo is None or request.occurred_at.utcoffset() is None:
        raise HTTPException(status_code=422, detail="occurred_at must include a timezone offset.")
    now = datetime.now(timezone.utc).isoformat()
    occurred_at = request.occurred_at.astimezone(timezone.utc).isoformat()
    reference = request.payment_reference.strip().upper() if request.payment_reference else None
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            "SELECT * FROM payment_events WHERE idempotency_key = ? OR (shop_id = ? AND event_id = ?) LIMIT 2",
            (request.idempotency_key, current_shop(), request.event_id),
        ).fetchall()
        if len(existing) > 1:
            raise HTTPException(status_code=409, detail="Idempotency key and payment event ID resolve to different records.")
        if existing:
            row = existing[0]
            same_event = (
                row["event_id"] == request.event_id
                and row["amount_paise"] == request.amount_paise
                and row["payment_status"] == request.status
                and row["occurred_at"] == occurred_at
                and row["payer_token"] == request.payer_token
                and row["payment_reference"] == reference
            )
            if not same_event:
                raise HTTPException(status_code=409, detail="Payment event ID or idempotency key was reused with different data.")
            return _intake_view(row, idempotent_replay=True)

        resolution_status = "UNMATCHED"
        reason = None
        allocation_entry_id = None
        customer_id = None
        collection_request_id = None
        matched_by = None
        mapping = None
        if request.payer_token:
            mapping = connection.execute(
                "SELECT customer_id FROM payer_customer_mappings WHERE shop_id = ? AND payer_token = ?",
                (current_shop(), request.payer_token),
            ).fetchone()
        collection = None
        if reference:
            from app.services.recovery import find_collection_request  # lazy: avoids import cycle

            collection = find_collection_request(connection, reference)
            collection_request_id = collection["request_id"] if collection else None
        if request.status != "SUCCESS":
            resolution_status, reason = "IGNORED", "payment_not_successful"
        elif collection is not None and mapping is not None and mapping["customer_id"] != collection["customer_id"]:
            resolution_status, reason = "REVIEW", "payment_reference_conflicts_with_payer"
        elif collection is None and reference and mapping is None:
            resolution_status, reason = "UNMATCHED", "payment_reference_not_found"
        elif collection is None and not request.payer_token:
            resolution_status, reason = "UNMATCHED", "payer_token_missing"
        elif collection is None and mapping is None:
            resolution_status, reason = "UNMATCHED", "payer_token_not_mapped"
        else:
            matched_by = "payment_reference" if collection is not None else "payer_token"
            customer_id = collection["customer_id"] if collection is not None else mapping["customer_id"]
            balance = int(connection.execute(
                """SELECT COALESCE(SUM(CASE entry_type WHEN 'CREDIT' THEN amount_paise WHEN 'REPAYMENT' THEN -amount_paise END), 0)
                   FROM ledger_entries WHERE shop_id = ? AND customer_id = ? AND status = 'POSTED'""",
                (current_shop(), customer_id),
            ).fetchone()[0])
            if balance <= 0:
                resolution_status, reason = "REVIEW", "no_outstanding_balance"
            elif request.amount_paise > balance:
                resolution_status, reason = "REVIEW", "payment_exceeds_outstanding_balance"
            else:
                resolution_status = "ALLOCATED"
                allocation_entry_id = f"entry_{uuid.uuid4().hex[:12]}"
                allocation_source_id = f"payment:{request.event_id}:allocation"
                allocation_key = f"payalloc:{request.event_id}"
                connection.execute(
                    """INSERT INTO ledger_entries
                       (entry_id, shop_id, customer_id, entry_type, amount_paise, source_event_id, idempotency_key, status, created_at)
                       VALUES (?, ?, ?, 'REPAYMENT', ?, ?, ?, 'POSTED', ?)""",
                    (allocation_entry_id, current_shop(), customer_id, request.amount_paise, allocation_source_id, allocation_key, now),
                )
                append_event(
                    connection,
                    event_type="REPAYMENT_POSTED",
                    entity_type="LEDGER_ENTRY",
                    entity_id=allocation_entry_id,
                    source_event_id=allocation_source_id,
                    source_channel="provider_mock",
                    source_utterance=None,
                    status="POSTED",
                    summary=(f"Mock payment allocation of {request.amount_paise} paise recorded after exact "
                             + ("payment-reference match." if matched_by == "payment_reference" else "payer-token match.")),
                    idempotency_key=allocation_key,
                )
                from app.services.reminders import cancel_reminders_if_settled  # lazy: avoids import cycle

                cancel_reminders_if_settled(connection, customer_id)

        connection.execute(
            """INSERT INTO payment_events
               (event_id, shop_id, amount_paise, payment_status, occurred_at, payer_token, source, idempotency_key,
                resolution_status, resolution_reason, allocation_entry_id, created_at, payment_reference, collection_request_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (request.event_id, current_shop(), request.amount_paise, request.status, occurred_at, request.payer_token,
             request.source, request.idempotency_key, resolution_status, reason, allocation_entry_id, now,
             reference, collection_request_id),
        )
        append_event(
            connection,
            event_type="PAYMENT_RECEIVED",
            entity_type="PAYMENT_EVENT",
            entity_id=request.event_id,
            source_event_id=request.event_id,
            source_channel="provider_mock",
            source_utterance=None,
            status="OBSERVED",
            summary=f"Mock payment event received: {request.status}, {request.amount_paise} paise, resolution {resolution_status}.",
            idempotency_key=request.idempotency_key,
        )
        row = connection.execute("SELECT * FROM payment_events WHERE event_id = ?", (request.event_id,)).fetchone()
    return _intake_view(row)


def list_payment_review(limit: int = 50) -> list[PaymentReviewView]:
    bounded_limit = min(max(limit, 1), 100)
    with connect() as connection:
        rows = connection.execute(
            """SELECT event_id, amount_paise, payment_status, resolution_status, resolution_reason, occurred_at, created_at,
                      payment_reference
               FROM payment_events p WHERE p.shop_id = ? AND p.resolution_status IN ('REVIEW', 'UNMATCHED')
                 AND NOT EXISTS (SELECT 1 FROM payment_resolutions r WHERE r.shop_id = p.shop_id AND r.event_id = p.event_id)
               ORDER BY p.created_at DESC LIMIT ?""",
            (current_shop(), bounded_limit),
        ).fetchall()
    return [
        PaymentReviewView(
            event_id=row["event_id"], amount_paise=row["amount_paise"], status=row["payment_status"],
            resolution_status=row["resolution_status"], reason=row["resolution_reason"],
            occurred_at=datetime.fromisoformat(row["occurred_at"]), created_at=datetime.fromisoformat(row["created_at"]),
            payment_reference=row["payment_reference"],
        )
        for row in rows
    ]


def manually_allocate_payment(event_id: str, request: PaymentAllocationCreate) -> PaymentAllocationView:
    if not request.confirmed:
        raise HTTPException(status_code=409, detail="Merchant confirmation is required before allocating this payment.")
    now = datetime.now(timezone.utc).isoformat()
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            "SELECT * FROM payment_resolutions WHERE idempotency_key = ? OR (shop_id = ? AND event_id = ?) LIMIT 2",
            (request.idempotency_key, current_shop(), event_id),
        ).fetchall()
        if len(existing) > 1:
            raise HTTPException(status_code=409, detail="Resolution key and payment event resolve to different allocations.")
        if existing:
            row = existing[0]
            if row["event_id"] != event_id or row["customer_id"] != request.customer_id:
                raise HTTPException(status_code=409, detail="Payment was already allocated to a different customer.")
            return PaymentAllocationView(
                event_id=row["event_id"], customer_id=row["customer_id"], amount_paise=row["amount_paise"],
                allocation_entry_id=row["allocation_entry_id"], idempotent_replay=True,
            )

        payment = connection.execute(
            "SELECT * FROM payment_events WHERE shop_id = ? AND event_id = ?",
            (current_shop(), event_id),
        ).fetchone()
        if payment is None:
            raise HTTPException(status_code=404, detail="Payment event not found.")
        if payment["payment_status"] != "SUCCESS" or payment["resolution_status"] not in ("REVIEW", "UNMATCHED"):
            raise HTTPException(status_code=409, detail="Only successful unmatched or review-required payments can be manually allocated.")
        customer = connection.execute(
            "SELECT customer_id FROM customers WHERE shop_id = ? AND customer_id = ?",
            (current_shop(), request.customer_id),
        ).fetchone()
        if customer is None:
            raise HTTPException(status_code=404, detail="Customer not found in this demo shop.")
        balance = int(connection.execute(
            """SELECT COALESCE(SUM(CASE entry_type WHEN 'CREDIT' THEN amount_paise WHEN 'REPAYMENT' THEN -amount_paise END), 0)
               FROM ledger_entries WHERE shop_id = ? AND customer_id = ? AND status = 'POSTED'""",
            (current_shop(), request.customer_id),
        ).fetchone()[0])
        if balance <= 0:
            raise HTTPException(status_code=409, detail="Selected customer has no outstanding balance.")
        if payment["amount_paise"] > balance:
            raise HTTPException(
                status_code=409,
                detail={"code": "PAYMENT_EXCEEDS_OUTSTANDING_BALANCE", "balance_due_paise": balance, "payment_paise": payment["amount_paise"]},
            )

        resolution_id = f"resolution_{uuid.uuid4().hex[:12]}"
        entry_id = f"entry_{uuid.uuid4().hex[:12]}"
        source_event_id = f"payment:{event_id}:manual-allocation"
        ledger_key = f"manual-payalloc:{event_id}"
        connection.execute(
            """INSERT INTO ledger_entries
               (entry_id, shop_id, customer_id, entry_type, amount_paise, source_event_id, idempotency_key, status, created_at)
               VALUES (?, ?, ?, 'REPAYMENT', ?, ?, ?, 'POSTED', ?)""",
            (entry_id, current_shop(), request.customer_id, payment["amount_paise"], source_event_id, ledger_key, now),
        )
        connection.execute(
            """INSERT INTO payment_resolutions
               (resolution_id, shop_id, event_id, customer_id, amount_paise, allocation_entry_id, idempotency_key, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (resolution_id, current_shop(), event_id, request.customer_id, payment["amount_paise"], entry_id, request.idempotency_key, now),
        )
        append_event(
            connection,
            event_type="REPAYMENT_POSTED",
            entity_type="LEDGER_ENTRY",
            entity_id=entry_id,
            source_event_id=source_event_id,
            source_channel="text",
            source_utterance=None,
            status="POSTED",
            summary=f"Merchant-confirmed payment allocation of {payment['amount_paise']} paise recorded.",
            idempotency_key=ledger_key,
        )
        from app.services.reminders import cancel_reminders_if_settled  # lazy: avoids import cycle

        cancel_reminders_if_settled(connection, request.customer_id)
    return PaymentAllocationView(
        event_id=event_id, customer_id=request.customer_id, amount_paise=payment["amount_paise"], allocation_entry_id=entry_id,
    )


def _intake_view(row, idempotent_replay: bool = False) -> PaymentIntakeView:
    return PaymentIntakeView(
        event_id=row["event_id"], amount_paise=row["amount_paise"], status=row["payment_status"],
        resolution_status=row["resolution_status"], reason=row["resolution_reason"],
        allocation_entry_id=row["allocation_entry_id"], created_at=datetime.fromisoformat(row["created_at"]),
        idempotent_replay=idempotent_replay, payment_reference=row["payment_reference"],
        collection_request_id=row["collection_request_id"],
        matched_by=(None if row["resolution_status"] != "ALLOCATED"
                    else "payment_reference" if row["collection_request_id"] else "payer_token"),
    )
