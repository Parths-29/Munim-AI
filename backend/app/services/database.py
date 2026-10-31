"""SQLite initialization and connection helpers for the single-shop demo."""

import os
import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Iterator


BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = BACKEND_ROOT / "data" / "munim.sqlite3"
DB_PATH = Path(os.environ.get("MUNIM_DB_PATH") or DEFAULT_DB_PATH).expanduser()
DEMO_SHOP_ID = "shop_synth_01"

# Synthetic demo shops. Each persona has its own customers, stock, suppliers, and reminders.
SHOPS = {
    "kirana": "shop_synth_01",
    "tea_stall": "shop_synth_tea",
    "medical_store": "shop_synth_medical",
}
_CURRENT_SHOP: ContextVar[str] = ContextVar("munim_shop", default=DEMO_SHOP_ID)


def current_shop() -> str:
    """Shop for the current request (set from the X-Munim-Shop header); defaults to the kirana demo shop."""
    return _CURRENT_SHOP.get()


def resolve_shop(value: str | None) -> str:
    if not value:
        return DEMO_SHOP_ID
    value = value.strip()
    if value in SHOPS:
        return SHOPS[value]
    if value in SHOPS.values():
        return value
    raise ValueError(value)


@contextmanager
def use_shop(shop_id: str) -> Iterator[None]:
    token = _CURRENT_SHOP.set(shop_id)
    try:
        yield
    finally:
        _CURRENT_SHOP.reset(token)


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

CREATE TABLE IF NOT EXISTS products (
    product_id TEXT PRIMARY KEY,
    shop_id TEXT NOT NULL,
    name TEXT NOT NULL,
    unit TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    UNIQUE (shop_id, product_id)
);

CREATE TABLE IF NOT EXISTS product_aliases (
    alias_id TEXT PRIMARY KEY,
    shop_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    alias TEXT NOT NULL,
    alias_normalized TEXT NOT NULL,
    FOREIGN KEY (shop_id, product_id) REFERENCES products(shop_id, product_id)
);

CREATE INDEX IF NOT EXISTS ix_product_alias_lookup
    ON product_aliases(shop_id, alias_normalized);

CREATE TABLE IF NOT EXISTS inventory_movements (
    movement_id TEXT PRIMARY KEY,
    shop_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    quantity_delta INTEGER NOT NULL,
    counted_quantity INTEGER NOT NULL CHECK (counted_quantity >= 0),
    unit TEXT NOT NULL,
    reason TEXT NOT NULL CHECK (reason = 'PHYSICAL_COUNT'),
    source_event_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK (status = 'POSTED'),
    created_at TEXT NOT NULL,
    FOREIGN KEY (shop_id, product_id) REFERENCES products(shop_id, product_id),
    UNIQUE (shop_id, source_event_id)
);

CREATE INDEX IF NOT EXISTS ix_inventory_product_time
    ON inventory_movements(shop_id, product_id, created_at);

CREATE TRIGGER IF NOT EXISTS inventory_movements_no_update
BEFORE UPDATE ON inventory_movements
BEGIN
    SELECT RAISE(ABORT, 'inventory movements are append-only');
END;

CREATE TRIGGER IF NOT EXISTS inventory_movements_no_delete
BEFORE DELETE ON inventory_movements
BEGIN
    SELECT RAISE(ABORT, 'inventory movements are append-only');
END;

CREATE TABLE IF NOT EXISTS stockout_observations (
    observation_id TEXT PRIMARY KEY,
    shop_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    source_event_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    source_utterance TEXT,
    status TEXT NOT NULL CHECK (status = 'OBSERVED'),
    created_at TEXT NOT NULL,
    FOREIGN KEY (shop_id, product_id) REFERENCES products(shop_id, product_id),
    UNIQUE (shop_id, source_event_id)
);

CREATE TABLE IF NOT EXISTS business_events (
    event_id TEXT PRIMARY KEY,
    shop_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    source_event_id TEXT NOT NULL,
    source_channel TEXT NOT NULL CHECK (source_channel IN ('text', 'voice', 'provider_mock', 'system')),
    source_utterance TEXT,
    status TEXT NOT NULL CHECK (status IN ('POSTED', 'OBSERVED')),
    summary TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    UNIQUE (shop_id, source_event_id)
);

CREATE INDEX IF NOT EXISTS ix_business_events_time
    ON business_events(shop_id, created_at DESC);

CREATE TRIGGER IF NOT EXISTS business_events_no_update
BEFORE UPDATE ON business_events
BEGIN
    SELECT RAISE(ABORT, 'business events are append-only');
END;

CREATE TRIGGER IF NOT EXISTS business_events_no_delete
BEFORE DELETE ON business_events
BEGIN
    SELECT RAISE(ABORT, 'business events are append-only');
END;

CREATE TABLE IF NOT EXISTS synthetic_transactions (
    transaction_id TEXT PRIMARY KEY,
    shop_id TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    amount_paise INTEGER NOT NULL CHECK (amount_paise > 0),
    status TEXT NOT NULL CHECK (status IN ('SUCCESS', 'PENDING', 'FAILED', 'REVERSED')),
    payer_token TEXT,
    source TEXT NOT NULL CHECK (source = 'synthetic'),
    UNIQUE (shop_id, transaction_id)
);

CREATE INDEX IF NOT EXISTS ix_synthetic_tx_shop_time
    ON synthetic_transactions(shop_id, occurred_at);

CREATE TABLE IF NOT EXISTS mock_actions (
    action_id TEXT PRIMARY KEY,
    shop_id TEXT NOT NULL,
    persona TEXT NOT NULL CHECK (persona IN ('kirana', 'tea_stall', 'medical_store')),
    action_type TEXT NOT NULL CHECK (action_type IN ('counter_notice', 'qr_offer_mock')),
    action_text TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status = 'APPROVED_MOCK'),
    baseline_start TEXT NOT NULL,
    baseline_end TEXT NOT NULL,
    baseline_collections_paise INTEGER NOT NULL CHECK (baseline_collections_paise >= 0),
    baseline_transaction_count INTEGER NOT NULL CHECK (baseline_transaction_count >= 0),
    measurement_start TEXT NOT NULL,
    measurement_end TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    UNIQUE (shop_id, action_id)
);

CREATE INDEX IF NOT EXISTS ix_mock_actions_shop_created
    ON mock_actions(shop_id, created_at DESC);

CREATE TRIGGER IF NOT EXISTS mock_actions_no_update
BEFORE UPDATE ON mock_actions
BEGIN
    SELECT RAISE(ABORT, 'mock actions are append-only');
END;

CREATE TRIGGER IF NOT EXISTS mock_actions_no_delete
BEFORE DELETE ON mock_actions
BEGIN
    SELECT RAISE(ABORT, 'mock actions are append-only');
END;

CREATE TABLE IF NOT EXISTS payer_customer_mappings (
    mapping_id TEXT PRIMARY KEY,
    shop_id TEXT NOT NULL,
    payer_token TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    UNIQUE (shop_id, payer_token),
    FOREIGN KEY (shop_id, customer_id) REFERENCES customers(shop_id, customer_id)
);

CREATE TRIGGER IF NOT EXISTS payer_mappings_no_update
BEFORE UPDATE ON payer_customer_mappings
BEGIN
    SELECT RAISE(ABORT, 'payer mappings are append-only');
END;

CREATE TRIGGER IF NOT EXISTS payer_mappings_no_delete
BEFORE DELETE ON payer_customer_mappings
BEGIN
    SELECT RAISE(ABORT, 'payer mappings are append-only');
END;

CREATE TABLE IF NOT EXISTS payment_events (
    event_id TEXT PRIMARY KEY,
    shop_id TEXT NOT NULL,
    amount_paise INTEGER NOT NULL CHECK (amount_paise > 0),
    payment_status TEXT NOT NULL CHECK (payment_status IN ('SUCCESS', 'PENDING', 'FAILED', 'REVERSED')),
    occurred_at TEXT NOT NULL,
    payer_token TEXT,
    source TEXT NOT NULL CHECK (source = 'provider_mock'),
    idempotency_key TEXT NOT NULL UNIQUE,
    resolution_status TEXT NOT NULL CHECK (resolution_status IN ('ALLOCATED', 'REVIEW', 'UNMATCHED', 'IGNORED')),
    resolution_reason TEXT,
    allocation_entry_id TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (shop_id, event_id)
);

CREATE INDEX IF NOT EXISTS ix_payment_review_queue
    ON payment_events(shop_id, resolution_status, created_at DESC);

CREATE TRIGGER IF NOT EXISTS payment_events_no_update
BEFORE UPDATE ON payment_events
BEGIN
    SELECT RAISE(ABORT, 'payment events are append-only');
END;

CREATE TRIGGER IF NOT EXISTS payment_events_no_delete
BEFORE DELETE ON payment_events
BEGIN
    SELECT RAISE(ABORT, 'payment events are append-only');
END;

CREATE TABLE IF NOT EXISTS payment_resolutions (
    resolution_id TEXT PRIMARY KEY,
    shop_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    amount_paise INTEGER NOT NULL CHECK (amount_paise > 0),
    allocation_entry_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    UNIQUE (shop_id, event_id),
    FOREIGN KEY (shop_id, event_id) REFERENCES payment_events(shop_id, event_id),
    FOREIGN KEY (shop_id, customer_id) REFERENCES customers(shop_id, customer_id)
);

CREATE TRIGGER IF NOT EXISTS payment_resolutions_no_update
BEFORE UPDATE ON payment_resolutions
BEGIN
    SELECT RAISE(ABORT, 'payment resolutions are append-only');
END;

CREATE TRIGGER IF NOT EXISTS payment_resolutions_no_delete
BEFORE DELETE ON payment_resolutions
BEGIN
    SELECT RAISE(ABORT, 'payment resolutions are append-only');
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
    """Create or upgrade the demo schema through versioned, additive migrations."""
    from app.services.migrations import run_migrations

    with connect() as connection:
        run_migrations(connection)


