"""Models for consent-aware overdue-credit reminders (mock delivery only)."""

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from app.domain.models import StrictModel

Channel = Literal["sms", "whatsapp"]
ReminderStatus = Literal[
    "PENDING_APPROVAL", "APPROVED_MOCK", "SENT_MOCK", "DELIVERED_MOCK", "FAILED_MOCK", "CANCELLED", "BLOCKED_OPTED_OUT",
]


class ShopSettingsView(StrictModel):
    shop_id: str
    timezone: str
    reminder_overdue_days: int
    quiet_hours_start: str
    quiet_hours_end: str
    reminder_min_interval_days: int
    max_mock_sends_per_day: int
    notification_provider: Literal["mock"] = "mock"
    updated_at: datetime


class ShopSettingsUpdate(StrictModel):
    timezone: str = Field(default="Asia/Kolkata", max_length=64)
    reminder_overdue_days: int = Field(default=15, strict=True, ge=1, le=365)
    quiet_hours_start: str = Field(default="21:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    quiet_hours_end: str = Field(default="09:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    reminder_min_interval_days: int = Field(default=7, strict=True, ge=1, le=90)
    max_mock_sends_per_day: int = Field(default=20, strict=True, ge=1, le=500)
    confirmed: bool


class ConsentWrite(StrictModel):
    channel: Channel
    consent_status: Literal["OPTED_IN", "OPTED_OUT"]
    contact_value: str | None = Field(default=None, max_length=20)
    contact_verified: bool = False
    verification_method: str | None = Field(default=None, max_length=80)
    evidence_note: str = Field(min_length=5, max_length=200)
    confirmed: bool
    idempotency_key: str = Field(min_length=8, max_length=150)


class ConsentView(StrictModel):
    consent_id: str
    customer_id: str
    channel: Channel
    consent_status: Literal["OPTED_IN", "OPTED_OUT"]
    contact_masked: str | None
    contact_verified: bool
    verification_method: str | None
    evidence_note: str
    recorded_at: datetime
    usable_for_reminders: bool


class CustomerConsentSummary(StrictModel):
    customer_id: str
    channels: list[ConsentView]
    record_count: int


class OpenCredit(StrictModel):
    entry_id: str
    created_at: datetime
    local_date: date
    original_paise: int
    remaining_paise: int


class EligibilityRow(StrictModel):
    customer_id: str
    display_name: str
    balance_due_paise: int
    oldest_unpaid_since: datetime | None
    oldest_unpaid_local_date: date | None
    overdue_days: int | None
    open_credits: list[OpenCredit]
    eligible: bool
    reasons: list[str]
    channel: Channel | None
    contact_masked: str | None


class EligibilityPreview(StrictModel):
    as_of: datetime
    timezone: str
    overdue_threshold_days: int
    policy: str
    rows: list[EligibilityRow]


class TransitionView(StrictModel):
    to_status: ReminderStatus
    reason: str
    actor: str
    provider: str | None
    provider_message_id: str | None
    created_at: datetime


class ReminderView(StrictModel):
    reminder_id: str
    customer_id: str
    display_name: str
    channel: Channel
    contact_masked: str | None
    status: ReminderStatus
    outstanding_at_eligibility_paise: int
    current_balance_paise: int
    oldest_unpaid_local_date: date
    overdue_days_at_eligibility: int
    eligibility_reason: str
    message_preview: str
    include_amount: bool
    mock_only: Literal[True] = True
    delivered_to_real_recipient: Literal[False] = False
    created_at: datetime
    transitions: list[TransitionView]


class EligibilityRunResult(StrictModel):
    as_of: datetime
    created: list[ReminderView]
    cancelled_reminder_ids: list[str]
    skipped_by_reason: dict[str, int]


class ReminderApprove(StrictModel):
    confirmed: bool
    include_amount: bool = False
    idempotency_key: str = Field(min_length=8, max_length=150)


class ReminderAction(StrictModel):
    confirmed: bool
    idempotency_key: str = Field(min_length=8, max_length=150)
    reason: str | None = Field(default=None, max_length=200)


class MockDeliveryReceipt(StrictModel):
    outcome: Literal["DELIVERED", "FAILED"]
    idempotency_key: str = Field(min_length=8, max_length=150)
