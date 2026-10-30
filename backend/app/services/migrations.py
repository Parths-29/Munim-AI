"""Versioned, additive SQLite migrations.

Migration 1 is the original idempotent baseline schema, so databases created
before versioning upgrade in place. Later migrations only add tables, indexes,
and triggers; they never rebuild or rewrite existing rows.
"""

import sqlite3
from datetime import datetime, timezone


def _append_only(table: str, label: str) -> str:
    return f"""
CREATE TRIGGER IF NOT EXISTS {table}_no_update
BEFORE UPDATE ON {table}
BEGIN
    SELECT RAISE(ABORT, '{label} are append-only');
END;

CREATE TRIGGER IF NOT EXISTS {table}_no_delete
BEFORE DELETE ON {table}
BEGIN
    SELECT RAISE(ABORT, '{label} are append-only');
END;
"""


SUPPLIERS = """
CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id TEXT PRIMARY KEY,
    shop_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    contact_phone TEXT,
    contact_note TEXT,
    idempotency_key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    UNIQUE (shop_id, supplier_id)
);

CREATE TABLE IF NOT EXISTS supplier_aliases (
    alias_id TEXT PRIMARY KEY,
    shop_id TEXT NOT NULL,
    supplier_id TEXT NOT NULL,
    alias TEXT NOT NULL,
    alias_normalized TEXT NOT NULL,
    FOREIGN KEY (shop_id, supplier_id) REFERENCES suppliers(shop_id, supplier_id)
);

CREATE INDEX IF NOT EXISTS ix_supplier_alias_lookup
    ON supplier_aliases(shop_id, alias_normalized);

-- Amounts are always positive. INVOICE_CREDIT and ADJUSTMENT_INCREASE raise the
-- amount the shop owes; PAYMENT, DEBIT_NOTE and ADJUSTMENT_DECREASE lower it.
CREATE TABLE IF NOT EXISTS supplier_payable_entries (
    entry_id TEXT PRIMARY KEY,
    shop_id TEXT NOT NULL,
    supplier_id TEXT NOT NULL,
    entry_type TEXT NOT NULL CHECK (entry_type IN
        ('INVOICE_CREDIT', 'PAYMENT', 'DEBIT_NOTE', 'ADJUSTMENT_INCREASE', 'ADJUSTMENT_DECREASE')),
    amount_paise INTEGER NOT NULL CHECK (amount_paise > 0),
    source_kind TEXT NOT NULL CHECK (source_kind IN ('invoice_receipt', 'merchant_entry')),
    source_document_id TEXT,
    note TEXT,
    source_event_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK (status = 'POSTED'),
    created_at TEXT NOT NULL,
    FOREIGN KEY (shop_id, supplier_id) REFERENCES suppliers(shop_id, supplier_id),
    UNIQUE (shop_id, source_event_id)
);

CREATE INDEX IF NOT EXISTS ix_supplier_payable_time
    ON supplier_payable_entries(shop_id, supplier_id, created_at);
""" + _append_only("supplier_payable_entries", "supplier payable entries")


INTAKE_AND_RECEIPTS = """
-- Merchant-confirmed conversions such as "1 case = 24 packet". Append-only; the
-- latest row for (product, unit) wins.
CREATE TABLE IF NOT EXISTS product_unit_conversions (
    conversion_id TEXT PRIMARY KEY,
    shop_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    unit TEXT NOT NULL,
    base_units_per_unit INTEGER NOT NULL CHECK (base_units_per_unit > 0),
    idempotency_key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    FOREIGN KEY (shop_id, product_id) REFERENCES products(shop_id, product_id)
);

CREATE INDEX IF NOT EXISTS ix_unit_conversion_lookup
    ON product_unit_conversions(shop_id, product_id, unit, created_at);

-- Draft proposals are mutable working state (versioned); they are not ledger
-- records and never change stock or payables by themselves.
CREATE TABLE IF NOT EXISTS intake_proposals (
    proposal_id TEXT PRIMARY KEY,
    shop_id TEXT NOT NULL,
    source_kind TEXT NOT NULL CHECK (source_kind IN ('invoice_image', 'manual_invoice', 'voice_inward', 'text_inward')),
    status TEXT NOT NULL CHECK (status IN ('NEEDS_REVIEW', 'READY', 'CONFIRMED', 'REJECTED', 'EXPIRED')),
    version INTEGER NOT NULL CHECK (version >= 1),
    content_hash TEXT NOT NULL,
    draft_json TEXT NOT NULL,
    extraction_json TEXT NOT NULL,
    image_sha256 TEXT,
    source_utterance TEXT,
    idempotency_key TEXT NOT NULL UNIQUE,
    posted_receipt_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_intake_proposals_status
    ON intake_proposals(shop_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS intake_proposal_revisions (
    revision_id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL REFERENCES intake_proposals(proposal_id),
    version INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    draft_json TEXT NOT NULL,
    actor TEXT NOT NULL CHECK (actor IN ('extraction', 'parser', 'merchant')),
    created_at TEXT NOT NULL,
    UNIQUE (proposal_id, version)
);
""" + _append_only("intake_proposal_revisions", "proposal revisions") + """
CREATE TABLE IF NOT EXISTS stock_receipts (
    receipt_id TEXT PRIMARY KEY,
    shop_id TEXT NOT NULL,
    proposal_id TEXT NOT NULL UNIQUE REFERENCES intake_proposals(proposal_id),
    proposal_version INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    supplier_id TEXT,
    supplier_label TEXT,
    invoice_number TEXT,
    invoice_number_normalized TEXT,
    invoice_date TEXT,
    total_paise INTEGER CHECK (total_paise IS NULL OR total_paise >= 0),
    paid_now_paise INTEGER CHECK (paid_now_paise IS NULL OR paid_now_paise >= 0),
    payable_entry_id TEXT,
    supplier_due_before_paise INTEGER,
    line_count INTEGER NOT NULL CHECK (line_count > 0),
    source_channel TEXT NOT NULL,
    source_event_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    FOREIGN KEY (shop_id, supplier_id) REFERENCES suppliers(shop_id, supplier_id),
    UNIQUE (shop_id, source_event_id),
    CHECK (paid_now_paise IS NULL OR total_paise IS NULL OR paid_now_paise <= total_paise)
);

-- One supplier invoice number can be posted once.
CREATE UNIQUE INDEX IF NOT EXISTS ux_stock_receipts_supplier_invoice
    ON stock_receipts(shop_id, supplier_id, invoice_number_normalized)
    WHERE supplier_id IS NOT NULL AND invoice_number_normalized IS NOT NULL;
""" + _append_only("stock_receipts", "stock receipts") + """
-- Inward stock movements. On-hand = SUM(inventory_movements) + SUM(these).
CREATE TABLE IF NOT EXISTS stock_receipt_movements (
    movement_id TEXT PRIMARY KEY,
    shop_id TEXT NOT NULL,
    receipt_id TEXT NOT NULL REFERENCES stock_receipts(receipt_id),
    line_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    quantity_delta INTEGER NOT NULL CHECK (quantity_delta > 0),
    unit TEXT NOT NULL,
    received_quantity INTEGER NOT NULL CHECK (received_quantity > 0),
    received_unit TEXT NOT NULL,
    base_units_per_unit INTEGER NOT NULL CHECK (base_units_per_unit > 0),
    unit_cost_paise INTEGER CHECK (unit_cost_paise IS NULL OR unit_cost_paise >= 0),
    line_total_paise INTEGER CHECK (line_total_paise IS NULL OR line_total_paise >= 0),
    source_text TEXT,
    on_hand_before INTEGER NOT NULL,
    reason TEXT NOT NULL CHECK (reason = 'STOCK_RECEIPT'),
    status TEXT NOT NULL CHECK (status = 'POSTED'),
    created_at TEXT NOT NULL,
    FOREIGN KEY (shop_id, product_id) REFERENCES products(shop_id, product_id),
    UNIQUE (receipt_id, line_id)
);

CREATE INDEX IF NOT EXISTS ix_receipt_movements_product
    ON stock_receipt_movements(shop_id, product_id, created_at);
""" + _append_only("stock_receipt_movements", "stock receipt movements")


def _baseline() -> str:
    from app.services.database import SCHEMA

    # foreign_keys is set per connection; the PRAGMA is a no-op inside a transaction.
    return SCHEMA.replace("PRAGMA foreign_keys = ON;", "")


MIGRATIONS: list[tuple[int, str, object]] = [
    (1, "baseline_v0_schema", _baseline),
    (2, "suppliers_and_payables", SUPPLIERS),
    (3, "intake_proposals_and_stock_receipts", INTAKE_AND_RECEIPTS),
]


def applied_versions(connection: sqlite3.Connection) -> list[int]:
    connection.execute(
        """CREATE TABLE IF NOT EXISTS schema_migrations (
               version INTEGER PRIMARY KEY,
               name TEXT NOT NULL,
               applied_at TEXT NOT NULL
           )"""
    )
    return [row[0] for row in connection.execute("SELECT version FROM schema_migrations ORDER BY version")]


def run_migrations(connection: sqlite3.Connection) -> list[int]:
    """Apply pending migrations in order; each one commits or rolls back as a unit."""
    done = set(applied_versions(connection))
    newly_applied = []
    for version, name, script in MIGRATIONS:
        if version in done:
            continue
        sql = script() if callable(script) else script
        now = datetime.now(timezone.utc).isoformat()
        try:
            connection.executescript(
                "BEGIN IMMEDIATE;\n" + sql
                + f"\nINSERT INTO schema_migrations(version, name, applied_at) VALUES ({version}, '{name}', '{now}');\nCOMMIT;"
            )
        except BaseException:
            if connection.in_transaction:
                connection.rollback()
            raise
        newly_applied.append(version)
    return newly_applied
