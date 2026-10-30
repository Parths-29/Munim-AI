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


def _baseline() -> str:
    from app.services.database import SCHEMA

    # foreign_keys is set per connection; the PRAGMA is a no-op inside a transaction.
    return SCHEMA.replace("PRAGMA foreign_keys = ON;", "")


MIGRATIONS: list[tuple[int, str, object]] = [
    (1, "baseline_v0_schema", _baseline),
    (2, "suppliers_and_payables", SUPPLIERS),
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
