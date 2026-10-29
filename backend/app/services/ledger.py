"""Append-only customer credit ledger and alias resolution."""

import unicodedata
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from app.domain.models import CustomerBalance, CustomerCreate, CustomerResolution, CustomerView, LedgerEntryView, LedgerWrite
from app.services.database import DEMO_SHOP_ID, connect
from app.services.events import append_event


def normalize_alias(value: str) -> str:
    """Normalize whitespace and case while retaining the original display text."""
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def create_customer(request: CustomerCreate) -> CustomerView:
    if not request.confirmed:
        raise HTTPException(status_code=409, detail="Merchant confirmation is required before creating a customer.")

    display_name = request.display_name.strip()
    if not display_name:
        raise HTTPException(status_code=422, detail="Customer name cannot be blank.")
    aliases = list(dict.fromkeys([display_name, *(alias.strip() for alias in request.aliases if alias.strip())]))
    key = request.idempotency_key
    now = datetime.now(timezone.utc).isoformat()

    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        replay = connection.execute(
            "SELECT customer_id, display_name FROM customers WHERE idempotency_key = ?",
            (key,),
        ).fetchone()
        if replay:
            if replay["display_name"] != display_name:
                raise HTTPException(status_code=409, detail="Idempotency key was already used to create a different customer.")
            stored_aliases = connection.execute(
                "SELECT alias_normalized FROM customer_aliases WHERE shop_id = ? AND customer_id = ?",
                (DEMO_SHOP_ID, replay["customer_id"]),
            ).fetchall()
            expected_aliases = {normalize_alias(alias) for alias in aliases}
            if {row["alias_normalized"] for row in stored_aliases} != expected_aliases:
                raise HTTPException(status_code=409, detail="Idempotency key was already used with different customer aliases.")
            return _customer_view(connection, replay["customer_id"])

        customer_id = f"cust_{uuid.uuid4().hex[:12]}"
        connection.execute(
            "INSERT INTO customers(customer_id, shop_id, display_name, idempotency_key, created_at) VALUES (?, ?, ?, ?, ?)",
            (customer_id, DEMO_SHOP_ID, display_name, key, now),
        )
        for alias in aliases:
            connection.execute(
                "INSERT INTO customer_aliases(alias_id, shop_id, customer_id, alias, alias_normalized) VALUES (?, ?, ?, ?, ?)",
                (f"alias_{uuid.uuid4().hex[:12]}", DEMO_SHOP_ID, customer_id, alias, normalize_alias(alias)),
            )
        append_event(
            connection,
            event_type="CUSTOMER_CREATED",
            entity_type="CUSTOMER",
            entity_id=customer_id,
            source_event_id=key,
            source_channel=request.source_channel,
            source_utterance=request.source_utterance,
            status="POSTED",
            summary=f"Customer record created for {display_name}.",
            idempotency_key=key,
        )
        return _customer_view(connection, customer_id)


def resolve_customer(query: str) -> CustomerResolution:
    normalized = normalize_alias(query)
    with connect() as connection:
        rows = connection.execute(
            """SELECT DISTINCT c.customer_id, c.display_name
               FROM customers c
               LEFT JOIN customer_aliases a
                 ON a.shop_id = c.shop_id AND a.customer_id = c.customer_id
               WHERE c.shop_id = ?
                 AND a.alias_normalized = ?
               ORDER BY c.display_name""",
            (DEMO_SHOP_ID, normalized),
        ).fetchall()
        matches = [_customer_view(connection, row["customer_id"]) for row in rows]
    status = "NOT_FOUND" if not matches else "RESOLVED" if len(matches) == 1 else "AMBIGUOUS"
    return CustomerResolution(status=status, query=query, matches=matches)


def get_balance(customer_id: str) -> CustomerBalance:
    with connect() as connection:
        customer = connection.execute(
            "SELECT customer_id, display_name FROM customers WHERE shop_id = ? AND customer_id = ?",
            (DEMO_SHOP_ID, customer_id),
        ).fetchone()
        if customer is None:
            raise HTTPException(status_code=404, detail="Customer not found in this demo shop.")
        result = connection.execute(
            """SELECT
                 COALESCE(SUM(CASE entry_type WHEN 'CREDIT' THEN amount_paise WHEN 'REPAYMENT' THEN -amount_paise END), 0) AS due,
                 COUNT(*) AS entry_count
               FROM ledger_entries
               WHERE shop_id = ? AND customer_id = ? AND status = 'POSTED'""",
            (DEMO_SHOP_ID, customer_id),
        ).fetchone()
    return CustomerBalance(
        customer_id=customer["customer_id"],
        display_name=customer["display_name"],
        balance_due_paise=int(result["due"]),
        entry_count=int(result["entry_count"]),
    )


def post_credit(request: LedgerWrite) -> LedgerEntryView:
    return _post_ledger_entry(request, entry_type="CREDIT")


def post_repayment(request: LedgerWrite) -> LedgerEntryView:
    return _post_ledger_entry(request, entry_type="REPAYMENT")


def _post_ledger_entry(request: LedgerWrite, entry_type: str) -> LedgerEntryView:
    if not request.confirmed:
        raise HTTPException(status_code=409, detail="Merchant confirmation is required before posting a ledger entry.")

    now = datetime.now(timezone.utc).isoformat()
    entry_id = f"entry_{uuid.uuid4().hex[:12]}"
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        existing_rows = connection.execute(
            "SELECT * FROM ledger_entries WHERE idempotency_key = ? OR (shop_id = ? AND source_event_id = ?) LIMIT 2",
            (request.idempotency_key, DEMO_SHOP_ID, request.source_event_id),
        ).fetchall()
        if len(existing_rows) > 1:
            raise HTTPException(status_code=409, detail="Idempotency key and source event resolve to different ledger entries.")
        if existing_rows:
            existing = existing_rows[0]
            same_operation = (
                existing["customer_id"] == request.customer_id
                and existing["entry_type"] == entry_type
                and existing["amount_paise"] == request.amount_paise
                and existing["source_event_id"] == request.source_event_id
            )
            if not same_operation:
                raise HTTPException(status_code=409, detail="Idempotency key was already used for a different ledger operation.")
            return _entry_view(existing, idempotent_replay=True)

        customer = connection.execute(
            "SELECT customer_id FROM customers WHERE shop_id = ? AND customer_id = ?",
            (DEMO_SHOP_ID, request.customer_id),
        ).fetchone()
        if customer is None:
            raise HTTPException(status_code=404, detail="Customer not found in this demo shop.")

        if entry_type == "REPAYMENT":
            balance = connection.execute(
                """SELECT COALESCE(SUM(CASE entry_type WHEN 'CREDIT' THEN amount_paise WHEN 'REPAYMENT' THEN -amount_paise END), 0)
                   FROM ledger_entries WHERE shop_id = ? AND customer_id = ? AND status = 'POSTED'""",
                (DEMO_SHOP_ID, request.customer_id),
            ).fetchone()[0]
            if request.amount_paise > int(balance):
                raise HTTPException(
                    status_code=409,
                    detail={"code": "REPAYMENT_EXCEEDS_BALANCE", "balance_due_paise": int(balance), "requested_paise": request.amount_paise},
                )

        connection.execute(
            """INSERT INTO ledger_entries
               (entry_id, shop_id, customer_id, entry_type, amount_paise, source_event_id, idempotency_key, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'POSTED', ?)""",
            (entry_id, DEMO_SHOP_ID, request.customer_id, entry_type, request.amount_paise, request.source_event_id, request.idempotency_key, now),
        )
        row = connection.execute("SELECT * FROM ledger_entries WHERE entry_id = ?", (entry_id,)).fetchone()
        append_event(
            connection,
            event_type=f"{entry_type}_POSTED",
            entity_type="LEDGER_ENTRY",
            entity_id=entry_id,
            source_event_id=request.source_event_id,
            source_channel=request.source_channel,
            source_utterance=request.source_utterance,
            status="POSTED",
            summary=f"{entry_type.title()} of {request.amount_paise} paise recorded.",
            idempotency_key=request.idempotency_key,
        )
    return _entry_view(row)


def _customer_view(connection: sqlite3.Connection, customer_id: str) -> CustomerView:
    customer = connection.execute(
        "SELECT customer_id, display_name FROM customers WHERE shop_id = ? AND customer_id = ?",
        (DEMO_SHOP_ID, customer_id),
    ).fetchone()
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found in this demo shop.")
    aliases = connection.execute(
        "SELECT alias FROM customer_aliases WHERE shop_id = ? AND customer_id = ? ORDER BY alias",
        (DEMO_SHOP_ID, customer_id),
    ).fetchall()
    return CustomerView(customer_id=customer["customer_id"], display_name=customer["display_name"], aliases=[row["alias"] for row in aliases])


def _entry_view(row: sqlite3.Row, idempotent_replay: bool = False) -> LedgerEntryView:
    return LedgerEntryView(
        entry_id=row["entry_id"],
        customer_id=row["customer_id"],
        entry_type=row["entry_type"],
        amount_paise=row["amount_paise"],
        status=row["status"],
        source_event_id=row["source_event_id"],
        created_at=datetime.fromisoformat(row["created_at"]),
        idempotent_replay=idempotent_replay,
    )
