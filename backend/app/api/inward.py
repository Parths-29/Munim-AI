"""Quick inward (informal deliveries) from a reviewed voice transcript or typed text."""

from fastapi import APIRouter, status

from app.domain.intake import (
    InwardInterpretRequest,
    InwardInterpretResponse,
    ProposalConfirm,
    ProposalReject,
    ProposalRevise,
    ProposalView,
    ReceiptView,
)
from app.services.inward import create_inward_proposal
from app.services.proposals import INWARD_KINDS, get_proposal, reject_proposal, revise_proposal
from app.services.receipts import confirm_proposal

router = APIRouter(prefix="/inventory/inward", tags=["inventory"])


@router.post("/proposals", response_model=InwardInterpretResponse)
def create_inward_proposal_route(request: InwardInterpretRequest) -> InwardInterpretResponse:
    """Parse one delivery into a draft or a clarification question. Never writes stock."""
    return create_inward_proposal(request)


@router.get("/proposals/{proposal_id}", response_model=ProposalView)
def get_inward_proposal_route(proposal_id: str) -> ProposalView:
    return get_proposal(proposal_id, INWARD_KINDS)


@router.post("/proposals/{proposal_id}/revise", response_model=ProposalView)
def revise_inward_proposal_route(proposal_id: str, request: ProposalRevise) -> ProposalView:
    return revise_proposal(proposal_id, request, INWARD_KINDS)


@router.post("/proposals/{proposal_id}/reject", response_model=ProposalView)
def reject_inward_proposal_route(proposal_id: str, request: ProposalReject) -> ProposalView:
    return reject_proposal(proposal_id, request, INWARD_KINDS)


@router.post("/proposals/{proposal_id}/confirm", response_model=ReceiptView, status_code=status.HTTP_201_CREATED)
def confirm_inward_proposal_route(proposal_id: str, request: ProposalConfirm) -> ReceiptView:
    return confirm_proposal(proposal_id, request, INWARD_KINDS)
