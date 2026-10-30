import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.services import receipts
from tests.conftest import key, table_count


@pytest.fixture
def shop(make_product, make_supplier):
    return {
        "amul": make_product("Amul Taaza", "packet"),
        "dahi": make_product("Dahi", "cup"),
        "supplier": make_supplier("Sharma Distributors"),
    }


def manual(client, shop, number="INV-204", total=113000, lines=None, supplier=True, **invoice):
    body = {
        "supplier": {"supplier_id": shop["supplier"]["supplier_id"]} if supplier else {},
        "invoice": {"invoice_number": number, "total_paise": total, **invoice},
        "lines": lines or [
            {"product_id": shop["amul"]["product_id"], "quantity": 15, "unit_text": "packet",
             "unit_cost_paise": 4200, "line_total_paise": 63000},
            {"product_id": shop["dahi"]["product_id"], "quantity": 20, "unit_text": "cups",
             "unit_cost_paise": 2500, "line_total_paise": 50000},
        ],
        "idempotency_key": key("manual"),
    }
    response = client.post("/invoices/proposals/manual", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def confirm(client, view, paid_now=0, idem=None, **extra):
    return client.post(f"/invoices/proposals/{view['proposal_id']}/confirm", json={
        "expected_version": view["version"], "content_hash": view["content_hash"], "paid_now_paise": paid_now,
        "confirmed": True, "idempotency_key": idem or key("confirm"), **extra,
    })


def stock(client, product):
    return client.get(f"/inventory/products/{product['product_id']}/stock").json()["on_hand_quantity"]


def due(client, shop):
    return client.get(f"/suppliers/{shop['supplier']['supplier_id']}/balance").json()["amount_due_paise"]


def products_snapshot(path):
    with sqlite3.connect(path) as connection:
        return connection.execute("SELECT * FROM products ORDER BY product_id").fetchall()


def test_confirm_posts_once(client, shop, temp_db):
    view = manual(client, shop)
    assert view["status"] == "READY", view["issues"]
    before_products = products_snapshot(temp_db)
    first = confirm(client, view, paid_now=30000, idem="confirm-key-0001")
    assert first.status_code == 201, first.text
    receipt = first.json()
    assert receipt["payable_status"] == "POSTED" and receipt["retail_price_changed"] is False
    assert receipt["supplier_due_before_paise"] == 0 and receipt["supplier_due_after_paise"] == 83000
    assert [(l["on_hand_before"], l["on_hand_after"]) for l in receipt["lines"]] == [(0, 15), (0, 20)]
    assert stock(client, shop["amul"]) == 15 and stock(client, shop["dahi"]) == 20
    assert due(client, shop) == 83000

    replay = confirm(client, view, paid_now=30000, idem="confirm-key-0001")
    assert replay.status_code == 201 and replay.json()["idempotent_replay"] is True
    assert replay.json()["receipt_id"] == receipt["receipt_id"]
    assert stock(client, shop["amul"]) == 15 and due(client, shop) == 83000
    assert table_count(temp_db, "stock_receipt_movements") == 2
    assert table_count(temp_db, "supplier_payable_entries") == 1
    assert products_snapshot(temp_db) == before_products  # wholesale cost never touches products

    other_key = confirm(client, view, paid_now=30000)
    assert other_key.status_code == 409 and other_key.json()["detail"]["code"] == "PROPOSAL_ALREADY_CONFIRMED"
    assert client.get(f"/invoices/proposals/{view['proposal_id']}").json()["status"] == "CONFIRMED"
    events = [e["event_type"] for e in client.get("/events").json()]
    assert events.count("STOCK_RECEIPT_POSTED") == 1 and events.count("SUPPLIER_INVOICE_CREDIT_POSTED") == 1
    assert client.get(f"/receipts/{receipt['receipt_id']}").json()["lines"][0]["on_hand_after"] == 15


def test_paid_now_rules(client, shop):
    view = manual(client, shop)
    missing = confirm(client, view, paid_now=None)
    assert missing.status_code == 422 and missing.json()["detail"]["code"] == "PAID_NOW_REQUIRED"
    assert confirm(client, view, paid_now=113001).status_code == 422
    full = confirm(client, view, paid_now=113000)
    assert full.status_code == 201 and full.json()["payable_status"] == "FULLY_PAID_NOW"
    assert due(client, shop) == 0


def test_supplier_required_unless_paid_in_full(client, shop):
    view = manual(client, shop, supplier=False)
    blocked = confirm(client, view, paid_now=0)
    assert blocked.status_code == 409 and blocked.json()["detail"]["code"] == "SUPPLIER_REQUIRED_FOR_PAYABLE"
    assert confirm(client, view, paid_now=113000).status_code == 201


def test_unconfirmed_is_rejected(client, shop, temp_db):
    view = manual(client, shop)
    assert confirm(client, view, confirmed=False).status_code == 409
    assert table_count(temp_db, "stock_receipts") == 0


def test_stale_confirmation_rejected(client, shop, temp_db):
    view = manual(client, shop)
    revised = client.post(f"/invoices/proposals/{view['proposal_id']}/revise", json={
        "expected_version": 1, "supplier": {"supplier_id": shop["supplier"]["supplier_id"]},
        "invoice": {"invoice_number": "INV-204", "total_paise": 999900},
        "lines": [{"product_id": shop["amul"]["product_id"], "quantity": 15, "unit_text": "packet"}],
    }).json()
    stale = confirm(client, view)  # quotes version 1 / old hash
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "STALE_PROPOSAL"
    forged = confirm(client, {**revised, "content_hash": view["content_hash"]})
    assert forged.status_code == 409
    assert table_count(temp_db, "stock_receipts") == 0
    assert confirm(client, revised).status_code == 201


def test_rollback_on_failure(shop, temp_db, monkeypatch):
    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    view = manual(client, shop)

    def explode(*args, **kwargs):
        raise RuntimeError("injected failure after movements and payable")

    with monkeypatch.context() as patch:
        patch.setattr(receipts.events_service, "append_event", explode)
        assert confirm(client, view).status_code == 500
    for table in ("stock_receipts", "stock_receipt_movements", "supplier_payable_entries"):
        assert table_count(temp_db, table) == 0
    assert stock(client, shop["amul"]) == 0 and due(client, shop) == 0
    assert client.get(f"/invoices/proposals/{view['proposal_id']}").json()["status"] == "READY"
    assert confirm(client, view).status_code == 201
    assert stock(client, shop["amul"]) == 15


def test_duplicate_invoice_blocked(client, shop):
    assert confirm(client, manual(client, shop, number="INV-204")).status_code == 201
    same = manual(client, shop, number="inv 204")
    assert "DUPLICATE_INVOICE_ALREADY_POSTED" in {i["code"] for i in same["issues"]}
    assert confirm(client, same).json()["detail"]["code"] == "PROPOSAL_NOT_READY"
    conflicting = manual(client, shop, number="INV-204", total=120000)
    assert "DUPLICATE_INVOICE_CONFLICT" in {i["code"] for i in conflicting["issues"]}
    assert due(client, shop) == 113000


def test_warnings_need_acknowledgement(client, shop):
    view = manual(client, shop, lines=[{"product_id": shop["amul"]["product_id"], "quantity": 15, "unit_text": "packet",
                                        "unit_cost_paise": 4200, "line_total_paise": 70000}], total=70000)
    assert view["status"] == "READY" and view["warnings_require_acknowledgement"]
    blocked = confirm(client, view)
    assert blocked.status_code == 409 and blocked.json()["detail"]["code"] == "WARNINGS_NOT_ACKNOWLEDGED"
    assert confirm(client, view, acknowledge_warnings=True).status_code == 201


def test_case_needs_known_conversion(client, shop):
    lines = [{"product_id": shop["amul"]["product_id"], "quantity": 2, "unit_text": "case"}]
    view = manual(client, shop, lines=lines, total=None)
    assert "UNIT_CONVERSION_UNKNOWN" in {i["code"] for i in view["lines"][0]["issues"]}
    saved = client.post(f"/products/{shop['amul']['product_id']}/unit-conversions", json={
        "unit": "cases", "base_units_per_unit": 24, "confirmed": True, "idempotency_key": key("conv"),
    })
    assert saved.status_code == 201 and saved.json()["unit"] == "case"
    refreshed = client.get(f"/invoices/proposals/{view['proposal_id']}").json()
    assert refreshed["lines"][0]["base_quantity"] == 48 and refreshed["status"] == "READY"
    receipt = confirm(client, refreshed, paid_now=None).json()
    assert receipt["payable_status"] == "NOT_SUPPLIED" and stock(client, shop["amul"]) == 48


def test_physical_count_reconciles_with_receipts(client, shop):
    confirm(client, manual(client, shop, total=None), paid_now=None)
    count = client.post("/inventory/counts", json={
        "product_id": shop["amul"]["product_id"], "counted_quantity": 10, "source_event_id": "count-1",
        "idempotency_key": key("count"), "confirmed": True,
    }).json()
    assert count["quantity_delta"] == -5
    assert stock(client, shop["amul"]) == 10


def test_rejected_proposal_cannot_post(client, shop, temp_db):
    view = manual(client, shop)
    rejected = client.post(f"/invoices/proposals/{view['proposal_id']}/reject", json={"expected_version": 1, "confirmed": True})
    assert rejected.json()["status"] == "REJECTED"
    assert confirm(client, view).status_code == 409
    assert table_count(temp_db, "stock_receipts") == 0
