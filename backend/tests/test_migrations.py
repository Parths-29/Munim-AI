"""A database created by the pre-versioning schema upgrades in place without rewriting rows."""

import sqlite3

from app.services import database
from app.services.migrations import MIGRATIONS


def legacy_db(path):
    with sqlite3.connect(path) as connection:
        connection.executescript(database.SCHEMA)  # the original v0 script, unchanged
        connection.executescript("""
            INSERT INTO customers VALUES ('cust_legacy', 'shop_synth_01', 'Raju bhai', 'legacy-cust', '2026-10-01T00:00:00+00:00');
            INSERT INTO customer_aliases VALUES ('a1', 'shop_synth_01', 'cust_legacy', 'Raju', 'raju');
            INSERT INTO ledger_entries VALUES ('e1', 'shop_synth_01', 'cust_legacy', 'CREDIT', 50000, 's1', 'k1', 'POSTED', '2026-10-01T00:00:00+00:00');
            INSERT INTO products VALUES ('p1', 'shop_synth_01', 'Maggi', 'pack', 'legacy-prod', '2026-10-01T00:00:00+00:00');
            INSERT INTO inventory_movements VALUES ('m1', 'shop_synth_01', 'p1', 12, 12, 'pack', 'PHYSICAL_COUNT', 's2', 'k2', 'POSTED', '2026-10-01T00:00:00+00:00');
        """)


def dump(path, tables):
    with sqlite3.connect(path) as connection:
        return {table: connection.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall() for table in tables}


def test_legacy_database_upgrades_in_place(tmp_path, monkeypatch, client):
    path = tmp_path / "legacy.sqlite3"
    legacy_db(path)
    legacy_tables = ["customers", "customer_aliases", "ledger_entries", "products", "inventory_movements"]
    before = dump(path, legacy_tables)
    monkeypatch.setattr(database, "DB_PATH", path)

    database.initialize_database()
    database.initialize_database()  # second run is a no-op

    with sqlite3.connect(path) as connection:
        versions = [row[0] for row in connection.execute("SELECT version FROM schema_migrations ORDER BY version")]
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert versions == [version for version, _, _ in MIGRATIONS]
    assert {"suppliers", "stock_receipts", "reminders", "reminder_transitions"} <= tables
    assert dump(path, legacy_tables) == before

    assert client.get("/ledger/customers/cust_legacy/balance").json()["balance_due_paise"] == 50000
    assert client.get("/inventory/products/p1/stock").json()["on_hand_quantity"] == 12


def test_failed_migration_rolls_back(tmp_path, monkeypatch):
    from app.services import migrations

    path = tmp_path / "broken.sqlite3"
    monkeypatch.setattr(database, "DB_PATH", path)
    broken = migrations.MIGRATIONS + [(99, "broken", "CREATE TABLE half_done (x INTEGER); SELECT * FROM missing_table;")]
    monkeypatch.setattr(migrations, "MIGRATIONS", broken)
    try:
        database.initialize_database()
    except sqlite3.OperationalError:
        pass
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 4
        assert connection.execute("SELECT name FROM sqlite_master WHERE name = 'half_done'").fetchone() is None
