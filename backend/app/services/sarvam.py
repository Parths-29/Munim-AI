"""Sarvam translate (Mayura) and text-to-speech (Bulbul) adapters, server-side only.

``MUNIM_SARVAM_MODE``: ``live`` (default when SARVAM_API_KEY is set), ``fake``
(deterministic, offline), or ``off``. Translations must preserve every number in
the source text; otherwise the source text is used. Audio is generated on demand
and never stored.
"""

import base64
import io
import json
import logging
import math
import os
import re
import struct
import urllib.error
import urllib.request
import wave
from dataclasses import dataclass

from app.services.speech import _api_key

logger = logging.getLogger(__name__)

LANGUAGES = {
    "en-IN": "English", "hi-IN": "Hindi", "mr-IN": "Marathi", "gu-IN": "Gujarati", "bn-IN": "Bengali",
    "ta-IN": "Tamil", "te-IN": "Telugu", "kn-IN": "Kannada", "ml-IN": "Malayalam", "pa-IN": "Punjabi", "od-IN": "Odia",
}
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


@dataclass
class TranslationResult:
    text: str
    language_code: str
    status: str          # TRANSLATED | SOURCE_LANGUAGE | FALLBACK_SOURCE
    provider: str


def _mode() -> str:
    mode = os.environ.get("MUNIM_SARVAM_MODE", "").strip().lower()
    if mode in {"live", "fake", "off"}:
        return mode
    return "live" if _api_key() else "off"


def _numbers(text: str) -> list[str]:
    return sorted(n.replace(",", "") for n in NUMBER.findall(text))


def _post(url: str, payload: dict, timeout: float) -> dict:
    request = urllib.request.Request(
        url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"api-subscription-key": _api_key() or "", "Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def translate(text: str, target_language: str, source_language: str = "en-IN") -> TranslationResult:
    if target_language not in LANGUAGES:
        target_language = "en-IN"
    if target_language == source_language or target_language == "en-IN":
        return TranslationResult(text, source_language, "SOURCE_LANGUAGE", "none")
    mode = _mode()
    if mode == "off":
        return TranslationResult(text, source_language, "FALLBACK_SOURCE", "off")
    if mode == "fake":
        return TranslationResult(f"[{LANGUAGES[target_language]}] {text}", target_language, "TRANSLATED", "fake")
    try:
        body = _post("https://api.sarvam.ai/translate", {
            "input": text, "source_language_code": source_language, "target_language_code": target_language,
            "model": os.environ.get("SARVAM_TRANSLATE_MODEL", "mayura:v1"), "mode": "formal",
            "numerals_format": "international",
        }, timeout=10)
        translated = body.get("translated_text")
        if not isinstance(translated, str) or not translated.strip():
            raise ValueError("empty translation")
        if _numbers(translated) != _numbers(text):
            logger.warning("Sarvam translation changed numbers; using source text.")
            return TranslationResult(text, source_language, "FALLBACK_SOURCE", "sarvam")
        return TranslationResult(translated.strip(), target_language, "TRANSLATED", "sarvam")
    except Exception as error:
        logger.warning("Sarvam translate unavailable (%s).", type(error).__name__)
        return TranslationResult(text, source_language, "FALLBACK_SOURCE", "sarvam")


class SpeechUnavailable(Exception):
    pass


def _fake_wav(text: str) -> bytes:
    """Short synthetic tone (length scales with text). Clearly not speech; offline demos/tests only."""
    rate, seconds = 8000, min(0.4 + len(text) / 60, 3.0)
    frames = b"".join(struct.pack("<h", int(6000 * math.sin(2 * math.pi * 440 * i / rate))) for i in range(int(rate * seconds)))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(frames)
    return buffer.getvalue()


TTS_DEFAULT_MODEL = "bulbul:v3"
TTS_DEFAULT_SPEAKERS = {"bulbul:v3": "shubh", "bulbul:v2": "anushka", "bulbul:v4-flash": "shubh_enhi_ads"}
TTS_FALLBACK_MODEL = "bulbul:v2"
TTS_TEXT_LIMITS = {"bulbul:v2": 1500}


@dataclass
class SpeechResult:
    audio: bytes
    provider: str
    model: str | None
    speaker: str | None
    language_code: str


def _tts_request(text: str, language_code: str, model: str, speaker: str | None, timeout: float) -> bytes:
    payload = {"text": text[: TTS_TEXT_LIMITS.get(model, 2500)], "language_code": language_code, "model": model}
    if speaker:
        payload["speaker"] = speaker
    body = _post("https://api.sarvam.ai/text-to-speech", payload, timeout=timeout)
    audios = body.get("audios")
    if not isinstance(audios, list) or not audios or not isinstance(audios[0], str):
        raise ValueError("no audio in response")
    return base64.b64decode(audios[0])


def synthesize_speech(text: str, language_code: str = "en-IN", timeout: float = 20) -> SpeechResult:
    """Speak already-verified text. Audio is returned to the caller and never stored.

    SARVAM_TTS_MODEL (default bulbul:v3) and SARVAM_TTS_SPEAKER are configurable. If the account rejects the
    configured model (HTTP 400/403/422), one retry uses bulbul:v2 with its default voice. Timeouts and outages
    are not retried.
    """
    text = " ".join(text.split())
    if not text:
        raise SpeechUnavailable("Nothing to speak.")
    language_code = language_code if language_code in LANGUAGES else "en-IN"
    mode = _mode()
    if mode == "off":
        raise SpeechUnavailable("Voice output is not configured: set SARVAM_API_KEY in the backend's ignored .env.")
    if mode == "fake":
        return SpeechResult(_fake_wav(text), "fake", None, None, language_code)
    model = (os.environ.get("SARVAM_TTS_MODEL") or TTS_DEFAULT_MODEL).strip()
    speaker = (os.environ.get("SARVAM_TTS_SPEAKER") or TTS_DEFAULT_SPEAKERS.get(model, "")).strip() or None
    attempts = [(model, speaker)]
    if model != TTS_FALLBACK_MODEL:
        attempts.append((TTS_FALLBACK_MODEL, TTS_DEFAULT_SPEAKERS[TTS_FALLBACK_MODEL]))
    last_error = "unknown"
    for index, (attempt_model, attempt_speaker) in enumerate(attempts):
        try:
            audio = _tts_request(text, language_code, attempt_model, attempt_speaker, timeout)
            return SpeechResult(audio, "sarvam", attempt_model, attempt_speaker, language_code)
        except urllib.error.HTTPError as error:
            logger.warning("Sarvam TTS HTTP %s for model %s.", error.code, attempt_model)
            last_error = f"HTTP {error.code}"
            if error.code in (400, 403, 422) and index + 1 < len(attempts):
                continue
            if error.code in (401, 403):
                raise SpeechUnavailable("Sarvam rejected the API key for voice output. Update SARVAM_API_KEY in the ignored .env.") from None
            if error.code == 429:
                raise SpeechUnavailable("Sarvam voice output quota or rate limit reached. The text reply is still shown.") from None
            raise SpeechUnavailable(f"Sarvam voice output failed ({last_error}). The text reply is still shown.") from None
        except Exception as error:
            logger.warning("Sarvam TTS unavailable (%s).", type(error).__name__)
            raise SpeechUnavailable("Sarvam voice output is unreachable or timed out. The text reply is still shown.") from None
    raise SpeechUnavailable(f"Sarvam voice output failed ({last_error}).")


def synthesize(text: str, language_code: str = "hi-IN") -> tuple[bytes, str]:
    """Backward-compatible wrapper: (wav_bytes, provider)."""
    result = synthesize_speech(text, language_code)
    return result.audio, result.provider
