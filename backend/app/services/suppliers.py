"""Supplier profiles and the append-only supplier payable ledger.

Supplier balances are money the shop owes. They live in their own tables and
never share rows, services, or response fields with customer udhaar.
"""

import re
import sqlite3
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from app.domain.models import (
    SupplierAdjustmentWrite,
    SupplierBalanceView,
    SupplierCreate,
    SupplierPayableEntryView,
    SupplierPaymentWrite,
    SupplierResolution,
    SupplierView,
)
from app.services.database import DEMO_SHOP_ID, connect
from app.services.events import append_event
from app.services.ledger import normalize_alias

INCREASES_DUE = {"INVOICE_CREDIT", "ADJUSTMENT_INCREASE"}
DECREASES_DUE = {"PAYMENT", "DEBIT_NOTE", "ADJUSTMENT_DECREASE"}
PHONE_PATTERN = re.compile(r"^\+?[0-9][0-9 -]{6,18}[0-9]$")

DUE_SQL = """SELECT
    COALESCE(SUM(CASE WHEN entry_type IN ('INVOICE_CREDIT', 'ADJUSTMENT_INCREASE') THEN amount_paise
                      ELSE -amount_paise END), 0)
  FROM supplier_payable_entries
  WHERE shop_id = ? AND supplier_id = ? AND status = 'POSTED'"""


def mask_phone(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    return f"{'*' * max(len(digits) - 4, 0)}{digits[-4:]}"


def create_supplier(request: SupplierCreate) -> SupplierView:
    if not request.confirmed:
        raise HTTPException(status_code=409, detail="Merchant confirmation is required before creating a supplier.")
    display_name = request.display_name.strip()
    if not display_name:
        raise HTTPException(status_code=422, detail="Supplier name cannot be blank.")
    phone = request.contact_phone.strip() if request.contact_phone else None
    if phone and not PHONE_PATTERN.fullmatch(phone):
        raise HTTPException(status_code=422, detail="Supplier contact phone must contain only digits, spaces, dashes, or a leading +.")
    note = request.contact_note.strip() if request.contact_note else None
    aliases = list(dict.fromkeys([display_name, *(alias.strip() for alias in request.aliases if alias.strip())]))
    now = datetime.now(timezone.utc).isoformat()

    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        replay = connection.execute(
            "SELECT * FROM suppliers WHERE idempotency_key = ?", (request.idempotency_key,)
        ).fetchone()
        if replay:
            stored_aliases = {
                row["alias_normalized"]
                for row in connection.execute(
                    "SELECT alias_normalized FROM supplier_aliases WHERE shop_id = ? AND supplier_id = ?",
                    (DEMO_SHOP_ID, replay["supplier_id"]),
                )
            }
            same = (
                replay["display_name"] == display_name
                and replay["contact_phone"] == phone
                and replay["contact_note"] == note
                and stored_aliases == {normalize_alias(alias) for alias in aliases}
            )
            if not same:
                raise HTTPException(status_code=409, detail="Idempotency key was already used to create a different supplier.")
            return supplier_view(connection, replay["supplier_id"])

        supplier_id = f"supplier_{uuid.uuid4().hex[:12]}"
        connection.execute(
            """INSERT INTO suppliers(supplier_id, shop_id, display_name, contact_phone, contact_note, idempotency_key, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (supplier_id, DEMO_SHOP_ID, display_name, phone, note, request.idempotency_key, now),
        )
        for alias in aliases:
            connection.execute(
                "INSERT INTO supplier_aliases(alias_id, shop_id, supplier_id, alias, alias_normalized) VALUES (?, ?, ?, ?, ?)",
                (f"salias_{uuid.uuid4().hex[:12]}", DEMO_SHOP_ID, supplier_id, alias, normalize_alias(alias)),
            )
        append_event(
            connection,
            event_type="SUPPLIER_CREATED",
            entity_type="SUPPLIER",
            entity_id=supplier_id,
            source_event_id=request.idempotency_key,
            source_channel=request.source_channel,
            source_utterance=request.source_utterance,
            status="POSTED",
            summary=f"Supplier record created for {display_name}.",
            idempotency_key=request.idempotency_key,
        )
        return supplier_view(connection, supplier_id)


def list_suppliers() -> list[SupplierView]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT supplier_id FROM suppliers WHERE shop_id = ? ORDER BY display_name", (DEMO_SHOP_ID,)
        ).fetchall()
        return [supplier_view(connection, row["supplier_id"]) for row in rows]


def resolve_supplier_in(connection: sqlite3.Connection, query: str) -> SupplierResolution:
    rows = connection.execute(
        """SELECT DISTINCT s.supplier_id, s.display_name
           FROM suppliers s
           JOIN supplier_aliases a ON a.shop_id = s.shop_id AND a.supplier_id = s.supplier_id
           WHERE s.shop_id = ? AND a.alias_normalized = ?
           ORDER BY s.display_name""",
        (DEMO_SHOP_ID, normalize_alias(query)),
    ).fetchall()
    matches = [supplier_view(connection, row["supplier_id"]) for row in rows]
    status = "NOT_FOUND" if not matches else "RESOLVED" if len(matches) == 1 else "AMBIGUOUS"
    return SupplierResolution(status=status, query=query, matches=matches)


def resolve_supplier(query: str) -> SupplierResolution:
    with connect() as connection:
        return resolve_supplier_in(connection, query)


def supplier_due(connection: sqlite3.Connection, supplier_id: str) -> int:
    return int(connection.execute(DUE_SQL, (DEMO_SHOP_ID, supplier_id)).fetchone()[0])


def get_supplier_balance(supplier_id: str) -> SupplierBalanceView:
    with connect() as connection:
        supplier = _require_supplier(connection, supplier_id)
        totals = {
            row["entry_type"]: int(row["total"])
            for row in connection.execute(
                """SELECT entry_type, SUM(amount_paise) AS total FROM supplier_payable_entries
                   WHERE shop_id = ? AND supplier_id = ? AND status = 'POSTED' GROUP BY entry_type""",
                (DEMO_SHOP_ID, supplier_id),
            )
        }
        count = connection.execute(
            "SELECT COUNT(*) FROM supplier_payable_entries WHERE shop_id = ? AND supplier_id = ?",
            (DEMO_SHOP_ID, supplier_id),
        ).fetchone()[0]
        due = supplier_due(connection, supplier_id)
    return SupplierBalanceView(
        supplier_id=supplier_id,
        display_name=supplier["display_name"],
        amount_due_paise=due,
        entry_count=int(count),
        totals_by_type_paise=totals,
    )


def list_supplier_entries(supplier_id: str, limit: int = 100) -> list[SupplierPayableEntryView]:
    with connect() as connection:
        _require_supplier(connection, supplier_id)
        rows = connection.execute(
            """SELECT * FROM supplier_payable_entries WHERE shop_id = ? AND supplier_id = ?
               ORDER BY created_at DESC, entry_id DESC LIMIT ?""",
            (DEMO_SHOP_ID, supplier_id, min(max(limit, 1), 200)),
        ).fetchall()
    return [entry_view(row) for row in rows]


def record_supplier_payment(supplier_id: str, request: SupplierPaymentWrite) -> SupplierPayableEntryView:
    """Record a payment the merchant says they already made. No money is transferred."""
    return _merchant_entry(supplier_id, request, "PAYMENT", request.note)


def record_supplier_adjustment(supplier_id: str, request: SupplierAdjustmentWrite) -> SupplierPayableEntryView:
    return _merchant_entry(supplier_id, request, request.entry_type, request.note.strip())


def _merchant_entry(supplier_id, request, entry_type: str, note: str | None) -> SupplierPayableEntryView:
    if not request.confirmed:
        raise HTTPException(status_code=409, detail="Merchant confirmation is required before changing a supplier balance.")
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row, replay = append_payable_entry(
            connection,
            supplier_id=supplier_id,
            entry_type=entry_type,
            amount_paise=request.amount_paise,
            source_kind="merchant_entry",
            source_document_id=None,
            note=note,
            source_event_id=request.source_event_id,
            idempotency_key=request.idempotency_key,
            source_channel=request.source_channel,
            source_utterance=request.source_utterance,
        )
    return entry_view(row, idempotent_replay=replay)


def append_payable_entry(
    connection: sqlite3.Connection,
    *,
    supplier_id: str,
    entry_type: str,
    amount_paise: int,
    source_kind: str,
    source_document_id: str | None,
    note: str | None,
    source_event_id: str,
    idempotency_key: str,
    source_channel: str,
    source_utterance: str | None,
) -> tuple[sqlite3.Row, bool]:
    """Append one payable entry inside the caller's open transaction.

    Returns ``(row, idempotent_replay)``. The caller owns commit/rollback so this
    can be part of a larger atomic posting (for example, an invoice receipt).
    """
    if amount_paise <= 0:
        raise HTTPException(status_code=422, detail="Supplier payable amounts must be positive paise.")
    supplier = _require_supplier(connection, supplier_id)
    existing = connection.execute(
        """SELECT * FROM supplier_payable_entries
           WHERE idempotency_key = ? OR (shop_id = ? AND source_event_id = ?) LIMIT 2""",
        (idempotency_key, DEMO_SHOP_ID, source_event_id),
    ).fetchall()
    if len(existing) > 1:
        raise HTTPException(status_code=409, detail="Idempotency key and source event resolve to different supplier entries.")
    if existing:
        row = existing[0]
        same = (
            row["supplier_id"] == supplier_id
            and row["entry_type"] == entry_type
            and row["amount_paise"] == amount_paise
            and row["source_event_id"] == source_event_id
            and row["idempotency_key"] == idempotency_key
        )
        if not same:
            raise HTTPException(status_code=409, detail="Idempotency key was already used for a different supplier entry.")
        return row, True

    if entry_type in DECREASES_DUE:
        due = supplier_due(connection, supplier_id)
        if amount_paise > due:
            raise HTTPException(
                status_code=409,
                detail={"code": "SUPPLIER_DECREASE_EXCEEDS_DUE", "amount_due_paise": due, "requested_paise": amount_paise},
            )

    entry_id = f"spay_{uuid.uuid4().hex[:12]}"
    connection.execute(
        """INSERT INTO supplier_payable_entries
           (entry_id, shop_id, supplier_id, entry_type, amount_paise, source_kind, source_document_id, note,
            source_event_id, idempotency_key, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'POSTED', ?)""",
        (entry_id, DEMO_SHOP_ID, supplier_id, entry_type, amount_paise, source_kind, source_document_id, note,
         source_event_id, idempotency_key, datetime.now(timezone.utc).isoformat()),
    )
    verb = "increased" if entry_type in INCREASES_DUE else "reduced"
    append_event(
        connection,
        event_type=f"SUPPLIER_{entry_type}_POSTED",
        entity_type="SUPPLIER_PAYABLE_ENTRY",
        entity_id=entry_id,
        source_event_id=source_event_id,
        source_channel=source_channel,
        source_utterance=source_utterance,
        status="POSTED",
        summary=f"Supplier payable to {supplier['display_name']} {verb} by {amount_paise} paise ({entry_type}).",
        idempotency_key=idempotency_key,
    )
    row = connection.execute("SELECT * FROM supplier_payable_entries WHERE entry_id = ?", (entry_id,)).fetchone()
    return row, False


def supplier_view(connection: sqlite3.Connection, supplier_id: str) -> SupplierView:
    supplier = _require_supplier(connection, supplier_id)
    aliases = connection.execute(
        "SELECT alias FROM supplier_aliases WHERE shop_id = ? AND supplier_id = ? ORDER BY alias",
        (DEMO_SHOP_ID, supplier_id),
    ).fetchall()
    return SupplierView(
        supplier_id=supplier["supplier_id"],
        display_name=supplier["display_name"],
        aliases=[row["alias"] for row in aliases],
        contact_phone_masked=mask_phone(supplier["contact_phone"]),
    )


def _require_supplier(connection: sqlite3.Connection, supplier_id: str) -> sqlite3.Row:
    supplier = connection.execute(
        "SELECT * FROM suppliers WHERE shop_id = ? AND supplier_id = ?", (DEMO_SHOP_ID, supplier_id)
    ).fetchone()
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found in this demo shop.")
    return supplier


def entry_view(row: sqlite3.Row, idempotent_replay: bool = False) -> SupplierPayableEntryView:
    return SupplierPayableEntryView(
        entry_id=row["entry_id"],
        supplier_id=row["supplier_id"],
        entry_type=row["entry_type"],
        direction="INCREASES_DUE" if row["entry_type"] in INCREASES_DUE else "DECREASES_DUE",
        amount_paise=row["amount_paise"],
        source_kind=row["source_kind"],
        source_document_id=row["source_document_id"],
        note=row["note"],
        status=row["status"],
        source_event_id=row["source_event_id"],
        created_at=datetime.fromisoformat(row["created_at"]),
        idempotent_replay=idempotent_replay,
    )
