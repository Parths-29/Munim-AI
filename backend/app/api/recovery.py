"""N8 recovery concierge routes. Read-only brief plus merchant-confirmed settings; nothing here sends a message."""

from datetime import datetime

from fastapi import APIRouter, Query

from app.domain.recovery import (
    CollectionRequestView,
    LanguagePreferenceView,
    LanguagePreferenceWrite,
    PaymentProfileView,
    PaymentProfileWrite,
    RecoveryBrief,
)
from app.services import recovery as service

router = APIRouter(tags=["recovery"])


@router.get("/recovery/payment-profile", response_model=PaymentProfileView)
def get_payment_profile_route() -> PaymentProfileView:
    return service.get_payment_profile()


@router.post("/recovery/payment-profile", response_model=PaymentProfileView)
def set_payment_profile_route(request: PaymentProfileWrite) -> PaymentProfileView:
    """The shop's own UPI ID, used only inside pay links that the customer opens themselves."""
    return service.set_payment_profile(request)


@router.get("/customers/{customer_id}/language", response_model=LanguagePreferenceView)
def get_language_route(customer_id: str) -> LanguagePreferenceView:
    return service.get_language(customer_id)


@router.post("/customers/{customer_id}/language", response_model=LanguagePreferenceView)
def set_language_route(customer_id: str, request: LanguagePreferenceWrite) -> LanguagePreferenceView:
    return service.set_language(customer_id, request)


@router.get("/customers/{customer_id}/recovery-brief", response_model=RecoveryBrief)
def recovery_brief_route(
    customer_id: str,
    language: str | None = Query(default=None, description="Override the customer's saved language, e.g. hi-IN."),
    include_amount: bool = Query(default=True),
    as_of: datetime | None = Query(default=None),
) -> RecoveryBrief:
    """Why this customer owes money, whether a reminder is allowed, and a localized draft to review. Writes nothing."""
    return service.recovery_brief(customer_id, language, include_amount, as_of)


@router.get("/customers/{customer_id}/collection-requests", response_model=list[CollectionRequestView])
def collection_requests_route(customer_id: str) -> list[CollectionRequestView]:
    return service.list_collection_requests(customer_id)
