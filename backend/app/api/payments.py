"""Mock-only payment event intake and reconciliation review queue."""

from fastapi import APIRouter, Query, status

from app.domain.models import (
    PaymentAllocationCreate,
    PaymentAllocationView,
    PaymentIntakeCreate,
    PaymentIntakeView,
    PaymentReviewView,
    PayerMappingCreate,
    PayerMappingView,
)
from app.services.payments import create_payer_mapping, intake_payment, list_payment_review, manually_allocate_payment

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/payer-mappings", response_model=PayerMappingView, status_code=status.HTTP_201_CREATED)
def create_payer_mapping_route(request: PayerMappingCreate) -> PayerMappingView:
    return create_payer_mapping(request)


@router.post("/intake", response_model=PaymentIntakeView, status_code=status.HTTP_201_CREATED)
def intake_payment_route(request: PaymentIntakeCreate) -> PaymentIntakeView:
    return intake_payment(request)


@router.get("/review", response_model=list[PaymentReviewView])
def payment_review_route(limit: int = Query(default=50, ge=1, le=100)) -> list[PaymentReviewView]:
    return list_payment_review(limit)


@router.post("/{event_id}/allocate", response_model=PaymentAllocationView)
def allocate_reviewed_payment_route(event_id: str, request: PaymentAllocationCreate) -> PaymentAllocationView:
    return manually_allocate_payment(event_id, request)
