import pytest

from app.services import inward_parser
from tests.conftest import key, table_count

EXAMPLE = "Doodh wale se 15 packet Amul Taaza aur 10 dahi liye."


@pytest.fixture
def shop(make_product, make_supplier):
    return {
        "amul": make_product("Amul Taaza", "packet"),
        "dahi": make_product("Dahi", "cup"),
        "supplier": make_supplier("Gupta Dairy"),
    }


def interpret(client, utterance=EXAMPLE, channel="voice", idem=None):
    response = client.post("/inventory/inward/proposals", json={
        "utterance": utterance, "source_channel": channel, "idempotency_key": idem or key("inward"),
    })
    assert response.status_code == 200, response.text
    return response.json()


def revise(client, proposal, lines, **extra):
    response = client.post(f"/inventory/inward/proposals/{proposal['proposal_id']}/revise", json={
        "expected_version": proposal["version"], "lines": lines, **extra,
    })
    assert response.status_code == 200, response.text
    return response.json()


def confirm(client, proposal, paid_now=None, idem=None):
    return client.post(f"/inventory/inward/proposals/{proposal['proposal_id']}/confirm", json={
        "expected_version": proposal["version"], "content_hash": proposal["content_hash"], "paid_now_paise": paid_now,
        "confirmed": True, "idempotency_key": idem or key("confirm"), "source_channel": "voice",
    })


def stock(client, product):
    return client.get(f"/inventory/products/{product['product_id']}/stock").json()["on_hand_quantity"]


def test_example_produces_two_lines_and_asks_unit_for_dahi(client, shop, temp_db):
    result = interpret(client)
    assert result["status"] == "proposal" and result["parsed_by"] == "deterministic"
    proposal = result["proposal"]
    assert proposal["source_kind"] == "voice_inward" and proposal["source_utterance"] == EXAMPLE
    amul, dahi = proposal["lines"]
    assert (amul["quantity"], amul["unit"], amul["match_status"], amul["base_quantity"]) == (15, "packet", "MATCHED", 15)
    assert (dahi["quantity"], dahi["unit"], dahi["match_status"]) == (10, None, "MATCHED")
    unit_issue = next(i for i in dahi["issues"] if i["code"] == "UNIT_MISSING")
    assert "cup" in unit_issue["message"] and dahi["unit_options"] == ["cup"]
    assert proposal["supplier"]["label"] == "Doodh wale" and proposal["supplier"]["match_status"] == "NOT_FOUND"
    assert proposal["supplier"]["supplier_id"] is None  # generic phrase is never mapped to a supplier
    assert proposal["status"] == "NEEDS_REVIEW"
    assert table_count(temp_db, "stock_receipt_movements") == 0


def test_quantity_only_inward_changes_stock_only(client, shop, temp_db):
    proposal = interpret(client)["proposal"]
    amul, dahi = proposal["lines"]
    ready = revise(client, proposal, [
        {"line_id": amul["line_id"], "product_name_text": "Amul Taaza", "quantity": 15, "unit_text": "packet"},
        {"line_id": dahi["line_id"], "product_name_text": "dahi", "quantity": 10, "unit_text": "cup"},
    ], supplier={"label": "Doodh wale"})
    assert ready["status"] == "READY", ready["issues"]
    assert "No verified total" in ready["totals"]["payable_note"]
    receipt = confirm(client, ready, idem="inward-confirm-01")
    assert receipt.status_code == 201, receipt.text
    receipt = receipt.json()
    assert receipt["payable_status"] == "NOT_SUPPLIED" and receipt["payable_entry_id"] is None
    assert receipt["supplier_label"] == "Doodh wale"
    assert stock(client, shop["amul"]) == 15 and stock(client, shop["dahi"]) == 10
    assert table_count(temp_db, "supplier_payable_entries") == 0
    replay = confirm(client, ready, idem="inward-confirm-01").json()
    assert replay["idempotent_replay"] is True and stock(client, shop["amul"]) == 15
    assert table_count(temp_db, "stock_receipt_movements") == 2


def test_paid_now_without_total_rejected(client, shop):
    proposal = interpret(client, "15 packet Amul Taaza aaye")["proposal"]
    assert proposal["status"] == "READY"
    assert confirm(client, proposal, paid_now=5000).status_code == 422


def test_explicit_confirmed_cost_creates_one_payable(client, shop, temp_db):
    proposal = interpret(client, "Gupta Dairy se 20 cup dahi liye")["proposal"]
    assert proposal["supplier"]["match_status"] == "RESOLVED"
    line = proposal["lines"][0]
    priced = revise(client, proposal, [
        {"line_id": line["line_id"], "product_name_text": "dahi", "quantity": 20, "unit_text": "cup",
         "unit_cost_paise": 2500, "line_total_paise": 50000},
    ], supplier={"supplier_id": shop["supplier"]["supplier_id"]}, invoice={"total_paise": 50000})
    assert priced["status"] == "READY", priced["issues"]
    receipt = confirm(client, priced, paid_now=10000, idem="inward-paid-0001").json()
    assert receipt["payable_status"] == "POSTED"
    assert client.get(f"/suppliers/{shop['supplier']['supplier_id']}/balance").json()["amount_due_paise"] == 40000
    confirm(client, priced, paid_now=10000, idem="inward-paid-0001")
    assert table_count(temp_db, "supplier_payable_entries") == 1


@pytest.mark.parametrize("utterance", ["kuch maal aaya", "Amul 15 packet 42 rupaye ka"])
def test_unclear_or_priced_speech_asks_for_clarification(client, shop, temp_db, utterance):
    result = interpret(client, utterance)
    assert result["status"] == "clarification" and result["proposal"] is None and result["message"]
    assert table_count(temp_db, "intake_proposals") == 0


def test_llm_outage_creates_no_writes(client, shop, temp_db, monkeypatch):
    monkeypatch.setattr(inward_parser, "llm_interpret", lambda utterance: None)
    result = interpret(client, "thoda doodh aur kuch bread")
    assert result["status"] == "clarification"
    assert table_count(temp_db, "intake_proposals") == 0 and table_count(temp_db, "stock_receipt_movements") == 0


def test_llm_spans_must_be_verbatim(client, shop, temp_db, monkeypatch):
    utterance = "Amul Taaza pandrah ke packet wale aaye"
    invented = {"supplier_text": None, "clarification": None,
                "lines": [{"quantity_text": "15", "unit_text": "packet", "product_text": "Amul Taaza"}]}
    monkeypatch.setattr(inward_parser, "llm_interpret", lambda u: invented)
    result = interpret(client, utterance)
    assert result["status"] == "clarification"  # "15" never appears in the utterance
    verbatim = {"supplier_text": None, "clarification": None,
                "lines": [{"quantity_text": "pandrah", "unit_text": "packet", "product_text": "Amul Taaza"}]}
    monkeypatch.setattr(inward_parser, "llm_interpret", lambda u: verbatim)
    result = interpret(client, utterance)
    assert result["status"] == "proposal" and result["parsed_by"] == "gemini"
    assert result["proposal"]["lines"][0]["quantity"] == 15
    assert table_count(temp_db, "stock_receipt_movements") == 0


def test_unknown_product_needs_selection(client, shop):
    proposal = interpret(client, "5 packet bread liye")["proposal"]
    assert proposal["lines"][0]["match_status"] == "NOT_FOUND"
    assert confirm(client, proposal).json()["detail"]["code"] == "PROPOSAL_NOT_READY"


def test_inward_idempotent_interpretation(client, shop, temp_db):
    first = interpret(client, idem="inward-key-0001")["proposal"]
    again = interpret(client, idem="inward-key-0001")["proposal"]
    assert again["proposal_id"] == first["proposal_id"]
    conflict = client.post("/inventory/inward/proposals", json={
        "utterance": "3 packet Amul Taaza", "source_channel": "voice", "idempotency_key": "inward-key-0001"})
    assert conflict.status_code == 409
    assert table_count(temp_db, "intake_proposals") == 1


def test_inward_and_invoice_endpoints_are_separate(client, shop):
    proposal = interpret(client)["proposal"]
    assert client.get(f"/invoices/proposals/{proposal['proposal_id']}").status_code == 404
