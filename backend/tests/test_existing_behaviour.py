"""Pre-existing endpoints keep their behaviour after the new phases."""

from tests.conftest import key


def test_health_and_command_fallback(client):
    assert client.get("/health").json()["status"] == "ok"
    response = client.post("/commands/interpret", json={"utterance": "what does Raju owe?"}).json()
    assert response["status"] == "unavailable" and response["fallback_used"] is True


def test_customer_ledger_flow_unchanged(client, make_customer):
    cid = make_customer("Raju bhai", ["Raju"])["customer_id"]
    assert client.get("/customers/resolve", params={"query": "raju"}).json()["status"] == "RESOLVED"
    body = {"customer_id": cid, "amount_paise": 50000, "source_event_id": "c1", "idempotency_key": "credit-key-001", "confirmed": True}
    assert client.post("/ledger/credits", json=body).status_code == 201
    assert client.post("/ledger/credits", json=body).json()["idempotent_replay"] is True
    over = client.post("/ledger/repayments", json={**body, "amount_paise": 60000, "source_event_id": "r1", "idempotency_key": key()})
    assert over.json()["detail"]["code"] == "REPAYMENT_EXCEEDS_BALANCE"
    client.post("/ledger/repayments", json={**body, "amount_paise": 20000, "source_event_id": "r2", "idempotency_key": key()})
    assert client.get(f"/ledger/customers/{cid}/balance").json()["balance_due_paise"] == 30000


def test_inventory_and_stockout_unchanged(client, make_product):
    pid = make_product("Maggi", "pack")["product_id"]
    count = {"product_id": pid, "counted_quantity": 12, "source_event_id": "s1", "idempotency_key": key(), "confirmed": True}
    assert client.post("/inventory/counts", json=count).json()["quantity_delta"] == 12
    observed = client.post("/inventory/stockout-observations", json={
        "product_id": pid, "source_event_id": "o1", "idempotency_key": key(), "confirmed": True})
    assert observed.status_code == 201
    assert client.get(f"/inventory/products/{pid}/stock").json()["on_hand_quantity"] == 12


def test_payment_review_unchanged(client, make_customer):
    cid = make_customer("Raju bhai")["customer_id"]
    client.post("/ledger/credits", json={"customer_id": cid, "amount_paise": 50000, "source_event_id": "c1",
                                         "idempotency_key": key(), "confirmed": True})
    intake = client.post("/payments/intake", json={
        "event_id": "pay_1", "amount_paise": 30000, "status": "SUCCESS", "occurred_at": "2026-10-30T10:00:00+05:30",
        "idempotency_key": key(), "source": "provider_mock"}).json()
    assert intake["resolution_status"] in {"REVIEW", "UNMATCHED"}
    allocated = client.post("/payments/pay_1/allocate", json={"customer_id": cid, "confirmed": True, "idempotency_key": key()})
    assert allocated.status_code == 200
    assert client.get(f"/ledger/customers/{cid}/balance").json()["balance_due_paise"] == 20000
    summary = client.get("/events/summary").json()
    assert summary["repayment_entry_count"] == 1
