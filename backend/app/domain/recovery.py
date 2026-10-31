"""Models for the N8 recovery concierge: due explanation, localized draft, UPI link, reference matching.

Nothing here sends a message. Reminders still go through merchant approval and the mock outbox.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from app.domain.models import StrictModel
from app.domain.reminders import Channel, OpenCredit, ReminderStatus

UPI_VPA_PATTERN = r"^[A-Za-z0-9._-]{2,64}@[A-Za-z][A-Za-z0-9]{1,63}$"


class PaymentProfileWrite(StrictModel):
    upi_vpa: str = Field(pattern=UPI_VPA_PATTERN, max_length=129)
    payee_name: str = Field(min_length=2, max_length=60)
    confirmed: bool


class PaymentProfileView(StrictModel):
    shop_id: str
    upi_vpa: str
    payee_name: str
    updated_at: datetime


class LanguagePreferenceWrite(StrictModel):
    language_code: str = Field(min_length=5, max_length=5)
    confirmed: bool


class LanguagePreferenceView(StrictModel):
    customer_id: str
    language_code: str
    language_name: str
    is_default: bool


class RecoveryDraft(StrictModel):
    source_language: Literal["en-IN"] = "en-IN"
    source_text: str
    language_code: str
    text: str
    translation_status: Literal["TRANSLATED", "SOURCE_LANGUAGE", "FALLBACK_SOURCE"]
    translation_provider: str
    include_amount: bool
    numbers_verified: bool


class PaymentLinkPreview(StrictModel):
    available: bool
    upi_vpa: str | None
    payee_name: str | None
    note: str


class CollectionRequestView(StrictModel):
    request_id: str
    customer_id: str
    reminder_id: str | None
    reference: str
    amount_paise: int | None
    balance_at_request_paise: int
    paid_paise: int
    status: Literal["OPEN", "PART_PAID", "PAID"]
    upi_link: str
    created_at: datetime


class ActiveReminderSummary(StrictModel):
    reminder_id: str
    status: ReminderStatus


class RecoveryBrief(StrictModel):
    customer_id: str
    display_name: str
    as_of: datetime
    balance_due_paise: int
    overdue_threshold_days: int
    overdue_days: int | None
    oldest_unpaid_local_date: date | None
    open_credits: list[OpenCredit]
    explanation: str
    eligible: bool
    reasons: list[str]
    reason_explanations: list[str]
    channel: Channel | None
    contact_masked: str | None
    active_reminder: ActiveReminderSummary | None
    draft: RecoveryDraft
    payment_link: PaymentLinkPreview
    collection_requests: list[CollectionRequestView]
    approve_payload: dict
    mock_only: Literal[True] = True
