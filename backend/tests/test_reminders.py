import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.services import reminders
from tests.conftest import key, table_count

T0 = datetime(2026, 10, 1, 6, 0, tzinfo=timezone.utc)  # 11:30 IST
PHONE = "+91 98765 43210"


def ledger_row(path, customer_id, entry_type, amount, when):
    entry_id = f"entry_{uuid.uuid4().hex[:12]}"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """INSERT INTO ledger_entries (entry_id, shop_id, customer_id, entry_type, amount_paise, source_event_id,
               idempotency_key, status, created_at) VALUES (?, 'shop_synth_01', ?, ?, ?, ?, ?, 'POSTED', ?)""",
            (entry_id, customer_id, entry_type, amount, f"src-{entry_id}", f"key-{entry_id}", when.isoformat()),
        )
    return entry_id


def at(monkeypatch, moment):
    monkeypatch.setattr(reminders, "now_utc", lambda: moment)
    return moment


def consent(client, customer_id, status="OPTED_IN", verified=True, channel="whatsapp", idem=None):
    body = {"channel": channel, "consent_status": status, "contact_value": PHONE if status == "OPTED_IN" else None,
            "contact_verified": verified, "verification_method": "Customer read number back at counter" if verified else None,
            "evidence_note": "Customer agreed at counter to receive balance reminders", "confirmed": True,
            "idempotency_key": idem or key("consent")}
    response = client.post(f"/customers/{customer_id}/reminder-consent", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def run(client, moment):
    response = client.post("/reminders/eligibility/run", params={"as_of": moment.isoformat()})
    assert response.status_code == 200, response.text
    return response.json()


def preview_row(client, moment, customer_id):
    rows = client.get("/reminders/eligibility/preview", params={"as_of": moment.isoformat()}).json()["rows"]
    return next(row for row in rows if row["customer_id"] == customer_id)


def action(client, reminder_id, verb, **body):
    return client.post(f"/reminders/{reminder_id}/{verb}", json={"confirmed": True, "idempotency_key": key(verb), **body})


@pytest.fixture
def raju(make_customer, client, temp_db):
    customer = make_customer("Raju bhai")
    consent(client, customer["customer_id"])
    ledger_row(temp_db, customer["customer_id"], "CREDIT", 50000, T0)
    return customer


def test_due_under_threshold_not_eligible_then_eligible_once(client, raju, monkeypatch):
    day14 = at(monkeypatch, T0 + timedelta(days=14))
    row = preview_row(client, day14, raju["customer_id"])
    assert row["overdue_days"] == 14 and row["eligible"] is False and row["reasons"] == ["NOT_YET_OVERDUE"]
    assert run(client, day14)["created"] == []

    day15 = at(monkeypatch, T0 + timedelta(days=15))
    first = run(client, day15)
    assert len(first["created"]) == 1
    reminder = first["created"][0]
    assert reminder["status"] == "PENDING_APPROVAL" and reminder["overdue_days_at_eligibility"] == 15
    assert reminder["mock_only"] is True and reminder["delivered_to_real_recipient"] is False
    assert "₹" not in reminder["message_preview"]  # amount omitted by default
    again = run(client, day15)
    assert again["created"] == [] and again["skipped_by_reason"].get("REMINDER_ALREADY_ACTIVE") == 1
    assert len(client.get("/reminders").json()) == 1


def test_shop_timezone_day_boundary(client, make_customer, temp_db, monkeypatch):
    customer = make_customer("Meena")
    consent(client, customer["customer_id"])
    ledger_row(temp_db, customer["customer_id"], "CREDIT", 10000, datetime(2026, 10, 1, 20, 0, tzinfo=timezone.utc))  # 2 Oct IST
    late_16th_ist = at(monkeypatch, datetime(2026, 10, 16, 18, 0, tzinfo=timezone.utc))  # 16 Oct 23:30 IST
    assert preview_row(client, late_16th_ist, customer["customer_id"])["overdue_days"] == 14
    early_17th_ist = at(monkeypatch, datetime(2026, 10, 16, 19, 0, tzinfo=timezone.utc))  # 17 Oct 00:30 IST
    row = preview_row(client, early_17th_ist, customer["customer_id"])
    assert row["oldest_unpaid_local_date"] == "2026-10-02" and row["overdue_days"] == 15 and row["eligible"]


def test_fifo_partial_repayments(client, make_customer, temp_db, monkeypatch):
    customer = make_customer("Asha")
    cid = customer["customer_id"]
    consent(client, cid)
    old = ledger_row(temp_db, cid, "CREDIT", 50000, T0)
    newer = ledger_row(temp_db, cid, "CREDIT", 30000, T0 + timedelta(days=9))
    ledger_row(temp_db, cid, "REPAYMENT", 30000, T0 + timedelta(days=10))
    moment = at(monkeypatch, T0 + timedelta(days=20))
    row = preview_row(client, moment, cid)
    # Partial repayment reduces the oldest credit; the remainder keeps its original age.
    assert [(c["entry_id"], c["remaining_paise"]) for c in row["open_credits"]] == [(old, 20000), (newer, 30000)]
    assert row["overdue_days"] == 20 and row["eligible"]

    ledger_row(temp_db, cid, "REPAYMENT", 20000, T0 + timedelta(days=11))  # oldest credit now fully settled
    row = preview_row(client, moment, cid)
    assert [(c["entry_id"], c["remaining_paise"]) for c in row["open_credits"]] == [(newer, 30000)]
    assert row["overdue_days"] == 11 and row["reasons"] == ["NOT_YET_OVERDUE"]
    assert row["balance_due_paise"] == 30000


def test_full_repayment_cancels_pending_reminder(client, raju, monkeypatch):
    at(monkeypatch, T0 + timedelta(days=16))
    reminder = run(client, T0 + timedelta(days=16))["created"][0]
    partial = client.post("/ledger/repayments", json={"customer_id": raju["customer_id"], "amount_paise": 10000,
                                                      "source_event_id": "r1", "idempotency_key": key("rep"), "confirmed": True})
    assert partial.status_code == 201
    assert client.get(f"/reminders/{reminder['reminder_id']}").json()["status"] == "PENDING_APPROVAL"
    client.post("/ledger/repayments", json={"customer_id": raju["customer_id"], "amount_paise": 40000,
                                            "source_event_id": "r2", "idempotency_key": key("rep"), "confirmed": True})
    view = client.get(f"/reminders/{reminder['reminder_id']}").json()
    assert view["status"] == "CANCELLED" and view["transitions"][-1]["reason"] == "Balance fully repaid."
    assert action(client, reminder["reminder_id"], "approve").status_code == 409


def test_consent_rules_block_contact(client, make_customer, temp_db, monkeypatch):
    moment = at(monkeypatch, T0 + timedelta(days=30))
    none = make_customer("No Consent")
    unverified = make_customer("Unverified")
    opted_out = make_customer("Opted Out")
    for customer in (none, unverified, opted_out):
        ledger_row(temp_db, customer["customer_id"], "CREDIT", 10000, T0)
    consent(client, unverified["customer_id"], verified=False)
    consent(client, opted_out["customer_id"])
    consent(client, opted_out["customer_id"], status="OPTED_OUT")
    reasons = {row["display_name"]: row["reasons"] for row in client.get(
        "/reminders/eligibility/preview", params={"as_of": moment.isoformat()}).json()["rows"]}
    assert reasons == {"No Consent": ["NO_CONSENT_RECORDED"], "Unverified": ["CONTACT_NOT_VERIFIED"], "Opted Out": ["OPTED_OUT"]}
    assert run(client, moment)["created"] == []
    assert table_count(temp_db, "reminders") == 0


def test_opt_out_after_eligibility_blocks_send(client, raju, monkeypatch):
    moment = at(monkeypatch, T0 + timedelta(days=16))
    reminder = run(client, moment)["created"][0]
    assert action(client, reminder["reminder_id"], "approve").status_code == 200
    consent(client, raju["customer_id"], status="OPTED_OUT")
    assert client.get(f"/reminders/{reminder['reminder_id']}").json()["status"] == "BLOCKED_OPTED_OUT"
    assert action(client, reminder["reminder_id"], "mock-send").status_code == 409


def test_unverified_or_invalid_contact_rejected(client, make_customer):
    cid = make_customer("Test")["customer_id"]
    bad = client.post(f"/customers/{cid}/reminder-consent", json={
        "channel": "sms", "consent_status": "OPTED_IN", "contact_value": "12345", "contact_verified": True,
        "verification_method": "x", "evidence_note": "said yes", "confirmed": True, "idempotency_key": key()})
    assert bad.status_code == 422
    missing_method = client.post(f"/customers/{cid}/reminder-consent", json={
        "channel": "sms", "consent_status": "OPTED_IN", "contact_value": PHONE, "contact_verified": True,
        "evidence_note": "said yes", "confirmed": True, "idempotency_key": key()})
    assert missing_method.status_code == 422


def test_full_mock_flow_and_audit(client, raju, monkeypatch):
    moment = at(monkeypatch, T0 + timedelta(days=16))
    reminder = run(client, moment)["created"][0]
    rid = reminder["reminder_id"]
    assert action(client, rid, "mock-send").json()["detail"]["code"] == "NOT_APPROVED"
    approve_key = "approve-key-0001"
    approved = client.post(f"/reminders/{rid}/approve", json={"confirmed": True, "include_amount": True, "idempotency_key": approve_key})
    assert approved.status_code == 200
    approved = approved.json()
    assert approved["status"] == "APPROVED_MOCK" and "₹500.00" in approved["message_preview"]
    assert client.post(f"/reminders/{rid}/approve", json={"confirmed": True, "include_amount": True,
                                                           "idempotency_key": approve_key}).json()["status"] == "APPROVED_MOCK"
    send_key = "send-key-00001"
    sent = client.post(f"/reminders/{rid}/mock-send", json={"confirmed": True, "idempotency_key": send_key}).json()
    assert sent["status"] == "SENT_MOCK"
    last = sent["transitions"][-1]
    assert last["provider"] == "mock" and last["provider_message_id"].startswith("mock_")
    replay = client.post(f"/reminders/{rid}/mock-send", json={"confirmed": True, "idempotency_key": send_key}).json()
    assert len(replay["transitions"]) == len(sent["transitions"])
    delivered = client.post(f"/reminders/{rid}/mock-delivery-receipt", json={"outcome": "DELIVERED", "idempotency_key": key()}).json()
    assert delivered["status"] == "DELIVERED_MOCK"
    assert [t["to_status"] for t in delivered["transitions"]] == ["PENDING_APPROVAL", "APPROVED_MOCK", "SENT_MOCK", "DELIVERED_MOCK"]
    events = client.get("/events").json()
    types = {e["event_type"] for e in events}
    assert {"REMINDER_PENDING_APPROVAL", "REMINDER_APPROVED_MOCK", "REMINDER_SENT_MOCK", "REMINDER_DELIVERED_MOCK"} <= types
    assert "98765" not in client.get("/events").text and "98765" not in client.get(f"/reminders/{rid}").text
    assert delivered["contact_masked"] == "********3210"


def test_cancel_by_merchant(client, raju, monkeypatch):
    moment = at(monkeypatch, T0 + timedelta(days=16))
    rid = run(client, moment)["created"][0]["reminder_id"]
    assert action(client, rid, "cancel", reason="Spoke in person").json()["status"] == "CANCELLED"
    assert action(client, rid, "approve").status_code == 409


def test_quiet_hours_block_send(client, raju, monkeypatch):
    moment = at(monkeypatch, T0 + timedelta(days=16))
    rid = run(client, moment)["created"][0]["reminder_id"]
    action(client, rid, "approve")
    at(monkeypatch, datetime(2026, 10, 17, 16, 30, tzinfo=timezone.utc))  # 22:00 IST
    blocked = action(client, rid, "mock-send")
    assert blocked.status_code == 409 and blocked.json()["detail"]["code"] == "QUIET_HOURS"


def test_daily_rate_limit(client, raju, make_customer, temp_db, monkeypatch):
    other = make_customer("Second")
    consent(client, other["customer_id"])
    ledger_row(temp_db, other["customer_id"], "CREDIT", 10000, T0)
    client.post("/reminders/settings", json={"max_mock_sends_per_day": 1, "confirmed": True})
    moment = at(monkeypatch, T0 + timedelta(days=16))
    created = run(client, moment)["created"]
    assert len(created) == 2
    for reminder in created:
        action(client, reminder["reminder_id"], "approve")
    assert action(client, created[0]["reminder_id"], "mock-send").status_code == 200
    limited = action(client, created[1]["reminder_id"], "mock-send")
    assert limited.status_code == 429 and limited.json()["detail"]["code"] == "DAILY_LIMIT"


def test_min_interval_between_reminders(client, raju, monkeypatch):
    moment = at(monkeypatch, T0 + timedelta(days=16))
    rid = run(client, moment)["created"][0]["reminder_id"]
    action(client, rid, "approve")
    action(client, rid, "mock-send")
    client.post(f"/reminders/{rid}/mock-delivery-receipt", json={"outcome": "DELIVERED", "idempotency_key": key()})
    soon = at(monkeypatch, moment + timedelta(days=3))
    assert run(client, soon)["skipped_by_reason"].get("REMINDED_RECENTLY") == 1
    later = at(monkeypatch, moment + timedelta(days=8))
    assert len(run(client, later)["created"]) == 1


def test_no_real_provider_and_admin_guard(client, raju, monkeypatch):
    moment = at(monkeypatch, T0 + timedelta(days=16))
    monkeypatch.setenv("MUNIM_ADMIN_TOKEN", "local-admin-secret")
    assert client.post("/reminders/eligibility/run", params={"as_of": moment.isoformat()}).status_code == 403
    allowed = client.post("/reminders/eligibility/run", params={"as_of": moment.isoformat()},
                          headers={"X-Munim-Admin-Token": "local-admin-secret"})
    rid = allowed.json()["created"][0]["reminder_id"]
    action(client, rid, "approve")
    assert action(client, rid, "mock-send").status_code == 403
    monkeypatch.setenv("MUNIM_NOTIFICATION_PROVIDER", "whatsapp")
    real = client.post(f"/reminders/{rid}/mock-send", json={"confirmed": True, "idempotency_key": key()},
                       headers={"X-Munim-Admin-Token": "local-admin-secret"})
    assert real.status_code == 503
    assert client.get(f"/reminders/{rid}").json()["status"] == "APPROVED_MOCK"


def test_settings_validation(client):
    assert client.get("/reminders/settings").json()["reminder_overdue_days"] == 15
    assert client.post("/reminders/settings", json={"timezone": "Mars/Base", "confirmed": True}).status_code == 422
    assert client.post("/reminders/settings", json={"quiet_hours_start": "25:00", "confirmed": True}).status_code == 422
