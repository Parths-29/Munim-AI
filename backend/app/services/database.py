"""SQLite initialization and connection helpers for the single-shop demo."""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = BACKEND_ROOT / "data" / "munim.sqlite3"
DB_PATH = Path(os.environ.get("MUNIM_DB_PATH") or DEFAULT_DB_PATH).expanduser()
DEMO_SHOP_ID = "shop_synth_01"


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY,
    shop_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    UNIQUE (shop_id, customer_id)
);

CREATE TABLE IF NOT EXISTS customer_aliases (
    alias_id TEXT PRIMARY KEY,
    shop_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    alias TEXT NOT NULL,
    alias_normalized TEXT NOT NULL,
    FOREIGN KEY (shop_id, customer_id) REFERENCES customers(shop_id, customer_id)
);

CREATE INDEX IF NOT EXISTS ix_customer_alias_lookup
    ON customer_aliases(shop_id, alias_normalized);

CREATE TABLE IF NOT EXISTS ledger_entries (
    entry_id TEXT PRIMARY KEY,
    shop_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    entry_type TEXT NOT NULL CHECK (entry_type IN ('CREDIT', 'REPAYMENT')),
    amount_paise INTEGER NOT NULL CHECK (amount_paise > 0),
    source_event_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK (status = 'POSTED'),
    created_at TEXT NOT NULL,
    FOREIGN KEY (shop_id, customer_id) REFERENCES customers(shop_id, customer_id),
    UNIQUE (shop_id, source_event_id)
);

CREATE INDEX IF NOT EXISTS ix_ledger_customer_time
    ON ledger_entries(shop_id, customer_id, created_at);

CREATE TRIGGER IF NOT EXISTS ledger_entries_no_update
BEFORE UPDATE ON ledger_entries
BEGIN
    SELECT RAISE(ABORT, 'ledger entries are append-only');
END;

CREATE TRIGGER IF NOT EXISTS ledger_entries_no_delete
BEFORE DELETE ON ledger_entries
BEGIN
    SELECT RAISE(ABORT, 'ledger entries are append-only');
END;
"""


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Yield a short-lived connection and always close it after the request."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        if connection.in_transaction:
            connection.commit()
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database() -> None:
    """Create the minimal demo schema if it does not already exist."""
    with connect() as connection:
        connection.executescript(SCHEMA)


