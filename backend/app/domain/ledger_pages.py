"""Models for bahi-khata (handwritten udhaar notebook) page proposals."""

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from app.domain.intake import ExtractionView, Issue
from app.domain.models import CustomerView, StrictModel

EntryType = Literal["CREDIT", "REPAYMENT"]


class PageLine(StrictModel):
    line_id: str
    source_text: str | None = Field(default=None, max_length=240)
    name_text: str | None = Field(default=None, max_length=100)        # as written (any script)
    name_latin: str | None = Field(default=None, max_length=100)       # transliteration, if provided
    customer_id: str | None = None
    create_customer: bool = False
    amount_paise: int | None = Field(default=None, ge=0)
    entry_type: EntryType | None = None
    entry_date: date | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    merchant_verified: bool = False
    accepted: bool = True
    parse_notes: list[str] = Field(default_factory=list)


class PageDraft(StrictModel):
    language_hint: str | None = Field(default=None, max_length=20)
    lines: list[PageLine] = Field(default_factory=list, max_length=60)


class PageLineView(StrictModel):
    line_id: str
    source_text: str | None
    name_text: str | None
    name_latin: str | None
    matched_customer_id: str | None
    match_status: Literal["MATCHED", "SELECTED", "AMBIGUOUS", "NOT_FOUND", "WILL_CREATE", "NOT_PROVIDED"]
    candidates: list[CustomerView]
    amount_paise: int | None
    entry_type: EntryType | None
    entry_date: date | None
    confidence: float | None
    merchant_verified: bool
    accepted: bool
    issues: list[Issue]


class PageTotals(StrictModel):
    accepted_lines: int
    credit_total_paise: int
    repayment_total_paise: int
    customers_to_create: int


class PageView(StrictModel):
    proposal_id: str
    status: Literal["NEEDS_REVIEW", "READY", "CONFIRMED", "REJECTED", "EXPIRED"]
    version: int
    content_hash: str
    language_hint: str | None
    lines: list[PageLineView]
    issues: list[Issue]
    totals: PageTotals
    ready_to_confirm: bool
    warnings_require_acknowledgement: bool
    image_retained: Literal[False] = False
    extraction: ExtractionView
    posted_batch_id: str | None
    created_at: datetime
    updated_at: datetime
    expires_at: datetime


class PageLineEdit(StrictModel):
    line_id: str | None = Field(default=None, max_length=40)
    name_text: str | None = Field(default=None, max_length=100)
    name_latin: str | None = Field(default=None, max_length=100)
    customer_id: str | None = Field(default=None, max_length=100)
    create_customer: bool = False
    amount_paise: int | None = Field(default=None, strict=True, gt=0)
    entry_type: EntryType | None = None
    entry_date: date | None = None
    merchant_verified: bool = True
    accepted: bool = True


class PageRevise(StrictModel):
    expected_version: int = Field(strict=True, ge=1)
    language_hint: str | None = Field(default=None, max_length=20)
    lines: list[PageLineEdit] = Field(max_length=60)


class PageVoiceCorrection(StrictModel):
    expected_version: int = Field(strict=True, ge=1)
    utterance: str = Field(min_length=1, max_length=240)


class PageVoiceCorrectionResult(StrictModel):
    status: Literal["applied", "clarification"]
    message: str
    matched_line_id: str | None
    proposal: PageView


class PageConfirm(StrictModel):
    expected_version: int = Field(strict=True, ge=1)
    content_hash: str = Field(min_length=64, max_length=64)
    acknowledge_warnings: bool = False
    confirmed: bool
    idempotency_key: str = Field(min_length=8, max_length=150)


class PageReject(StrictModel):
    expected_version: int = Field(strict=True, ge=1)
    confirmed: bool


class PagePostedEntry(StrictModel):
    line_id: str
    entry_id: str
    customer_id: str
    display_name: str
    entry_type: EntryType
    amount_paise: int
    occurred_on: date | None
    customer_created: bool
    balance_after_paise: int


class PagePostingView(StrictModel):
    batch_id: str
    proposal_id: str
    entries: list[PagePostedEntry]
    customers_created: int
    created_at: datetime
    idempotent_replay: bool = False
