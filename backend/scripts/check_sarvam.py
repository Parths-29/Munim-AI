"""Live Sarvam check: Bulbul speaks a synthetic Hinglish sentence, then speech-to-text transcribes that audio.

Run from backend/:  python -m scripts.check_sarvam
Uses SARVAM_API_KEY from the environment or the ignored .env. Prints statuses only; never prints the key.
No real merchant/customer data is used and no audio is stored.
"""

import os
import time

from fastapi import HTTPException

from app.services import sarvam, speech

SENTENCE = "Raju bhai ka balance paanch sau rupaye hai."


def main() -> int:
    os.environ.setdefault("MUNIM_SARVAM_MODE", "live")
    print(f"key configured: {speech._api_key() is not None}")
    started = time.time()
    try:
        result = sarvam.synthesize_speech(SENTENCE, "hi-IN", timeout=20)
    except sarvam.SpeechUnavailable as error:
        print(f"voice output:   FAILED - {error}")
        return 1
    print(f"voice output:   ok ({result.provider} {result.model}/{result.speaker}, {len(result.audio)} bytes, {time.time() - started:.1f}s)")
    started = time.time()
    try:
        transcript = speech.transcribe_audio(result.audio, "audio/wav")
    except HTTPException as error:
        print(f"speech-to-text: FAILED - HTTP {error.status_code}: {error.detail}")
        return 1
    print(f"speech-to-text: ok ({time.time() - started:.1f}s) -> {transcript.transcript!r} [{transcript.language_code}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
