"""Supplier invoice / delivery-bill proposals. Drafts never write stock or payables."""

from fastapi import APIRouter, File, Form, Query, UploadFile, status
from starlette.concurrency import run_in_threadpool

from app.domain.intake import (
    ManualInvoiceCreate,
    ProposalConfirm,
    ProposalReject,
    ProposalRevise,
    ProposalView,
    ReceiptView,
)
from app.services.image_validation import max_image_bytes
from app.services.proposals import (
    INVOICE_KINDS,
    create_invoice_proposal_from_image,
    create_manual_invoice_proposal,
    get_proposal,
    list_proposals,
    reject_proposal,
    revise_proposal,
)
from app.services.receipts import confirm_proposal, get_receipt

router = APIRouter(tags=["invoices"])


@router.post("/invoices/proposals", response_model=ProposalView, status_code=status.HTTP_201_CREATED)
async def create_invoice_proposal_route(
    file: UploadFile = File(...),
    idempotency_key: str = Form(min_length=8, max_length=150),
    supplier_id: str | None = Form(default=None, max_length=100),
) -> ProposalView:
    """Upload a bill photo (JPEG/PNG/WebP). Returns an editable draft; the image is not retained."""
    try:
        image = await file.read(max_image_bytes() + 1)
        content_type = file.content_type
    finally:
        await file.close()  # releases Starlette's spooled temporary file
    return await run_in_threadpool(create_invoice_proposal_from_image, image, content_type, idempotency_key, supplier_id or None)


@router.post("/invoices/proposals/manual", response_model=ProposalView, status_code=status.HTTP_201_CREATED)
def create_manual_invoice_route(request: ManualInvoiceCreate) -> ProposalView:
    return create_manual_invoice_proposal(request)


@router.get("/invoices/proposals", response_model=list[ProposalView])
def list_invoice_proposals_route(
    status_filter: str | None = Query(default=None, alias="status"), limit: int = Query(default=50, ge=1, le=100),
) -> list[ProposalView]:
    return list_proposals(INVOICE_KINDS, status_filter, limit)


@router.get("/invoices/proposals/{proposal_id}", response_model=ProposalView)
def get_invoice_proposal_route(proposal_id: str) -> ProposalView:
    return get_proposal(proposal_id, INVOICE_KINDS)


@router.post("/invoices/proposals/{proposal_id}/revise", response_model=ProposalView)
def revise_invoice_proposal_route(proposal_id: str, request: ProposalRevise) -> ProposalView:
    return revise_proposal(proposal_id, request, INVOICE_KINDS)


@router.post("/invoices/proposals/{proposal_id}/reject", response_model=ProposalView)
def reject_invoice_proposal_route(proposal_id: str, request: ProposalReject) -> ProposalView:
    return reject_proposal(proposal_id, request, INVOICE_KINDS)


@router.post("/invoices/proposals/{proposal_id}/confirm", response_model=ReceiptView, status_code=status.HTTP_201_CREATED)
def confirm_invoice_proposal_route(proposal_id: str, request: ProposalConfirm) -> ReceiptView:
    return confirm_proposal(proposal_id, request, INVOICE_KINDS)


@router.get("/receipts/{receipt_id}", response_model=ReceiptView)
def get_receipt_route(receipt_id: str) -> ReceiptView:
    return get_receipt(receipt_id)
