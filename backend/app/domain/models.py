"""Typed API models for the first customer/ledger slice."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CustomerCreate(StrictModel):
    display_name: str = Field(min_length=1, max_length=100)
    aliases: list[str] = Field(default_factory=list, max_length=12)
    confirmed: bool
    idempotency_key: str = Field(min_length=8, max_length=150)
    source_utterance: str | None = Field(default=None, max_length=240)
    source_channel: Literal["text", "voice", "provider_mock", "system"] = "text"


class CustomerView(StrictModel):
    customer_id: str
    display_name: str
    aliases: list[str]


class CustomerResolution(StrictModel):
    status: str
    query: str
    matches: list[CustomerView]


class LedgerWrite(StrictModel):
    customer_id: str = Field(min_length=1, max_length=100)
    amount_paise: int = Field(strict=True, gt=0)
    source_event_id: str = Field(min_length=1, max_length=120)
    idempotency_key: str = Field(min_length=8, max_length=150)
    confirmed: bool
    source_utterance: str | None = Field(default=None, max_length=240)
    source_channel: Literal["text", "voice", "provider_mock", "system"] = "text"


class LedgerEntryView(StrictModel):
    entry_id: str
    customer_id: str
    entry_type: str
    amount_paise: int
    status: str
    source_event_id: str
    created_at: datetime
    idempotent_replay: bool = False


class CustomerBalance(StrictModel):
    customer_id: str
    display_name: str
    balance_due_paise: int
    currency: str = "INR"
    entry_count: int


class ProductCreate(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    aliases: list[str] = Field(default_factory=list, max_length=12)
    unit: str = Field(min_length=1, max_length=32)
    confirmed: bool
    idempotency_key: str = Field(min_length=8, max_length=150)
    source_utterance: str | None = Field(default=None, max_length=240)
    source_channel: Literal["text", "voice", "provider_mock", "system"] = "text"


class ProductView(StrictModel):
    product_id: str
    name: str
    aliases: list[str]
    unit: str


class ProductResolution(StrictModel):
    status: str
    query: str
    matches: list[ProductView]


class StockoutObservationCreate(StrictModel):
    product_id: str = Field(min_length=1, max_length=100)
    source_event_id: str = Field(min_length=1, max_length=120)
    idempotency_key: str = Field(min_length=8, max_length=150)
    confirmed: bool
    source_utterance: str | None = Field(default=None, max_length=240)
    source_channel: Literal["text", "voice", "provider_mock", "system"] = "text"


class StockoutObservationView(StrictModel):
    observation_id: str
    product_id: str
    status: str = "OBSERVED"
    source_event_id: str
    created_at: datetime
    idempotent_replay: bool = False


class StockCountCreate(StrictModel):
    product_id: str = Field(min_length=1, max_length=100)
    counted_quantity: int = Field(strict=True, ge=0)
    source_event_id: str = Field(min_length=1, max_length=120)
    idempotency_key: str = Field(min_length=8, max_length=150)
    confirmed: bool
    source_utterance: str | None = Field(default=None, max_length=240)
    source_channel: Literal["text", "voice", "provider_mock", "system"] = "text"


class InventoryMovementView(StrictModel):
    movement_id: str
    product_id: str
    quantity_delta: int
    counted_quantity: int
    unit: str
    reason: str
    status: str
    source_event_id: str
    created_at: datetime
    idempotent_replay: bool = False


class StockBalanceView(StrictModel):
    product_id: str
    product_name: str
    on_hand_quantity: int
    unit: str
    movement_count: int


class BusinessEventView(StrictModel):
    event_id: str
    event_type: str
    entity_type: str
    entity_id: str
    source_event_id: str
    source_channel: str
    source_utterance: str | None
    status: str
    summary: str
    created_at: datetime


class RecentPaymentSummary(StrictModel):
    event_id: str
    amount_paise: int
    payment_status: Literal["SUCCESS", "PENDING", "FAILED", "REVERSED"]
    resolution_status: Literal["ALLOCATED", "REVIEW", "UNMATCHED", "IGNORED"]
    reason: str | None
    occurred_at: datetime


class ActivitySummaryView(StrictModel):
    data_mode: Literal["synthetic", "merchant_entered", "provider_mock"]
    period_label: str
    recorded_event_count: int
    credit_entry_count: int
    credit_total_paise: int
    repayment_entry_count: int
    repayment_total_paise: int
    payment_event_count: int
    successful_payment_count: int
    successful_payment_total_paise: int
    pending_payment_count: int
    pending_payment_total_paise: int
    failed_payment_count: int
    failed_payment_total_paise: int
    open_review_payment_count: int
    open_review_payment_total_paise: int
    reversed_payment_count: int
    reversed_payment_total_paise: int
    stockout_observation_count: int
    physical_count_event_count: int
    recent_payments: list[RecentPaymentSummary]
    latest_events: list[BusinessEventView]
    summary_text: str
    caveats: list[str]


class FactView(StrictModel):
    id: str
    label: str
    status: Literal["available", "unavailable", "needs_confirmation", "low_sample"]
    value: int | float | str | bool | None
    unit: str | None
    source: str
    count: int | None
    comparison_value: int | float | str | bool | None = None
    comparison_period: str | None = None
    definition: str | None = None
    reason_unavailable: str | None = None


class FactPeriod(StrictModel):
    start: datetime
    end: datetime
    timezone: str


class BusinessFactsView(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    shop_id: str
    data_mode: Literal["synthetic", "merchant_entered", "provider_mock"]
    period: FactPeriod
    facts: list[FactView]
    evidence_ids: list[str]
    caveats: list[str]
    allowed_actions: list[Literal["counter_notice", "qr_offer_mock", "review_payment", "confirm_stock_count"]]


class BriefExplanationRequest(StrictModel):
    persona: Literal["kirana", "tea_stall", "medical_store"] = "kirana"


class BriefExplanationResponse(StrictModel):
    explanation: str
    evidence_ids: list[str]
    proposed_action: str
    action_type: Literal["counter_notice", "qr_offer_mock"]
    fallback_used: bool
    validation_errors: list[str] = Field(default_factory=list)


class CommandInterpretRequest(StrictModel):
    utterance: str = Field(min_length=1, max_length=240)
    source_channel: Literal["text", "voice"] = "text"


class CommandInterpretResponse(StrictModel):
    status: Literal["ready", "clarification", "unavailable"]
    intent: Literal[
        "credit", "repayment", "balance", "customer_create", "stockout",
        "stock_check", "stock_count", "payment_summary", "timeline_summary",
    ] | None = None
    entity_text: str | None = None
    amount_text: str | None = None
    count_text: str | None = None
    confidence: float = Field(ge=0, le=1)
    message: str | None = None
    provider_used: Literal["gemini", "fallback"]
    fallback_used: bool


class MockActionCreate(StrictModel):
    persona: Literal["kirana", "tea_stall", "medical_store"] = "kirana"
    action_type: Literal["counter_notice", "qr_offer_mock"]
    action_text: str = Field(min_length=1, max_length=240)
    confirmed: bool
    idempotency_key: str = Field(min_length=8, max_length=150)


class MockActionView(StrictModel):
    action_id: str
    action_type: Literal["counter_notice", "qr_offer_mock"]
    action_text: str
    status: Literal["APPROVED_MOCK"]
    mock_only: Literal[True] = True
    created_at: datetime
    baseline_start: datetime
    baseline_end: datetime
    baseline_collections_paise: int
    baseline_transaction_count: int
    measurement_start: datetime
    measurement_end: datetime
    outcome_status: Literal["scheduled", "available", "insufficient_data"]
    outcome_collections_paise: int | None = None
    outcome_transaction_count: int | None = None
    collections_change_paise: int | None = None
    outcome_note: str


class SpeechTranscriptionView(StrictModel):
    transcript: str
    language_code: str | None = None
    request_id: str | None = None
    provider: Literal["sarvam"] = "sarvam"


class PayerMappingCreate(StrictModel):
    payer_token: str = Field(min_length=1, max_length=100)
    customer_id: str = Field(min_length=1, max_length=100)
    confirmed: bool
    idempotency_key: str = Field(min_length=8, max_length=150)


class PayerMappingView(StrictModel):
    mapping_id: str
    customer_id: str
    status: str


class PaymentIntakeCreate(StrictModel):
    event_id: str = Field(min_length=1, max_length=120)
    amount_paise: int = Field(strict=True, gt=0)
    status: Literal["SUCCESS", "PENDING", "FAILED", "REVERSED"]
    occurred_at: datetime
    idempotency_key: str = Field(min_length=8, max_length=150)
    payer_token: str | None = Field(default=None, max_length=100)
    source: Literal["provider_mock"] = "provider_mock"


class PaymentIntakeView(StrictModel):
    event_id: str
    amount_paise: int
    status: str
    resolution_status: str
    reason: str | None
    allocation_entry_id: str | None
    created_at: datetime
    idempotent_replay: bool = False


class PaymentReviewView(StrictModel):
    event_id: str
    amount_paise: int
    status: str
    resolution_status: str
    reason: str | None
    occurred_at: datetime
    created_at: datetime


class PaymentAllocationCreate(StrictModel):
    customer_id: str = Field(min_length=1, max_length=100)
    confirmed: bool
    idempotency_key: str = Field(min_length=8, max_length=150)


class PaymentAllocationView(StrictModel):
    event_id: str
    customer_id: str
    amount_paise: int
    allocation_entry_id: str
    status: Literal["ALLOCATED"] = "ALLOCATED"
    idempotent_replay: bool = False
