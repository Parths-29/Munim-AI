"""Voice transcription endpoint; audio is forwarded to Sarvam and not stored."""

from fastapi import APIRouter, File, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app.domain.models import SpeechTranscriptionView
from app.services.speech import MAX_AUDIO_BYTES, transcribe_audio

router = APIRouter(prefix="/speech", tags=["voice"])
SUPPORTED_AUDIO_TYPES = {
    "audio/aac", "audio/mp4", "audio/m4a", "audio/mpeg", "audio/ogg",
    "audio/wav", "audio/webm", "audio/x-m4a", "audio/3gpp",
}


@router.post("/transcribe", response_model=SpeechTranscriptionView)
async def transcribe_route(file: UploadFile = File(...)) -> SpeechTranscriptionView:
    media_type = (file.content_type or "").lower()
    if media_type not in SUPPORTED_AUDIO_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported audio format. Record in WAV or M4A format.")
    audio = await file.read(MAX_AUDIO_BYTES + 1)
    await file.close()
    return await run_in_threadpool(transcribe_audio, audio, media_type)
