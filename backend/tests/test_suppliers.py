import sqlite3

import pytest

from tests.conftest import key, table_count


def _entry(client, supplier_id, amount, idem=None, path="payments", **extra):
    idem = idem or key("pay")
    body = {"amount_paise": amount, "source_event_id": f"src-{idem}", "idempotency_key": idem, "confirmed": True}
    body.update(extra)
    return client.post(f"/suppliers/{supplier_id}/{path}", json=body)


def _increase(client, supplier_id, amount):
    response = _entry(client, supplier_id, amount, path="adjustments",
                      entry_type="ADJUSTMENT_INCREASE", note="Opening balance from notebook")
    assert response.status_code == 201, response.text
    return response.json()


def test_shared_alias_is_ambiguous_and_exact_alias_resolves(client, make_supplier):
    make_supplier("Sharma Distributors", ["Sharma"])
    make_supplier("Sharma Dairy", ["Sharma"])
    ambiguous = client.get("/suppliers/resolve", params={"query": "  sharma "}).json()
    assert ambiguous["status"] == "AMBIGUOUS"
    assert {m["display_name"] for m in ambiguous["matches"]} == {"Sharma Distributors", "Sharma Dairy"}
    assert client.get("/suppliers/resolve", params={"query": "sharma dairy"}).json()["status"] == "RESOLVED"


def test_generic_phrase_is_not_guessed(client, make_supplier):
    make_supplier("Sharma Dairy", ["Sharma"])
    assert client.get("/suppliers/resolve", params={"query": "doodh wale"}).json()["status"] == "NOT_FOUND"


def test_supplier_ledger_separate_from_customers(client, make_supplier, make_customer, temp_db):
    customer = make_customer()
    client.post("/ledger/credits", json={
        "customer_id": customer["customer_id"], "amount_paise": 5000, "source_event_id": "c1",
        "idempotency_key": key("credit"), "confirmed": True,
    })
    supplier = make_supplier("Sharma Distributors")
    _increase(client, supplier["supplier_id"], 147500)
    assert client.get(f"/ledger/customers/{customer['customer_id']}/balance").json()["balance_due_paise"] == 5000
    assert table_count(temp_db, "ledger_entries") == 1
    assert client.get(f"/suppliers/{supplier['supplier_id']}/balance").json()["amount_due_paise"] == 147500
    # A customer ID is not a supplier.
    assert client.get(f"/suppliers/{customer['customer_id']}/balance").status_code == 404


def test_payment_idempotency(client, make_supplier, temp_db):
    sid = make_supplier("Sharma Distributors")["supplier_id"]
    _increase(client, sid, 10000)
    first = _entry(client, sid, 4000, idem="pay-key-0001")
    replay = _entry(client, sid, 4000, idem="pay-key-0001")
    assert first.status_code == 201 and replay.status_code == 201
    assert replay.json()["idempotent_replay"] is True
    assert replay.json()["entry_id"] == first.json()["entry_id"]
    assert _entry(client, sid, 4500, idem="pay-key-0001").status_code == 409
    assert table_count(temp_db, "supplier_payable_entries") == 2
    assert client.get(f"/suppliers/{sid}/balance").json()["amount_due_paise"] == 6000


def test_unconfirmed_and_overpayment_rejected(client, make_supplier, temp_db):
    sid = make_supplier("Sharma Distributors")["supplier_id"]
    _increase(client, sid, 1000)
    assert _entry(client, sid, 500, confirmed=False).status_code == 409
    over = _entry(client, sid, 1001)
    assert over.status_code == 409
    assert over.json()["detail"]["code"] == "SUPPLIER_DECREASE_EXCEEDS_DUE"
    assert _entry(client, sid, "500").status_code == 422  # strict integer paise
    assert table_count(temp_db, "supplier_payable_entries") == 1


def test_balance_derived_and_append_only(client, make_supplier, temp_db):
    sid = make_supplier("Sharma Distributors")["supplier_id"]
    _increase(client, sid, 20000)
    _entry(client, sid, 5000)
    debit = _entry(client, sid, 2500, path="adjustments", entry_type="DEBIT_NOTE", note="2 damaged crates returned")
    assert debit.status_code == 201
    balance = client.get(f"/suppliers/{sid}/balance").json()
    assert balance["amount_due_paise"] == 12500
    assert balance["totals_by_type_paise"] == {"ADJUSTMENT_INCREASE": 20000, "PAYMENT": 5000, "DEBIT_NOTE": 2500}
    entries = client.get(f"/suppliers/{sid}/entries").json()
    assert len(entries) == 3 and {e["direction"] for e in entries} == {"INCREASES_DUE", "DECREASES_DUE"}
    with sqlite3.connect(temp_db) as connection, pytest.raises(sqlite3.IntegrityError):
        connection.execute("UPDATE supplier_payable_entries SET amount_paise = 1")
    with sqlite3.connect(temp_db) as connection, pytest.raises(sqlite3.IntegrityError):
        connection.execute("DELETE FROM supplier_payable_entries")


def test_contact_phone_is_masked(client, make_supplier):
    supplier = make_supplier("Sharma Distributors", contact_phone="+91 90000 01234")
    assert supplier["contact_phone_masked"] == "********1234"
    assert "90000" not in client.get("/suppliers").text
    assert "90000" not in client.get("/events").text


def test_supplier_create_idempotent(client):
    body = {"display_name": "Sharma Dairy", "aliases": ["Sharma"], "confirmed": True, "idempotency_key": "sup-create-0001"}
    first = client.post("/suppliers", json=body).json()
    assert client.post("/suppliers", json=body).json()["supplier_id"] == first["supplier_id"]
    assert client.post("/suppliers", json={**body, "display_name": "Other"}).status_code == 409
