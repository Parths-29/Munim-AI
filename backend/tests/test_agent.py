"""Voice-first agent: short natural requests, aliases, Hinglish amounts, ambiguity, context, compound + atomic confirm,
and Gemini success/failure (faked; tests never reach the network)."""

import io
import json
import sqlite3
import urllib.error
import uuid
from datetime import datetime, timezone

import pytest

from app.services import agent_llm
from tests.conftest import key, table_count

NOW = datetime.now(timezone.utc).isoformat()


def ledger(path, customer_id, entry_type, amount):
    with sqlite3.connect(path) as connection:
        entry = f"entry_{uuid.uuid4().hex[:12]}"
        connection.execute(
            """INSERT INTO ledger_entries (entry_id, shop_id, customer_id, entry_type, amount_paise, source_event_id, idempotency_key,
               status, created_at) VALUES (?, 'shop_synth_01', ?, ?, ?, ?, ?, 'POSTED', ?)""",
            (entry, customer_id, entry_type, amount, f"src-{entry}", f"key-{entry}", NOW))


def count(client, product_id, quantity):
    response = client.post("/inventory/counts", json={"product_id": product_id, "counted_quantity": quantity,
                                                      "source_event_id": key("src"), "idempotency_key": key(), "confirmed": True})
    assert response.status_code == 201, response.text


@pytest.fixture
def shop(client, temp_db, make_customer, make_product):
    raju = make_customer("Raju bhai")
    meena = make_customer("Meena ben")
    ledger(temp_db, raju["customer_id"], "CREDIT", 50000)
    ledger(temp_db, meena["customer_id"], "CREDIT", 50000)
    butter = make_product("Amul Butter 100g", "packet", ["Amul Butter"])
    taaza = make_product("Amul Taaza", "packet")
    count(client, butter["product_id"], 5)
    count(client, taaza["product_id"], 10)
    return {"raju": raju, "meena": meena, "butter": butter, "taaza": taaza, "db": temp_db}


def say(client, text, session=None, **extra):
    response = client.post("/agent/turn", json={"utterance": text, "session_id": session, **extra})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["writes_performed"] is False
    return data


def choose(client, session, slot, option):
    response = client.post("/agent/turn", json={"session_id": session, "choice": {"slot_id": slot, "option_id": option}})
    assert response.status_code == 200, response.text
    return response.json()


def confirm(client, proposal, idem=None):
    return client.post(f"/agent/proposals/{proposal['proposal_id']}/confirm",
                       json={"confirmed": True, "content_hash": proposal["content_hash"], "idempotency_key": idem or key("confirm")})


def balance(client, customer_id):
    return client.get(f"/ledger/customers/{customer_id}/balance").json()["balance_due_paise"]


# --- Short natural requests and aliases ---------------------------------------------

def test_short_balance_resolves_honorific_alias_without_writing(client, shop):
    before = table_count(shop["db"], "ledger_entries")
    data = say(client, "Raju ka balance?")
    assert data["status"] == "answer" and data["answer"]["customer_name"] == "Raju bhai"
    assert data["answer"]["balance_due_paise"] == 50000 and data["message"] == "Raju bhai owes ₹500."
    assert table_count(shop["db"], "ledger_entries") == before


def test_spoken_variant_is_shown_as_inference(client, shop):
    data = say(client, "Raaju ka hisaab batao")
    assert data["answer"]["customer_name"] == "Raju bhai"
    assert any("heard “Raaju”" in note for note in data["answer"]["notes"])


@pytest.mark.parametrize("text,kind,amount", [
    ("Raju ko paanch sau udhaar mein likho", "credit", 50000),
    ("Raju bhai ka 250 rupaye udhar likh do", "credit", 25000),
    ("Raju ko dedh sau udhaar", "credit", 15000),
])
def test_hinglish_credit_amounts(client, shop, text, kind, amount):
    data = say(client, text)
    action = data["proposal"]["actions"][0]
    assert data["status"] == "proposal" and action["kind"] == kind and action["amount_paise"] == amount
    assert action["balance_before_paise"] == 50000 and action["balance_after_paise"] == 50000 + amount


def test_repayment_without_rupee_word_and_confirm_is_idempotent(client, shop):
    proposal = say(client, "Meena ne pachaas jama kiye")["proposal"]
    assert proposal["actions"][0]["kind"] == "repayment" and proposal["actions"][0]["amount_paise"] == 5000
    idem = key("confirm")
    first = confirm(client, proposal, idem)
    assert first.status_code == 200 and first.json()["applied"][0]["kind"] == "repayment"
    replay = confirm(client, proposal, idem).json()
    assert replay["idempotent_replay"] is True
    assert confirm(client, proposal).status_code == 409  # a second, different confirm cannot apply it again
    assert balance(client, shop["meena"]["customer_id"]) == 45000


def test_repayment_more_than_balance_asks(client, shop):
    data = say(client, "Meena ne 900 rupaye jama kiye")
    assert data["status"] == "clarification" and "owes ₹500" in data["message"]


# --- Ambiguity and uncertain numbers ----------------------------------------------------

def test_ambiguous_customer_offers_choices(client, shop, make_customer):
    chacha = make_customer("Raju chacha")
    data = say(client, "Raju ko 100 rupaye udhaar")
    assert data["status"] == "clarification"
    assert {c["label"] for c in data["clarification"]["choices"]} == {"Raju bhai", "Raju chacha"}
    picked = choose(client, data["session_id"], data["clarification"]["slot_id"], chacha["customer_id"])
    assert picked["status"] == "proposal" and picked["proposal"]["actions"][0]["customer_name"] == "Raju chacha"


def test_pachs_asks_pachas_or_pachis_and_never_converts(client, shop):
    data = say(client, "pachs add kro")
    assert data["status"] == "clarification" and "pachs" in data["message"]
    assert {c["option_id"] for c in data["clarification"]["choices"]} == {"2500", "5000"}
    after = choose(client, data["session_id"], data["clarification"]["slot_id"], "5000")
    assert after["status"] == "clarification" and after["clarification"]["slot_id"].startswith("action:")


def test_unknown_customer_credit_offers_create_then_combined_proposal(client, shop):
    data = say(client, "Sunil ko 300 rupaye udhaar likho")
    options = {c["option_id"] for c in data["clarification"]["choices"]}
    assert "new" in options
    proposal = choose(client, data["session_id"], data["clarification"]["slot_id"], "new")["proposal"]
    assert [a["kind"] for a in proposal["actions"]] == ["customer_create", "credit"]
    assert confirm(client, proposal).status_code == 200


def test_sale_with_ambiguous_product_then_confirm_reduces_stock(client, shop):
    data = say(client, "Do Amul packets bech diye")
    assert data["status"] == "clarification"
    assert {c["label"] for c in data["clarification"]["choices"]} == {"Amul Butter 100g", "Amul Taaza"}
    proposal = choose(client, data["session_id"], data["clarification"]["slot_id"], shop["taaza"]["product_id"])["proposal"]
    action = proposal["actions"][0]
    assert action["kind"] == "sale" and action["quantity"] == 2 and (action["on_hand_before"], action["on_hand_after"]) == (10, 8)
    assert confirm(client, proposal).status_code == 200
    assert client.get(f"/inventory/products/{shop['taaza']['product_id']}/stock").json()["on_hand_quantity"] == 8


# --- Compound actions and atomic confirm ------------------------------------------------

def test_new_customer_plus_credit_in_one_turn(client, shop):
    data = say(client, "Rajju Sharma naya customer hai, aur uske ₹500 udhaar likho")
    actions = data["proposal"]["actions"]
    assert [a["kind"] for a in actions] == ["customer_create", "credit"]
    assert actions[1]["creates_customer_ref"] == 0 and actions[1]["amount_paise"] == 50000
    result = confirm(client, data["proposal"]).json()
    created = result["applied"][0]["entity_id"]
    assert balance(client, created) == 50000


def test_multi_action_confirm_is_all_or_nothing(client, shop, temp_db):
    data = say(client, "Kiran naya customer hai, aur Meena ne 300 rupaye jama kiye")
    assert [a["kind"] for a in data["proposal"]["actions"]] == ["customer_create", "repayment"]
    ledger(temp_db, shop["meena"]["customer_id"], "REPAYMENT", 40000)  # balance drops to ₹100 before confirm
    customers_before = table_count(temp_db, "customers")
    response = confirm(client, data["proposal"])
    assert response.status_code == 409 and response.json()["detail"]["code"] == "REPAYMENT_EXCEEDS_BALANCE"
    assert table_count(temp_db, "customers") == customers_before  # the customer creation rolled back too


# --- Follow-up context ----------------------------------------------------------------

def test_follow_up_reuses_customer_and_action_as_marked_inference(client, shop):
    first = say(client, "Raju ko paanch sau udhaar likho")
    confirm(client, first["proposal"])
    follow = say(client, "Aur 500 add kar do", session=first["session_id"])
    action = follow["proposal"]["actions"][0]
    assert action["kind"] == "credit" and action["customer_name"] == "Raju bhai" and action["amount_paise"] == 50000
    assert any("customer: Raju bhai" in n for n in action["inferred"]) and any("action: udhaar" in n for n in action["inferred"])
    assert action["balance_before_paise"] == 100000


def test_follow_up_after_balance_asks_credit_or_repayment(client, shop):
    first = say(client, "Raju ka balance?")
    follow = say(client, "Aur 500 add kar do", session=first["session_id"])
    assert follow["status"] == "clarification" and follow["clarification"]["slot_id"] == "action:0"
    proposal = choose(client, follow["session_id"], "action:0", "credit")["proposal"]
    assert proposal["actions"][0]["customer_name"] == "Raju bhai"


def test_context_never_crosses_shops(client, shop):
    first = say(client, "Raju ka balance?")
    other = client.post("/agent/turn", json={"utterance": "Aur 500 add kar do", "session_id": first["session_id"]},
                        headers={"X-Munim-Shop": "tea_stall"}).json()
    assert other["session_id"] != first["session_id"] and other["status"] == "clarification"


def test_without_cue_the_previous_customer_is_only_suggested(client, shop):
    first = say(client, "Raju ka balance?")
    follow = say(client, "500 rupaye udhaar likho", session=first["session_id"])
    assert follow["status"] == "clarification" and follow["clarification"]["choices"][0]["label"] == "Raju bhai"


# --- Cancel, spoken yes, corrections ---------------------------------------------------------

def test_cancel_and_spoken_yes(client, shop):
    first = say(client, "Raju ko 200 rupaye udhaar likho")
    yes = say(client, "haan", session=first["session_id"])
    assert yes["status"] == "info" and "tap Confirm" in yes["message"]
    cancelled = say(client, "cancel", session=first["session_id"])
    assert cancelled["status"] == "cancelled"
    assert confirm(client, first["proposal"]).json()["detail"]["code"] == "PROPOSAL_CANCELLED"
    assert balance(client, shop["raju"]["customer_id"]) == 50000


def test_amount_correction_supersedes_pending_proposal(client, shop):
    first = say(client, "Raju ko 500 rupaye udhaar likho")
    corrected = say(client, "nahi, 600", session=first["session_id"])
    action = corrected["proposal"]["actions"][0]
    assert action["amount_paise"] == 60000 and "amount corrected" in action["inferred"][0]
    assert confirm(client, first["proposal"]).json()["detail"]["code"] == "PROPOSAL_SUPERSEDED"


def test_stale_hash_is_rejected(client, shop):
    proposal = say(client, "Raju ko 200 rupaye udhaar likho")["proposal"]
    response = client.post(f"/agent/proposals/{proposal['proposal_id']}/confirm",
                           json={"confirmed": True, "content_hash": "0" * 32, "idempotency_key": key("c")})
    assert response.json()["detail"]["code"] == "PROPOSAL_CHANGED"


def test_transcript_original_is_kept(client, shop):
    data = say(client, "Raju ka balance?", transcript_original="raju ka balans", source_channel="voice")
    assert data["transcript"] == {"original": "raju ka balans", "used": "Raju ka balance?", "model_corrected": None}


# --- Gemini (faked) -------------------------------------------------------------------

def fake_gemini(monkeypatch, plan=None, error=None):
    monkeypatch.setattr(agent_llm, "_api_keys", lambda: [("GEMINI_API_KEY", "test-key")])

    def call(api_key, model, payload, timeout):
        if error:
            raise error
        return {"candidates": [{"content": {"parts": [{"text": json.dumps(plan)}]}}]}

    monkeypatch.setattr(agent_llm, "_call", call)


def plan(*actions, corrected=None, question=None):
    base = {"customer_text": None, "product_text": None, "amount_text": None, "quantity_text": None, "unit_text": None,
            "refers_to_previous_customer": False, "refers_to_previous_action": False, "customer_from_action_index": None}
    return {"corrected_utterance": corrected, "actions": [{**base, **a} for a in actions], "question": question, "confidence": 0.9}


def test_gemini_plan_is_used_and_amount_computed_deterministically(client, shop, monkeypatch):
    fake_gemini(monkeypatch, plan({"kind": "credit", "customer_text": "Raju", "amount_text": "paanch sau"}))
    data = say(client, "Raju ko paanch sau udhaar mein likho")
    assert data["interpreted_by"] == "gemini" and data["llm"]["status"] == "ok"
    assert data["proposal"]["actions"][0]["amount_paise"] == 50000


def test_gemini_cannot_infer_credit_or_invent_spans(client, shop, monkeypatch):
    fake_gemini(monkeypatch, plan({"kind": "credit", "customer_text": "Raju", "amount_text": "500"}))
    assert say(client, "Raju ko 500 add karo")["clarification"]["slot_id"] == "action:0"
    fake_gemini(monkeypatch, plan({"kind": "credit", "customer_text": "Mohan", "amount_text": "₹500"}))
    data = say(client, "₹500 udhaar likho")
    assert data["status"] == "clarification" and "customer" in data["clarification"]["missing"]


def test_gemini_compound_plan(client, shop, monkeypatch):
    fake_gemini(monkeypatch, plan({"kind": "customer_create", "customer_text": "Rajju Sharma"},
                                  {"kind": "credit", "amount_text": "₹500", "customer_from_action_index": 0}))
    data = say(client, "Rajju Sharma naya customer hai, aur uske ₹500 udhaar likho")
    assert [a["kind"] for a in data["proposal"]["actions"]] == ["customer_create", "credit"]


@pytest.mark.parametrize("error,status", [
    (urllib.error.URLError("proxy"), "unreachable"),
    (urllib.error.HTTPError("u", 403, "forbidden", {}, io.BytesIO(b"{}")), "auth_error"),
    (urllib.error.HTTPError("u", 404, "missing", {}, io.BytesIO(b"{}")), "model_not_found"),
])
def test_gemini_failure_falls_back_to_deterministic(client, shop, monkeypatch, error, status):
    fake_gemini(monkeypatch, error=error)
    data = say(client, "Raju ko paanch sau udhaar mein likho")
    assert data["llm"]["status"] == status and data["interpreted_by"] == "deterministic"
    assert data["proposal"]["actions"][0]["amount_paise"] == 50000
    if status == "auth_error":
        assert ".env" in data["llm"]["detail"] and "test-key" not in json.dumps(data)


def test_health_reports_category_without_key(client, monkeypatch):
    assert client.get("/agent/health?refresh=true").json()["llm"]["status"] == "not_configured"
    fake_gemini(monkeypatch, plan())
    body = client.get("/agent/health?refresh=true").json()
    assert body["llm"]["status"] == "ok" and body["key_configured"] is True and "test-key" not in json.dumps(body)
