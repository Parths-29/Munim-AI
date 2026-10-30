"""Short, server-side Sarvam speech transcription; audio is never persisted."""

import json
import os
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from fastapi import HTTPException

from app.domain.models import SpeechTranscriptionView

SARVAM_URL = "https://api.sarvam.ai/speech-to-text"
MAX_AUDIO_BYTES = 12 * 1024 * 1024
KEYTERMS = ["Munim-AI", "Raju bhai", "udhaar", "jamma", "Maggi", "Paytm"]
FILE_EXTENSIONS = {
    "audio/aac": ".aac", "audio/mp4": ".m4a", "audio/m4a": ".m4a",
    "audio/mpeg": ".mp3", "audio/ogg": ".ogg", "audio/wav": ".wav",
    "audio/webm": ".webm", "audio/x-m4a": ".m4a", "audio/3gpp": ".3gp",
}


def _api_key() -> str | None:
    key = os.environ.get("SARVAM_API_KEY")
    if key:
        return key.strip().strip("\"'")
    root = Path(__file__).resolve().parents[3]
    for path in (root / ".env", root / "backend" / ".env", Path(".env")):
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("SARVAM_API_KEY="):
                    return line.split("=", 1)[1].strip().strip("\"'") or None
        except (OSError, UnicodeError):
            continue
    return None


def transcribe_audio(audio: bytes, content_type: str) -> SpeechTranscriptionView:
    if not audio:
        raise HTTPException(status_code=400, detail="Audio recording is empty.")
    if len(audio) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio exceeds the 12 MB upload limit.")
    key = _api_key()
    if not key:
        raise HTTPException(status_code=503, detail="Voice transcription is not configured. Set SARVAM_API_KEY on the backend.")

    extension = FILE_EXTENSIONS.get(content_type, ".m4a")
    filename = f"merchant-voice{extension}"
    boundary = f"MunimBoundary{uuid.uuid4().hex}"
    fields = {
        "model": "saaras:v4",
        # Transliterated Hindi/Hinglish matches the existing Latin-script command parser.
        "mode": "translit",
        "keyterms": json.dumps(KEYTERMS, ensure_ascii=False),
    }
    parts = []
    for name, value in fields.items():
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()
        )
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
        f"Content-Type: {content_type}\r\n\r\n".encode()
        + audio + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    request = urllib.request.Request(
        SARVAM_URL,
        data=b"".join(parts),
        headers={
            "api-subscription-key": key,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise HTTPException(status_code=429, detail="Sarvam transcription rate limit reached. Try again shortly.") from None
        if exc.code in (400, 422):
            raise HTTPException(status_code=422, detail="Sarvam could not process this audio. Try a clear recording under 20 seconds.") from None
        if exc.code in (401, 403):
            raise HTTPException(status_code=503, detail="Sarvam rejected the backend voice credentials. Check SARVAM_API_KEY.") from None
        raise HTTPException(status_code=503, detail="Sarvam voice transcription is temporarily unavailable.") from None
    except (TimeoutError, urllib.error.URLError, json.JSONDecodeError):
        raise HTTPException(status_code=503, detail="Sarvam voice transcription timed out or returned an invalid response.") from None

    transcript = payload.get("transcript")
    if not isinstance(transcript, str) or not transcript.strip():
        raise HTTPException(status_code=422, detail="No speech was detected. Try again or type the request.")
    return SpeechTranscriptionView(
        transcript=transcript.strip(),
        language_code=payload.get("language_code"),
        request_id=payload.get("request_id"),
    )
