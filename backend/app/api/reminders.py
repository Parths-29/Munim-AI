"""Overdue-credit reminder consent, eligibility, approval, and mock outbox routes.

There is no real SMS/WhatsApp sending in this build. When ``MUNIM_ADMIN_TOKEN``
is set, run/send/receipt routes require it in the ``X-Munim-Admin-Token`` header.
"""

import hmac
import os
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from app.domain.reminders import (
    ConsentView,
    ConsentWrite,
    CustomerConsentSummary,
    EligibilityPreview,
    EligibilityRunResult,
    MockDeliveryReceipt,
    ReminderAction,
    ReminderApprove,
    ReminderView,
    ShopSettingsUpdate,
    ShopSettingsView,
)
from app.services import reminders as service

router = APIRouter(tags=["reminders"])


def require_admin(x_munim_admin_token: str | None = Header(default=None)) -> None:
    expected = os.environ.get("MUNIM_ADMIN_TOKEN", "").strip()
    if expected and not hmac.compare_digest(expected, (x_munim_admin_token or "").strip()):
        raise HTTPException(status_code=403, detail="Admin token required for this operation.")


@router.get("/reminders/settings", response_model=ShopSettingsView)
def get_settings_route() -> ShopSettingsView:
    return service.get_settings()


@router.post("/reminders/settings", response_model=ShopSettingsView)
def update_settings_route(request: ShopSettingsUpdate) -> ShopSettingsView:
    return service.update_settings(request)


@router.post("/customers/{customer_id}/reminder-consent", response_model=ConsentView, status_code=status.HTTP_201_CREATED)
def record_consent_route(customer_id: str, request: ConsentWrite) -> ConsentView:
    """Merchant-recorded consent evidence. Opt-in is never inferred."""
    return service.record_consent(customer_id, request)


@router.get("/customers/{customer_id}/reminder-consent", response_model=CustomerConsentSummary)
def get_consent_route(customer_id: str) -> CustomerConsentSummary:
    return service.get_consent(customer_id)


@router.get("/reminders/eligibility/preview", response_model=EligibilityPreview)
def preview_route(as_of: datetime | None = Query(default=None)) -> EligibilityPreview:
    """Read-only: who would be eligible and why not, with FIFO aging details."""
    return service.preview_eligibility(as_of)


@router.post("/reminders/eligibility/run", response_model=EligibilityRunResult, dependencies=[Depends(require_admin)])
def run_route(as_of: datetime | None = Query(default=None)) -> EligibilityRunResult:
    """Create reminders awaiting merchant approval. Idempotent per debt; never sends anything."""
    return service.run_eligibility(as_of)


@router.get("/reminders", response_model=list[ReminderView])
def list_route(status_filter: str | None = Query(default=None, alias="status"), limit: int = Query(default=50, ge=1, le=200)) -> list[ReminderView]:
    return service.list_reminders(status_filter, limit)


@router.get("/reminders/{reminder_id}", response_model=ReminderView)
def get_route(reminder_id: str) -> ReminderView:
    return service.get_reminder(reminder_id)


@router.post("/reminders/{reminder_id}/approve", response_model=ReminderView)
def approve_route(reminder_id: str, request: ReminderApprove) -> ReminderView:
    return service.approve_reminder(reminder_id, request)


@router.post("/reminders/{reminder_id}/cancel", response_model=ReminderView)
def cancel_route(reminder_id: str, request: ReminderAction) -> ReminderView:
    return service.cancel_reminder(reminder_id, request)


@router.post("/reminders/{reminder_id}/mock-send", response_model=ReminderView, dependencies=[Depends(require_admin)])
def mock_send_route(reminder_id: str, request: ReminderAction) -> ReminderView:
    """Records a simulated send only. No message reaches any phone."""
    return service.mock_send(reminder_id, request)


@router.post("/reminders/{reminder_id}/mock-delivery-receipt", response_model=ReminderView, dependencies=[Depends(require_admin)])
def mock_delivery_route(reminder_id: str, request: MockDeliveryReceipt) -> ReminderView:
    return service.record_mock_delivery(reminder_id, request)
