"""N8 recovery concierge: due explanation, localized draft, UPI pay link, payment-reference matching (all offline)."""

from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest

from app.services import recovery, reminders
from tests.conftest import key, table_count
from tests.test_reminders import T0, action, at, consent, ledger_row, run

DAY15 = T0 + timedelta(days=15)


def set_profile(client, vpa="rajustore@okaxis", name="Raju General Store"):
    response = client.post("/recovery/payment-profile", json={"upi_vpa": vpa, "payee_name": name, "confirmed": True})
    assert response.status_code == 200, response.text
    return response.json()


def brief(client, customer_id, **params):
    response = client.get(f"/customers/{customer_id}/recovery-brief", params={"as_of": DAY15.isoformat(), **params})
    assert response.status_code == 200, response.text
    return response.json()


def pending_reminder(client, monkeypatch):
    at(monkeypatch, DAY15)
    created = run(client, DAY15)["created"]
    assert len(created) == 1
    return created[0]


def approve(client, reminder_id, **body):
    return client.post(f"/reminders/{reminder_id}/approve",
                       json={"confirmed": True, "idempotency_key": key("approve"), **body})


def pay(client, amount, reference=None, payer_token=None, event_id=None, status="SUCCESS"):
    body = {"event_id": event_id or key("evt"), "amount_paise": amount, "status": status,
            "occurred_at": DAY15.isoformat(), "idempotency_key": key("pay")}
    if reference:
        body["payment_reference"] = reference
    if payer_token:
        body["payer_token"] = payer_token
    response = client.post("/payments/intake", json=body)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def raju(make_customer, client, temp_db):
    customer = make_customer("Raju bhai")
    consent(client, customer["customer_id"])
    ledger_row(temp_db, customer["customer_id"], "CREDIT", 50000, T0)
    return customer


def balance(client, customer_id):
    return client.get(f"/ledger/customers/{customer_id}/balance").json()["balance_due_paise"]


# --- Settings ---------------------------------------------------------------

def test_payment_profile_validation_and_confirmation(client):
    assert client.get("/recovery/payment-profile").status_code == 404
    bad = client.post("/recovery/payment-profile", json={"upi_vpa": "not-a-vpa", "payee_name": "Shop", "confirmed": True})
    assert bad.status_code == 422
    unconfirmed = client.post("/recovery/payment-profile", json={"upi_vpa": "shop@okaxis", "payee_name": "Shop", "confirmed": False})
    assert unconfirmed.status_code == 409
    set_profile(client)
    assert client.get("/recovery/payment-profile").json()["upi_vpa"] == "rajustore@okaxis"


def test_language_preference(client, raju):
    cid = raju["customer_id"]
    assert client.get(f"/customers/{cid}/language").json() == {
        "customer_id": cid, "language_code": "en-IN", "language_name": "English", "is_default": True}
    assert client.post(f"/customers/{cid}/language", json={"language_code": "xx-IN", "confirmed": True}).status_code == 422
    saved = client.post(f"/customers/{cid}/language", json={"language_code": "hi-IN", "confirmed": True}).json()
    assert saved["language_name"] == "Hindi" and saved["is_default"] is False


# --- Brief ------------------------------------------------------------------

def test_brief_explains_due_and_drafts_localized_text_without_writing(client, raju, temp_db):
    cid = raju["customer_id"]
    client.post(f"/customers/{cid}/language", json={"language_code": "hi-IN", "confirmed": True})
    before = {t: table_count(temp_db, t) for t in ("reminders", "collection_requests", "business_events", "ledger_entries")}
    data = brief(client, cid)
    assert {t: table_count(temp_db, t) for t in before} == before  # read-only
    assert data["balance_due_paise"] == 50000 and data["overdue_days"] == 15 and data["eligible"] is True
    assert "owes ₹500.00" in data["explanation"] and "2026-10-01" in data["explanation"] and "15 days ago" in data["explanation"]
    draft = data["draft"]
    assert draft["language_code"] == "hi-IN" and draft["translation_status"] == "TRANSLATED"
    assert draft["text"].startswith("[Hindi] ") and "₹500.00" in draft["text"] and draft["numbers_verified"] is True
    assert data["approve_payload"]["localized_message"] == draft["text"]
    assert data["payment_link"]["available"] is False and data["mock_only"] is True


def test_brief_says_why_not_eligible(client, make_customer, temp_db):
    customer = make_customer("Sharma ji")
    ledger_row(temp_db, customer["customer_id"], "CREDIT", 20000, T0 + timedelta(days=10))
    data = brief(client, customer["customer_id"])
    assert data["eligible"] is False and set(data["reasons"]) == {"NOT_YET_OVERDUE", "NO_CONSENT_RECORDED"}
    assert any("reminders start at 15 days" in text for text in data["reason_explanations"])
    assert any("Ask the customer at the counter" in text for text in data["reason_explanations"])


def test_brief_falls_back_to_english_when_translation_changes_numbers(client, raju, monkeypatch):
    monkeypatch.setenv("MUNIM_SARVAM_MODE", "live")
    monkeypatch.setattr("app.services.sarvam._post", lambda *a, **k: {"translated_text": "राजू भाई, ₹5000 बाकी है"})
    draft = brief(client, raju["customer_id"], language="hi-IN")["draft"]
    assert draft["translation_status"] == "FALLBACK_SOURCE" and draft["text"] == draft["source_text"]
    assert "approve_payload" in brief(client, raju["customer_id"], language="hi-IN")


# --- Approval -----------------------------------------------------------------

def test_approve_localized_message_with_upi_link_then_mock_send(client, raju, monkeypatch, temp_db):
    set_profile(client)
    reminder = pending_reminder(client, monkeypatch)
    text = brief(client, raju["customer_id"], language="hi-IN")["draft"]["text"]
    idem = key("approve")
    body = {"confirmed": True, "idempotency_key": idem, "include_amount": True, "language_code": "hi-IN",
            "localized_message": text, "include_payment_link": True}
    approved = client.post(f"/reminders/{reminder['reminder_id']}/approve", json=body).json()
    assert approved["status"] == "APPROVED_MOCK" and approved["language_code"] == "hi-IN"
    assert approved["message_preview"].startswith("[Hindi] ") and "\nUPI: upi://pay?" in approved["message_preview"]
    reference = approved["payment_reference"]
    query = parse_qs(urlparse(approved["message_preview"].split("UPI: ", 1)[1]).query)
    assert query["pa"] == ["rajustore@okaxis"] and query["tr"] == [reference] and query["am"] == ["500.00"] and query["cu"] == ["INR"]
    # Replay does not create a second pay link.
    assert client.post(f"/reminders/{reminder['reminder_id']}/approve", json=body).json()["payment_reference"] == reference
    assert table_count(temp_db, "collection_requests") == 1
    sent = action(client, reminder["reminder_id"], "mock-send").json()
    assert sent["status"] == "SENT_MOCK" and sent["delivered_to_real_recipient"] is False


def test_link_without_amount_when_amount_hidden(client, raju, monkeypatch):
    set_profile(client)
    reminder = pending_reminder(client, monkeypatch)
    approved = approve(client, reminder["reminder_id"], include_payment_link=True).json()
    assert "₹" not in approved["message_preview"] and "am=" not in approved["message_preview"]
    assert approved["language_code"] == "en-IN" and approved["payment_reference"].startswith("MJ")


def test_tampered_localized_amount_is_rejected(client, raju, monkeypatch, temp_db):
    set_profile(client)
    reminder = pending_reminder(client, monkeypatch)
    response = approve(client, reminder["reminder_id"], include_amount=True, language_code="hi-IN",
                       localized_message="[Hindi] Raju bhai, ₹5,000.00 baaki hai", include_payment_link=True)
    assert response.status_code == 422 and response.json()["detail"]["code"] == "LOCALIZED_NUMBERS_MISMATCH"
    assert client.get(f"/reminders/{reminder['reminder_id']}").json()["status"] == "PENDING_APPROVAL"
    assert table_count(temp_db, "collection_requests") == 0


def test_language_without_reviewed_text_and_missing_upi_profile(client, raju, monkeypatch, temp_db):
    reminder = pending_reminder(client, monkeypatch)
    no_text = approve(client, reminder["reminder_id"], language_code="hi-IN")
    assert no_text.status_code == 422 and no_text.json()["detail"]["code"] == "LOCALIZED_MESSAGE_REQUIRED"
    no_profile = approve(client, reminder["reminder_id"], include_payment_link=True)
    assert no_profile.status_code == 409 and no_profile.json()["detail"]["code"] == "UPI_PROFILE_MISSING"
    assert client.get(f"/reminders/{reminder['reminder_id']}").json()["status"] == "PENDING_APPROVAL"
    assert table_count(temp_db, "collection_requests") == 0


# --- Payment-reference matching ---------------------------------------------------

def approved_with_link(client, monkeypatch):
    set_profile(client)
    reminder = pending_reminder(client, monkeypatch)
    return approve(client, reminder["reminder_id"], include_amount=True, include_payment_link=True).json()


def test_payment_with_reference_settles_and_cancels_reminder(client, raju, monkeypatch):
    approved = approved_with_link(client, monkeypatch)
    result = pay(client, 50000, reference=approved["payment_reference"].lower())  # case-insensitive
    assert result["resolution_status"] == "ALLOCATED" and result["matched_by"] == "payment_reference"
    assert result["collection_request_id"] == approved["collection_request_id"]
    assert balance(client, raju["customer_id"]) == 0
    assert client.get(f"/reminders/{approved['reminder_id']}").json()["status"] == "CANCELLED"
    requests = client.get(f"/customers/{raju['customer_id']}/collection-requests").json()
    assert requests[0]["status"] == "PAID" and requests[0]["paid_paise"] == 50000


def test_partial_payment_by_reference(client, raju, monkeypatch):
    approved = approved_with_link(client, monkeypatch)
    pay(client, 20000, reference=approved["payment_reference"])
    assert balance(client, raju["customer_id"]) == 30000
    request = client.get(f"/customers/{raju['customer_id']}/collection-requests").json()[0]
    assert request["status"] == "PART_PAID" and request["paid_paise"] == 20000
    assert client.get(f"/reminders/{approved['reminder_id']}").json()["status"] == "APPROVED_MOCK"


def test_unknown_reference_and_overpayment_go_to_review(client, raju, monkeypatch):
    unknown = pay(client, 1000, reference="MJDOESNOTEXIST")
    assert unknown["resolution_status"] == "UNMATCHED" and unknown["reason"] == "payment_reference_not_found"
    approved = approved_with_link(client, monkeypatch)
    over = pay(client, 90000, reference=approved["payment_reference"])
    assert over["resolution_status"] == "REVIEW" and over["reason"] == "payment_exceeds_outstanding_balance"
    queue = client.get("/payments/review").json()
    assert {row["payment_reference"] for row in queue} == {"MJDOESNOTEXIST", approved["payment_reference"]}
    assert balance(client, raju["customer_id"]) == 50000


def test_reference_conflicting_with_payer_mapping_needs_review(client, raju, make_customer, monkeypatch):
    other = make_customer("Mohan")
    client.post("/payments/payer-mappings", json={"payer_token": "payer-mohan", "customer_id": other["customer_id"],
                                                 "confirmed": True, "idempotency_key": key("map")})
    approved = approved_with_link(client, monkeypatch)
    result = pay(client, 10000, reference=approved["payment_reference"], payer_token="payer-mohan")
    assert result["resolution_status"] == "REVIEW" and result["reason"] == "payment_reference_conflicts_with_payer"
    assert balance(client, raju["customer_id"]) == 50000


def test_reference_replay_is_idempotent_and_reuse_is_rejected(client, raju, monkeypatch):
    approved = approved_with_link(client, monkeypatch)
    body = {"event_id": "evt-ref-1", "amount_paise": 10000, "status": "SUCCESS", "occurred_at": DAY15.isoformat(),
            "idempotency_key": "pay-ref-0001", "payment_reference": approved["payment_reference"]}
    first = client.post("/payments/intake", json=body).json()
    replay = client.post("/payments/intake", json=body).json()
    assert replay["idempotent_replay"] is True and replay["allocation_entry_id"] == first["allocation_entry_id"]
    changed = client.post("/payments/intake", json={**body, "payment_reference": "MJOTHERREF1"})
    assert changed.status_code == 409
    assert balance(client, raju["customer_id"]) == 40000


def test_payer_token_matching_unchanged(client, raju):
    client.post("/payments/payer-mappings", json={"payer_token": "payer-raju", "customer_id": raju["customer_id"],
                                                 "confirmed": True, "idempotency_key": key("map")})
    result = pay(client, 5000, payer_token="payer-raju")
    assert result["resolution_status"] == "ALLOCATED" and result["matched_by"] == "payer_token"
    assert result["payment_reference"] is None and result["collection_request_id"] is None


def test_upi_link_encoding():
    link = recovery.build_upi_link("shop@okaxis", "Raju & Sons", "MJABC123", 12345)
    query = parse_qs(urlparse(link).query)
    assert link.startswith("upi://pay?") and query["pn"] == ["Raju & Sons"] and query["am"] == ["123.45"]
