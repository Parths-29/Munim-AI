import sqlite3

from app.services.catalog_seed import CATALOGS, seed_catalog
from tests.conftest import key, table_count


def count(client, product_id, quantity):
    response = client.post("/inventory/counts", json={"product_id": product_id, "counted_quantity": quantity,
                                                      "source_event_id": key("src"), "idempotency_key": key(), "confirmed": True})
    assert response.status_code == 201, response.text


def profile(client, product_id, **fields):
    response = client.post(f"/products/{product_id}/profile", json={"confirmed": True, "idempotency_key": key(), **fields})
    assert response.status_code == 200, response.text
    return response.json()


def outflow(client, lines, reason="SALE", idem=None):
    return client.post("/inventory/outflows", json={"reason": reason, "lines": lines, "confirmed": True,
                                                    "idempotency_key": idem or key("out"), "source_channel": "voice",
                                                    "source_utterance": "5 Maggi aur 2 Parle-G bike"})


def test_multi_line_sale_updates_stock_and_uses_selling_price(client, make_product, temp_db):
    maggi = make_product("Maggi", "pack")
    parle = make_product("Parle-G", "packet")
    count(client, maggi["product_id"], 20)
    count(client, parle["product_id"], 10)
    profile(client, maggi["product_id"], category="Snacks", retail_price_paise=1400, reorder_level=16)
    first = outflow(client, [{"product_id": maggi["product_id"], "quantity": 5},
                             {"product_id": parle["product_id"], "quantity": 2, "unit_price_paise": 1000}], idem="sale-key-0001")
    assert first.status_code == 201, first.text
    batch = first.json()
    assert batch["total_amount_paise"] == 5 * 1400 + 2 * 1000
    m, p = batch["lines"]
    assert (m["on_hand_before"], m["on_hand_after"], m["low_stock_after"]) == (20, 15, True)
    assert (p["on_hand_before"], p["on_hand_after"]) == (10, 8)
    replay = outflow(client, [{"product_id": maggi["product_id"], "quantity": 5},
                              {"product_id": parle["product_id"], "quantity": 2, "unit_price_paise": 1000}], idem="sale-key-0001")
    assert replay.json()["idempotent_replay"] is True
    assert client.get(f"/inventory/products/{maggi['product_id']}/stock").json()["on_hand_quantity"] == 15
    assert table_count(temp_db, "stock_outflow_movements") == 2


def test_insufficient_recorded_stock_rejected_atomically(client, make_product, temp_db):
    maggi = make_product("Maggi", "pack")
    tea = make_product("Tata Tea", "packet")
    count(client, maggi["product_id"], 3)
    count(client, tea["product_id"], 10)
    response = outflow(client, [{"product_id": tea["product_id"], "quantity": 2}, {"product_id": maggi["product_id"], "quantity": 5}])
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "INSUFFICIENT_RECORDED_STOCK" and detail["recorded_on_hand"] == 3
    assert table_count(temp_db, "stock_outflow_movements") == 0  # the valid tea line was not written either


def test_wastage_and_case_conversion(client, make_product):
    milk = make_product("Doodh", "packet")
    count(client, milk["product_id"], 50)
    assert outflow(client, [{"product_id": milk["product_id"], "quantity": 1, "unit_text": "crate"}]).status_code == 422
    client.post(f"/products/{milk['product_id']}/unit-conversions", json={"unit": "crate", "base_units_per_unit": 24,
                                                                          "confirmed": True, "idempotency_key": key()})
    sold = outflow(client, [{"product_id": milk["product_id"], "quantity": 1, "unit_text": "crate"}]).json()
    assert sold["lines"][0]["quantity_delta"] == -24
    wasted = outflow(client, [{"product_id": milk["product_id"], "quantity": 2}], reason="WASTAGE").json()
    assert wasted["reason"] == "WASTAGE" and wasted["total_amount_paise"] is None
    history = client.get(f"/inventory/products/{milk['product_id']}/history").json()
    assert [m["kind"] for m in history["movements"]][:2] == ["WASTAGE", "SALE"] and history["on_hand_quantity"] == 24


def test_profile_is_merchant_owned_and_receipts_do_not_change_price(client, make_product, make_supplier):
    maggi = make_product("Maggi", "pack")
    profile(client, maggi["product_id"], retail_price_paise=1400)
    supplier = make_supplier("Sharma Distributors")
    draft = client.post("/invoices/proposals/manual", json={
        "supplier": {"supplier_id": supplier["supplier_id"]}, "invoice": {"total_paise": 24000},
        "lines": [{"product_id": maggi["product_id"], "quantity": 20, "unit_text": "pack", "unit_cost_paise": 1200,
                   "line_total_paise": 24000}], "idempotency_key": key()}).json()
    client.post(f"/invoices/proposals/{draft['proposal_id']}/confirm", json={
        "expected_version": draft["version"], "content_hash": draft["content_hash"], "paid_now_paise": 0,
        "confirmed": True, "idempotency_key": key()})
    assert client.get(f"/products/{maggi['product_id']}/profile").json()["retail_price_paise"] == 1400
    row = next(p for p in client.get("/inventory/overview").json()["products"] if p["product_id"] == maggi["product_id"])
    assert row["last_unit_cost_paise"] == 1200 and row["margin_percent"] == 14.3 and row["stock_value_at_cost_paise"] == 24000


def test_catalog_seed_is_rich_idempotent_and_never_negative(client, temp_db):
    first = seed_catalog("tea_stall")
    again = seed_catalog("tea_stall")
    assert first == again and first["products"] == len(CATALOGS["tea_stall"])
    overview = client.get("/inventory/overview", headers={"X-Munim-Shop": "tea_stall"}).json()
    assert overview["product_count"] == len(CATALOGS["tea_stall"])
    assert all(p["on_hand_quantity"] >= 0 for p in overview["products"])
    assert "Elaichi 50g" in overview["low_stock"] and "Mathri" in overview["slow_movers"]
    assert overview["top_movers"][0] == "Paper Cup"
    suggestions = client.get("/inventory/reorder-suggestions", headers={"X-Munim-Shop": "tea_stall"}).json()
    assert any(s["name"] == "Elaichi 50g" and s["suggested_quantity"] > 0 for s in suggestions)
    assert client.get("/inventory/overview").json()["product_count"] == 0  # kirana shop untouched
    with sqlite3.connect(temp_db) as connection:
        assert connection.execute("SELECT COUNT(*) FROM stock_outflow_movements WHERE shop_id = 'shop_synth_tea'").fetchone()[0] > 100
