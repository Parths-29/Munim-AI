"""Sarvam command interpretation guards for Hinglish credit/repayment (offline: the provider response is faked)."""

import io
import json

import pytest

from app.services import command_nlp


def fake_sarvam(monkeypatch, **reply):
    data = {"intent": "clarification", "entity_text": None, "amount_text": None, "count_text": None,
            "confidence": 0.95, "message": None, **reply}
    body = json.dumps({"choices": [{"message": {"content": json.dumps(data)}}]}).encode()

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(command_nlp, "_get_api_key", lambda: "test-key")
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: Response(body))


def interpret(client, utterance):
    response = client.post("/commands/interpret", json={"utterance": utterance, "source_channel": "voice"})
    assert response.status_code == 200, response.text
    return response.json()


def test_pachs_add_kro_asks_for_every_missing_detail(client, monkeypatch):
    fake_sarvam(monkeypatch)
    result = interpret(client, "pachs add kro")
    assert result["status"] == "clarification" and result["intent"] is None
    assert result["message"].startswith("Please tell me which customer it is for, whether it is udhaar (credit given) "
                                        "or jama (payment received) and the amount in rupees.")


def test_model_cannot_convert_uncertain_word_into_money(client, monkeypatch):
    fake_sarvam(monkeypatch, intent="credit", entity_text="pachs", amount_text="pachs", confidence=0.9)
    assert interpret(client, "pachs add kro")["status"] == "clarification"


def test_model_cannot_invent_a_customer(client, monkeypatch):
    fake_sarvam(monkeypatch, intent="credit", entity_text="Raju", amount_text="pachs", confidence=0.9)
    assert interpret(client, "pachs add kro")["status"] == "clarification"


def test_model_cannot_infer_credit_without_an_action_word(client, monkeypatch):
    fake_sarvam(monkeypatch, intent="credit", entity_text="Raju", amount_text="50 rupaye", confidence=0.95)
    result = interpret(client, "Raju ko 50 rupaye add karo")
    assert result["status"] == "clarification" and "udhaar (credit given) or jama (payment received)" in result["message"]


@pytest.mark.parametrize("utterance,intent,entity,amount", [
    ("Raju ko pachaas rupaye udhaar add karo", "credit", "Raju", "pachaas rupaye"),
    ("Raju ka 50 rupaye udhar likho", "credit", "Raju", "50 rupaye"),
    ("Meena ne pachaas rupaye jama kiye", "repayment", "Meena", "pachaas rupaye"),
    ("Meena ne ₹75 wapas diye", "repayment", "Meena", "₹75"),
])
def test_explicit_hinglish_commands_are_ready(client, monkeypatch, utterance, intent, entity, amount):
    fake_sarvam(monkeypatch, intent=intent, entity_text=entity, amount_text=amount, confidence=0.93)
    result = interpret(client, utterance)
    assert (result["status"], result["intent"], result["entity_text"], result["amount_text"]) == ("ready", intent, entity, amount)


def test_missing_amount_message_is_specific(client, monkeypatch):
    fake_sarvam(monkeypatch, entity_text="Raju")
    result = interpret(client, "Raju ko udhaar add karo")
    assert result["message"].startswith("Please tell me the amount in rupees.")
