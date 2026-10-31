"""Offline checks for the voice-agent language helpers and Sarvam adapters."""

from app.services import agent_language as lang
from app.services import sarvam


def test_wake_phrase_and_yes_no():
    assert lang.strip_wake("Hey Munim ji, Ramesh ko 500 rupaye udhaar") == ("Ramesh ko 500 rupaye udhaar", True)
    assert lang.strip_wake("Ramesh ko 500 rupaye") == ("Ramesh ko 500 rupaye", False)
    assert lang.is_yes("haan ji") and lang.is_yes("theek hai") and not lang.is_yes("nahi")
    assert lang.is_no("nahi") and lang.is_no("cancel karo") and not lang.is_no("haan")


def test_spoken_amounts():
    assert lang.find_amount("dedh hazaar rupaye diye") == (150000, "dedh hazaar rupaye")
    assert lang.find_amount("saadhe teen sau")[0] == 35000
    assert lang.find_amount("do hazaar paanch sau")[0] == 250000
    assert lang.find_amount("₹1,200 jama") == (120000, "₹1,200")
    assert lang.find_amount("5 packet maggi") == (None, None)  # bare numbers are not money
    assert lang.find_bare_amount("700")[0] == 70000


def test_translate_modes(monkeypatch):
    assert sarvam.translate("Total 250", "en-IN").status == "SOURCE_LANGUAGE"
    assert sarvam.translate("Total 250", "hi-IN").text == "[Hindi] Total 250"  # fake mode from conftest
    monkeypatch.setenv("MUNIM_SARVAM_MODE", "off")
    assert sarvam.translate("Total 250", "hi-IN").status == "FALLBACK_SOURCE"


def test_live_translation_that_changes_numbers_is_discarded(monkeypatch):
    monkeypatch.setenv("MUNIM_SARVAM_MODE", "live")
    monkeypatch.setattr(sarvam, "_post", lambda *a, **k: {"translated_text": "कुल 2500"})
    result = sarvam.translate("Total 250", "hi-IN")
    assert result.status == "FALLBACK_SOURCE" and result.text == "Total 250"
    monkeypatch.setattr(sarvam, "_post", lambda *a, **k: {"translated_text": "कुल २५०"})
    assert sarvam.numbers_match("Total 250", "कुल २५०")  # Devanagari digits count as the same number


def test_fake_tts_is_wav_and_off_mode_refuses(monkeypatch):
    audio, provider = sarvam.synthesize("namaste")
    assert provider == "fake" and audio[:4] == b"RIFF"
    monkeypatch.setenv("MUNIM_SARVAM_MODE", "off")
    try:
        sarvam.synthesize("namaste")
        raise AssertionError("expected SpeechUnavailable")
    except sarvam.SpeechUnavailable:
        pass
