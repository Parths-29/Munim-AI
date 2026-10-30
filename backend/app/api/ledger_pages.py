"""Bahi-khata notebook page scanner routes. Drafts never write the ledger."""

from fastapi import APIRouter, File, Form, UploadFile, status
from starlette.concurrency import run_in_threadpool

from app.domain.ledger_pages import (
    PageConfirm,
    PagePostingView,
    PageReject,
    PageRevise,
    PageView,
    PageVoiceCorrection,
    PageVoiceCorrectionResult,
)
from app.services import ledger_pages as service
from app.services.image_validation import max_image_bytes

router = APIRouter(prefix="/ledger-pages", tags=["bahi-khata"])


@router.post("", response_model=PageView, status_code=status.HTTP_201_CREATED)
async def scan_page_route(file: UploadFile = File(...), idempotency_key: str = Form(min_length=8, max_length=150)) -> PageView:
    """Photograph a notebook page; returns an editable ledger draft. The image is not retained."""
    try:
        image = await file.read(max_image_bytes() + 1)
        content_type = file.content_type
    finally:
        await file.close()
    return await run_in_threadpool(service.create_from_image, image, content_type, idempotency_key)


@router.get("/{proposal_id}", response_model=PageView)
def get_page_route(proposal_id: str) -> PageView:
    return service.get_page(proposal_id)


@router.post("/{proposal_id}/revise", response_model=PageView)
def revise_page_route(proposal_id: str, request: PageRevise) -> PageView:
    return service.revise_page(proposal_id, request)


@router.post("/{proposal_id}/voice-correction", response_model=PageVoiceCorrectionResult)
def voice_correction_route(proposal_id: str, request: PageVoiceCorrection) -> PageVoiceCorrectionResult:
    """Apply a reviewed spoken confirmation like 'Sharma ji, 1200' to the one matching row."""
    return service.voice_correction(proposal_id, request)


@router.post("/{proposal_id}/reject", response_model=PageView)
def reject_page_route(proposal_id: str, request: PageReject) -> PageView:
    return service.reject_page(proposal_id, request)


@router.post("/{proposal_id}/confirm", response_model=PagePostingView, status_code=status.HTTP_201_CREATED)
def confirm_page_route(proposal_id: str, request: PageConfirm) -> PagePostingView:
    return service.confirm_page(proposal_id, request)
