import copy
from datetime import datetime, timedelta, timezone

import pytest

from app.services import ledger_pages, reminders
from app.services.invoice_extraction import ProviderUnavailable
from app.services.notebook_extraction import FAKE_PAGE, FakeNotebookProvider
from tests.conftest import key, table_count
from tests.images import png


def use(monkeypatch, data=None, fail=False):
    class Failing:
        name = "gemini"

        def extract(self, image, mime_type):
            raise ProviderUnavailable("timeout")

    provider = Failing() if fail else FakeNotebookProvider(data)
    monkeypatch.setattr(ledger_pages, "get_notebook_provider", lambda: provider)


def scan(client, image=None, idem=None):
    response = client.post("/ledger-pages", files={"file": ("page.png", image or png(), "image/png")},
                           data={"idempotency_key": idem or key("page")})
    assert response.status_code == 201, response.text
    return response.json()


def codes(line):
    return {issue["code"] for issue in line["issues"]}


def review_all(client, page, raju_id, patil_create=True):
    """Merchant review: verify every row, create new customers, set Meena's kind."""
    lines = []
    for line in page["lines"]:
        edit = {"line_id": line["line_id"], "name_text": line["name_text"], "name_latin": line["name_latin"],
                "amount_paise": line["amount_paise"], "entry_type": line["entry_type"] or "CREDIT",
                "entry_date": line["entry_date"], "merchant_verified": True}
        if line["name_latin"] == "Raju bhai":
            edit["customer_id"] = raju_id
        else:
            edit["create_customer"] = patil_create
        lines.append(edit)
    response = client.post(f"/ledger-pages/{page['proposal_id']}/revise", json={"expected_version": page["version"], "lines": lines})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def raju(make_customer, client):
    customer = make_customer("Raju bhai", ["Raju"])
    client.post("/ledger/credits", json={"customer_id": customer["customer_id"], "amount_paise": 50000, "source_event_id": "c0",
                                         "idempotency_key": key(), "confirmed": True})
    return customer


def test_scan_creates_draft_only(client, raju, monkeypatch, temp_db):
    use(monkeypatch)
    before = table_count(temp_db, "ledger_entries")
    page = scan(client)
    assert page["status"] == "NEEDS_REVIEW" and page["image_retained"] is False
    sharma, raju_line, patil, meena = page["lines"]
    assert sharma["name_text"] == "शर्मा जी" and sharma["amount_paise"] == 120000 and sharma["entry_type"] == "CREDIT"
    assert sharma["entry_date"] == "2026-10-28" and sharma["match_status"] == "NOT_FOUND"
    assert raju_line["match_status"] == "MATCHED" and raju_line["entry_type"] == "REPAYMENT"
    assert patil["amount_paise"] == 35000 and "LOW_CONFIDENCE" in codes(patil)  # Devanagari digits read deterministically
    assert "ENTRY_TYPE_MISSING" in codes(meena)
    assert table_count(temp_db, "ledger_entries") == before
    assert b"\x89PNG" not in temp_db.read_bytes()


def test_voice_correction_applies_to_one_row(client, raju, monkeypatch):
    use(monkeypatch)
    page = scan(client)
    result = client.post(f"/ledger-pages/{page['proposal_id']}/voice-correction",
                         json={"expected_version": 1, "utterance": "Patil kaka, ३५० udhaar"}).json()
    assert result["status"] == "applied"
    patil = next(line for line in result["proposal"]["lines"] if line["line_id"] == result["matched_line_id"])
    assert patil["merchant_verified"] and "LOW_CONFIDENCE" not in codes(patil)
    assert result["proposal"]["version"] == 2
    unclear = client.post(f"/ledger-pages/{page['proposal_id']}/voice-correction",
                          json={"expected_version": 2, "utterance": "Gupta ji 500"}).json()
    assert unclear["status"] == "clarification" and unclear["proposal"]["version"] == 2


def test_confirm_posts_with_notebook_dates_and_creates_chosen_customers(client, raju, monkeypatch, temp_db):
    use(monkeypatch)
    page = review_all(client, scan(client), raju["customer_id"])
    assert page["status"] == "READY", [l["issues"] for l in page["lines"]]
    assert page["totals"]["customers_to_create"] == 3
    body = {"expected_version": page["version"], "content_hash": page["content_hash"], "confirmed": True,
            "idempotency_key": "page-confirm-0001"}
    posted = client.post(f"/ledger-pages/{page['proposal_id']}/confirm", json=body)
    assert posted.status_code == 201, posted.text
    posted = posted.json()
    assert posted["customers_created"] == 3 and len(posted["entries"]) == 4
    by_name = {e["display_name"]: e for e in posted["entries"]}
    assert by_name["Sharma ji"]["occurred_on"] == "2026-10-28" and by_name["Sharma ji"]["customer_created"]
    assert by_name["Raju bhai"]["balance_after_paise"] == 20000 and not by_name["Raju bhai"]["customer_created"]
    sharma = client.get("/customers/resolve", params={"query": "शर्मा जी"}).json()
    assert sharma["status"] == "RESOLVED"
    assert client.get(f"/ledger/customers/{sharma['matches'][0]['customer_id']}/balance").json()["balance_due_paise"] == 120000
    replay = client.post(f"/ledger-pages/{page['proposal_id']}/confirm", json=body).json()
    assert replay["idempotent_replay"] and replay["batch_id"] == posted["batch_id"]
    assert table_count(temp_db, "ledger_entries") == 5
    other = client.post(f"/ledger-pages/{page['proposal_id']}/confirm", json={**body, "idempotency_key": key()})
    assert other.status_code == 409


def test_notebook_date_drives_overdue_age(client, raju, monkeypatch):
    use(monkeypatch)
    page = review_all(client, scan(client), raju["customer_id"])
    client.post(f"/ledger-pages/{page['proposal_id']}/confirm", json={
        "expected_version": page["version"], "content_hash": page["content_hash"], "confirmed": True, "idempotency_key": key()})
    patil = client.get("/customers/resolve", params={"query": "Patil kaka"}).json()["matches"][0]
    moment = datetime(2026, 10, 31, 6, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(reminders, "now_utc", lambda: moment)
    rows = client.get("/reminders/eligibility/preview", params={"as_of": moment.isoformat()}).json()["rows"]
    row = next(r for r in rows if r["customer_id"] == patil["customer_id"])
    assert row["oldest_unpaid_local_date"] == "2026-10-15" and row["overdue_days"] == 16


def test_unresolved_names_never_guessed(client, raju, monkeypatch, temp_db):
    use(monkeypatch)
    page = review_all(client, scan(client), raju["customer_id"], patil_create=False)
    assert page["status"] == "NEEDS_REVIEW"
    blocked = client.post(f"/ledger-pages/{page['proposal_id']}/confirm", json={
        "expected_version": page["version"], "content_hash": page["content_hash"], "confirmed": True, "idempotency_key": key()})
    assert blocked.json()["detail"]["code"] == "PROPOSAL_NOT_READY"
    assert table_count(temp_db, "customers") == 1


def test_repayment_cannot_exceed_balance(client, raju, monkeypatch):
    data = copy.deepcopy(FAKE_PAGE)
    data["lines"] = [{"source_text": "Raju 900 jama", "name_text": "Raju", "name_latin": "Raju", "amount_text": "900",
                      "kind_text": "jama", "date_text": "29/10/2026", "confidence": 0.95}]
    use(monkeypatch, data)
    page = scan(client)
    assert "REPAYMENT_EXCEEDS_BALANCE" in codes(page["lines"][0])


def test_future_date_and_stale_and_outage(client, raju, monkeypatch, temp_db):
    data = copy.deepcopy(FAKE_PAGE)
    future = (datetime.now(timezone.utc) + timedelta(days=5)).strftime("%d/%m/%Y")
    data["lines"] = [{**FAKE_PAGE["lines"][1], "date_text": future}]
    use(monkeypatch, data)
    page = scan(client)
    assert "DATE_IN_FUTURE" in codes(page["lines"][0])
    stale = client.post(f"/ledger-pages/{page['proposal_id']}/confirm", json={
        "expected_version": 1, "content_hash": "0" * 64, "confirmed": True, "idempotency_key": key()})
    assert stale.status_code == 409
    use(monkeypatch, fail=True)
    empty = scan(client, png(500, 400))
    assert empty["extraction"]["status"] == "PROVIDER_UNAVAILABLE" and empty["lines"] == []
    assert table_count(temp_db, "ledger_entries") == 1
