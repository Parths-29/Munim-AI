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
FILENAME_AUDIO_TYPES = {
    ".aac": "audio/aac", ".m4a": "audio/mp4", ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg", ".wav": "audio/wav", ".webm": "audio/webm",
    ".3gp": "audio/3gpp",
}


@router.post("/transcribe", response_model=SpeechTranscriptionView)
async def transcribe_route(file: UploadFile = File(...)) -> SpeechTranscriptionView:
    # Browser MediaRecorder may include codec parameters or report generic
    # binary/video WebM even when the payload is an audio-only WebM recording.
    media_type = (file.content_type or "").split(";", 1)[0].strip().lower()
    if media_type == "video/webm":
        media_type = "audio/webm"
    if media_type in {"application/octet-stream", "binary/octet-stream", ""}:
        filename_parts = (file.filename or "").rsplit(".", 1)
        filename_extension = f".{filename_parts[-1].lower()}" if len(filename_parts) == 2 else ""
        media_type = FILENAME_AUDIO_TYPES.get(filename_extension, media_type)
    if media_type not in SUPPORTED_AUDIO_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported audio format. Use a browser WebM recording or WAV/M4A audio.")
    audio = await file.read(MAX_AUDIO_BYTES + 1)
    await file.close()
    return await run_in_threadpool(transcribe_audio, audio, media_type)
