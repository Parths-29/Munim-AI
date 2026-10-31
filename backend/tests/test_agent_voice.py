"""Conversational voice copilot: spoken replies from verified results, truthful post-write receipts, new capabilities,
Gemini key rotation, and Sarvam TTS behaviour. All providers are faked; nothing reaches the network."""

import base64
import io
import json
import urllib.error

import pytest

from app.services import agent_llm, sarvam
from tests.conftest import key, table_count
from tests.test_agent import choose, confirm, count, ledger, say, shop  # noqa: F401  (fixture re-export)

THREE_KEYS = [("GEMINI_API_KEY", "k1"), ("GEMINI_API_KEY_FALLBACK_2", "k2"), ("GEMINI_API_KEY_FALLBACK_3", "k3")]


def http_error(code):
    return urllib.error.HTTPError("https://example.invalid", code, "x", {}, io.BytesIO(b"{}"))


def gemini_body(obj):
    return {"candidates": [{"content": {"parts": [{"text": json.dumps(obj)}]}}]}


def install_gemini(monkeypatch, plan_obj=None, reply=None, keys=None, errors=None):
    """Fake Gemini: interpretation calls get `plan_obj`, phrasing calls get {"reply": reply}. `errors` maps key → exception."""
    calls = []
    monkeypatch.setattr(agent_llm, "_api_keys", lambda: keys or [("GEMINI_API_KEY", "k1")])

    def call(api_key, model, payload, timeout):
        calls.append(api_key)
        if errors and api_key in errors:
            raise errors[api_key]
        system = payload.get("systemInstruction", {}).get("parts", [{}])[0].get("text", "")
        if system.startswith("You turn VERIFIED"):
            if reply is None:
                raise urllib.error.URLError("no phrasing")
            return gemini_body({"reply": reply})
        if plan_obj is None:
            raise urllib.error.URLError("no plan")
        return gemini_body(plan_obj)

    monkeypatch.setattr(agent_llm, "_call", call)
    return calls


# --- Spoken replies are built from backend results ----------------------------------------

def test_short_balance_reply_text_is_the_backend_balance(client, shop):
    data = say(client, "Raju ka balance?")
    assert data["reply_text"] == "Raju bhai owes ₹500." and data["reply_worded_by"] == "template"
    assert data["reply_language"] == "en-IN"


def test_gemini_may_word_verified_facts(client, shop, monkeypatch):
    install_gemini(monkeypatch, reply="Raju bhai ka balance ₹500 hai.")
    data = say(client, "Raju ka balance?")
    assert data["reply_text"] == "Raju bhai ka balance ₹500 hai." and data["reply_worded_by"] == "gemini"


def test_gemini_wording_with_an_invented_number_is_rejected(client, shop, monkeypatch):
    install_gemini(monkeypatch, reply="Raju bhai ka balance ₹5,000 hai.")
    data = say(client, "Raju ka balance?")
    assert data["reply_text"] == "Raju bhai owes ₹500." and data["reply_worded_by"] == "template"


def test_proposal_reply_says_nothing_saved_and_no_write_happens(client, shop):
    before = table_count(shop["db"], "ledger_entries")
    data = say(client, "Raju ko paanch sau rupaye udhaar likho")
    assert data["status"] == "proposal" and "Nothing is saved until you tap Confirm" in data["reply_text"]
    assert table_count(shop["db"], "ledger_entries") == before


def test_post_write_reply_uses_the_actual_resulting_balance(client, shop, temp_db):
    proposal = say(client, "Raju ko paanch sau rupaye udhaar likho")["proposal"]
    assert proposal["actions"][0]["balance_after_paise"] == 100000  # prediction at proposal time
    ledger(temp_db, shop["raju"]["customer_id"], "CREDIT", 20000)  # something else happened before confirm
    result = confirm(client, proposal).json()
    item = result["applied"][0]
    assert item["amount_paise"] == 50000 and item["balance_after_paise"] == 120000
    assert result["reply_text"] == "Saved. ₹500 udhaar recorded for Raju bhai; balance is now ₹1,200."


def test_post_write_wording_cannot_change_the_receipt(client, shop, monkeypatch):
    proposal = say(client, "Raju ko paanch sau rupaye udhaar likho")["proposal"]
    install_gemini(monkeypatch, reply="Ho gaya! Raju bhai ka naya balance ₹1,500 hai.")  # wrong number
    result = confirm(client, proposal).json()
    assert result["reply_worded_by"] == "template" and "₹1,000" in result["reply_text"]


def test_replayed_confirm_says_already_saved(client, shop):
    proposal = say(client, "Meena ne pachaas jama kiye")["proposal"]
    idem = key("c")
    confirm(client, proposal, idem)
    replay = confirm(client, proposal, idem).json()
    assert replay["idempotent_replay"] is True and replay["reply_text"].startswith("Already saved.")


# --- Natural English compound + follow-up ----------------------------------------------------

def test_english_compound_create_and_credit(client, shop):
    data = say(client, "Add Rajju as a customer and put ₹500 udhaar in his khata")
    # "Rajju" sounds like the existing "Raju bhai": ask before creating a near-duplicate.
    assert data["clarification"]["slot_id"] == "create:0"
    assert {c["label"] for c in data["clarification"]["choices"]} == {"Raju bhai", "Create new “Rajju”"}
    chosen = choose(client, data["session_id"], "create:0", "new")
    assert [a["kind"] for a in chosen["proposal"]["actions"]] == ["customer_create", "credit"]
    result = confirm(client, chosen["proposal"]).json()
    assert result["reply_text"] == "Saved. New customer Rajju added. ₹500 udhaar recorded for Rajju; balance is now ₹500."


def test_and_add_10_more_follow_up(client, shop):
    first = say(client, "Raju ko paanch sau rupaye udhaar likho")
    confirm(client, first["proposal"])
    follow = say(client, "and add 10 more", session=first["session_id"])
    action = follow["proposal"]["actions"][0]
    assert action["amount_paise"] == 1000 and action["customer_name"] == "Raju bhai" and len(action["inferred"]) == 2


# --- More existing capabilities ------------------------------------------------------------

def test_stock_count_and_stockout_proposals(client, shop):
    counted = say(client, "Amul Taaza ki ginti 12 packet")
    action = counted["proposal"]["actions"][0]
    assert action["kind"] == "stock_count" and (action["on_hand_before"], action["on_hand_after"]) == (10, 12)
    result = confirm(client, counted["proposal"]).json()
    assert result["applied"][0]["on_hand_after"] == 12 and "is now 12 packet" in result["reply_text"]
    out = say(client, "Amul Butter khatam ho gaya")
    assert out["proposal"]["actions"][0]["kind"] == "stockout"
    receipt = confirm(client, out["proposal"]).json()
    assert receipt["applied"][0]["on_hand_after"] == 5 and "still 5 packet" in receipt["reply_text"]


def test_supplier_balance_is_read_only(client, shop, make_supplier):
    make_supplier("Gupta Traders", ["Gupta"])
    data = say(client, "Gupta supplier ko kitna dena hai?")
    assert data["status"] == "answer" and data["answer"]["supplier_name"] == "Gupta Traders"
    assert data["reply_text"] == "The shop owes Gupta Traders ₹0."


def test_photo_flows_get_honest_guidance(client, shop):
    data = say(client, "invoice ki photo scan karni hai")
    assert data["answer"]["kind"] == "guidance" and "not part of the voice copilot yet" in data["reply_text"]


# --- Gemini key rotation -------------------------------------------------------------------

PLAN = {"corrected_utterance": None, "question": None, "confidence": 0.9, "actions": [{
    "kind": "balance", "customer_text": "Raju", "product_text": None, "supplier_text": None, "amount_text": None,
    "quantity_text": None, "unit_text": None, "refers_to_previous_customer": False, "refers_to_previous_action": False,
    "customer_from_action_index": None}]}


def test_rotation_moves_to_next_key_on_auth_failure(client, shop, monkeypatch):
    calls = install_gemini(monkeypatch, PLAN, keys=THREE_KEYS, errors={"k1": http_error(403)})
    data = say(client, "Raju ka balance?")
    assert data["llm"]["status"] == "ok" and data["llm"]["key_slot"] == "GEMINI_API_KEY_FALLBACK_2" and data["llm"]["attempts"] == 2
    assert calls[:2] == ["k1", "k2"] and "k2" not in json.dumps(data)


def test_rotation_on_quota_and_all_keys_exhausted(client, shop, monkeypatch):
    install_gemini(monkeypatch, PLAN, keys=THREE_KEYS, errors={k: http_error(429) for k in ("k1", "k2", "k3")})
    data = say(client, "Raju ka balance?")
    assert data["llm"]["status"] == "quota" and data["llm"]["attempts"] == 3 and "All 3 configured" in data["llm"]["detail"]
    assert data["answer"]["customer_name"] == "Raju bhai"  # deterministic fallback still answers


@pytest.mark.parametrize("error,status", [(urllib.error.URLError("timeout"), "unreachable"), (http_error(500), "server_error")])
def test_no_fan_out_on_timeouts_or_outages(client, shop, monkeypatch, error, status):
    calls = install_gemini(monkeypatch, PLAN, keys=THREE_KEYS, errors={"k1": error})
    data = say(client, "Raju ka balance?")
    assert data["llm"]["status"] == status
    assert calls.count("k2") == 0 and calls.count("k3") == 0  # interpretation and phrasing never tried other keys


def test_health_lists_slot_names_only(client, monkeypatch):
    install_gemini(monkeypatch, PLAN, keys=THREE_KEYS)
    body = client.get("/agent/health?refresh=true").json()
    assert body["key_slots_configured"] == ["GEMINI_API_KEY", "GEMINI_API_KEY_FALLBACK_2", "GEMINI_API_KEY_FALLBACK_3"]
    assert body["voice_output"] == "fake" and not any(k in json.dumps(body) for k in ("k1", "k2", "k3"))


# --- Sarvam voice output -------------------------------------------------------------------

def test_speak_returns_wav_and_never_stores(client):
    body = client.post("/agent/speak", json={"text": "Raju bhai owes ₹500."}).json()
    assert body["stored"] is False and body["provider"] == "fake" and base64.b64decode(body["audio_base64"])[:4] == b"RIFF"


def test_speak_off_gives_clear_error(client, monkeypatch):
    monkeypatch.setenv("MUNIM_SARVAM_MODE", "off")
    response = client.post("/agent/speak", json={"text": "hello"})
    assert response.status_code == 503 and "SARVAM_API_KEY" in response.json()["detail"]["message"]


def test_tts_uses_language_code_and_falls_back_to_v2_once(monkeypatch):
    monkeypatch.setenv("MUNIM_SARVAM_MODE", "live")
    payloads = []

    def post(url, payload, timeout):
        payloads.append(payload)
        if payload["model"] == "bulbul:v3":
            raise http_error(400)
        return {"audios": [base64.b64encode(b"RIFFdata").decode()]}

    monkeypatch.setattr(sarvam, "_post", post)
    result = sarvam.synthesize_speech("Raju bhai owes ₹500.", "en-IN")
    assert [p["model"] for p in payloads] == ["bulbul:v3", "bulbul:v2"] and result.model == "bulbul:v2"
    assert payloads[0]["language_code"] == "en-IN" and "target_language_code" not in payloads[0] and payloads[0]["speaker"] == "shubh"


def test_tts_timeout_is_not_retried(monkeypatch):
    monkeypatch.setenv("MUNIM_SARVAM_MODE", "live")
    calls = []

    def post(url, payload, timeout):
        calls.append(payload["model"])
        raise TimeoutError()

    monkeypatch.setattr(sarvam, "_post", post)
    with pytest.raises(sarvam.SpeechUnavailable, match="unreachable or timed out"):
        sarvam.synthesize_speech("hello", "en-IN")
    assert calls == ["bulbul:v3"]
