"""Typed models for stock-inflow proposals (invoice images, manual invoices, voice inward).

Draft models hold the merchant-editable content that is hashed and versioned.
View models add server-computed matching, unit resolution, and validation
issues. Model/OCR output never maps directly onto these: it is parsed into a
draft by deterministic code first.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from app.domain.models import ProductView, SourceChannel, StrictModel, SupplierView

ProposalStatus = Literal["NEEDS_REVIEW", "READY", "CONFIRMED", "REJECTED", "EXPIRED"]
SourceKind = Literal["invoice_image", "manual_invoice", "voice_inward", "text_inward"]
Severity = Literal["blocking", "warning", "info"]
Paise = int


# --- Stored draft (editable content) ----------------------------------------

class DraftSupplier(StrictModel):
    supplier_id: str | None = None
    label: str | None = Field(default=None, max_length=100)
    confidence: float | None = Field(default=None, ge=0, le=1)
    verified: bool = False


class DraftInvoice(StrictModel):
    invoice_number: str | None = Field(default=None, max_length=60)
    invoice_date: date | None = None
    subtotal_paise: Paise | None = Field(default=None, ge=0)
    tax_paise: Paise | None = Field(default=None, ge=0)
    discount_paise: Paise | None = Field(default=None, ge=0)
    freight_paise: Paise | None = Field(default=None, ge=0)
    other_charges_paise: Paise | None = Field(default=None, ge=0)
    rounding_paise: Paise | None = None
    total_paise: Paise | None = Field(default=None, ge=0)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    verified: bool = False


class DraftLine(StrictModel):
    line_id: str
    source_text: str | None = Field(default=None, max_length=240)
    product_name_text: str | None = Field(default=None, max_length=120)
    product_id: str | None = None
    quantity: int | None = None
    unit_text: str | None = Field(default=None, max_length=32)
    conversion_factor: int | None = Field(default=None, gt=0)
    unit_cost_paise: Paise | None = Field(default=None, ge=0)
    line_total_paise: Paise | None = Field(default=None, ge=0)
    confidence: float | None = Field(default=None, ge=0, le=1)
    merchant_verified: bool = False
    accepted: bool = True
    parse_notes: list[str] = Field(default_factory=list)


class DraftContent(StrictModel):
    supplier: DraftSupplier = Field(default_factory=DraftSupplier)
    invoice: DraftInvoice = Field(default_factory=DraftInvoice)
    lines: list[DraftLine] = Field(default_factory=list, max_length=100)


# --- Computed views ---------------------------------------------------------

class Issue(StrictModel):
    code: str
    severity: Severity
    message: str
    line_id: str | None = None
    field: str | None = None


class SupplierMatchView(StrictModel):
    label: str | None
    supplier_id: str | None
    match_status: Literal["RESOLVED", "SELECTED", "AMBIGUOUS", "NOT_FOUND", "NOT_PROVIDED"]
    candidates: list[SupplierView]
    confidence: float | None
    verified: bool


class InvoiceHeaderView(StrictModel):
    invoice_number: str | None
    invoice_date: date | None
    currency: Literal["INR"] = "INR"
    subtotal_paise: int | None
    tax_paise: int | None
    discount_paise: int | None
    freight_paise: int | None
    other_charges_paise: int | None
    rounding_paise: int | None
    total_paise: int | None
    field_confidence: dict[str, float]
    verified: bool


class LineView(StrictModel):
    line_id: str
    source_text: str | None
    product_name_text: str | None
    matched_product_id: str | None
    match_status: Literal["MATCHED", "SELECTED", "NEEDS_SELECTION", "NOT_FOUND", "NOT_PROVIDED"]
    candidates: list[ProductView]
    quantity: int | None
    unit_text: str | None
    unit: str | None
    unit_options: list[str]
    conversion_factor: int | None
    base_quantity: int | None
    base_unit: str | None
    unit_cost_paise: int | None
    line_total_paise: int | None
    confidence: float | None
    merchant_verified: bool
    accepted: bool
    issues: list[Issue]


class ExtractionView(StrictModel):
    provider: str
    model: str | None = None
    status: Literal["EXTRACTED", "PROVIDER_UNAVAILABLE", "NOT_REQUESTED", "PARSED", "CLARIFICATION"]
    correlation_id: str | None = None
    message: str | None = None


class ProposalTotals(StrictModel):
    accepted_line_count: int
    computed_lines_total_paise: int | None
    computed_invoice_total_paise: int | None
    amount_due_if_unpaid_paise: int | None
    rounding_tolerance_paise: int
    payable_note: str


class ProposalView(StrictModel):
    proposal_id: str
    source_kind: SourceKind
    status: ProposalStatus
    version: int
    content_hash: str
    supplier: SupplierMatchView
    invoice: InvoiceHeaderView
    lines: list[LineView]
    issues: list[Issue]
    totals: ProposalTotals
    requires_merchant_review: bool
    ready_to_confirm: bool
    warnings_require_acknowledgement: bool
    image_retained: Literal[False] = False
    extraction: ExtractionView
    source_utterance: str | None
    posted_receipt_id: str | None
    created_at: datetime
    updated_at: datetime
    expires_at: datetime


# --- Requests ---------------------------------------------------------------

class SupplierEdit(StrictModel):
    supplier_id: str | None = Field(default=None, max_length=100)
    label: str | None = Field(default=None, max_length=100)


class InvoiceEdit(StrictModel):
    invoice_number: str | None = Field(default=None, max_length=60)
    invoice_date: date | None = None
    subtotal_paise: int | None = Field(default=None, strict=True, ge=0)
    tax_paise: int | None = Field(default=None, strict=True, ge=0)
    discount_paise: int | None = Field(default=None, strict=True, ge=0)
    freight_paise: int | None = Field(default=None, strict=True, ge=0)
    other_charges_paise: int | None = Field(default=None, strict=True, ge=0)
    rounding_paise: int | None = Field(default=None, strict=True, ge=-10000, le=10000)
    total_paise: int | None = Field(default=None, strict=True, ge=0)
    verified: bool = True


class LineEdit(StrictModel):
    line_id: str | None = Field(default=None, max_length=40)
    product_name_text: str | None = Field(default=None, max_length=120)
    product_id: str | None = Field(default=None, max_length=100)
    quantity: int | None = Field(default=None, strict=True)
    unit_text: str | None = Field(default=None, max_length=32)
    conversion_factor: int | None = Field(default=None, strict=True, gt=0, le=100000)
    unit_cost_paise: int | None = Field(default=None, strict=True, ge=0)
    line_total_paise: int | None = Field(default=None, strict=True, ge=0)
    merchant_verified: bool = True
    accepted: bool = True


class ManualInvoiceCreate(StrictModel):
    supplier: SupplierEdit = Field(default_factory=SupplierEdit)
    invoice: InvoiceEdit = Field(default_factory=InvoiceEdit)
    lines: list[LineEdit] = Field(default_factory=list, max_length=100)
    idempotency_key: str = Field(min_length=8, max_length=150)


class ProposalRevise(StrictModel):
    expected_version: int = Field(strict=True, ge=1)
    supplier: SupplierEdit = Field(default_factory=SupplierEdit)
    invoice: InvoiceEdit = Field(default_factory=InvoiceEdit)
    lines: list[LineEdit] = Field(max_length=100)


class ProposalConfirm(StrictModel):
    expected_version: int = Field(strict=True, ge=1)
    content_hash: str = Field(min_length=64, max_length=64)
    paid_now_paise: int | None = Field(default=None, strict=True, ge=0)
    acknowledge_warnings: bool = False
    confirmed: bool
    idempotency_key: str = Field(min_length=8, max_length=150)
    source_channel: SourceChannel = "text"


class ProposalReject(StrictModel):
    expected_version: int = Field(strict=True, ge=1)
    reason: str | None = Field(default=None, max_length=200)
    confirmed: bool


class ReceiptLineResult(StrictModel):
    movement_id: str
    line_id: str
    product_id: str
    product_name: str
    received_quantity: int
    received_unit: str
    quantity_delta: int
    unit: str
    on_hand_before: int
    on_hand_after: int


class ReceiptView(StrictModel):
    receipt_id: str
    proposal_id: str
    proposal_version: int
    source_kind: SourceKind
    supplier_id: str | None
    supplier_label: str | None
    invoice_number: str | None
    total_paise: int | None
    paid_now_paise: int | None
    payable_entry_id: str | None
    payable_status: Literal["POSTED", "FULLY_PAID_NOW", "NOT_SUPPLIED"]
    supplier_due_before_paise: int | None
    supplier_due_after_paise: int | None
    lines: list[ReceiptLineResult]
    retail_price_changed: Literal[False] = False
    created_at: datetime
    idempotent_replay: bool = False


class UnitConversionCreate(StrictModel):
    unit: str = Field(min_length=1, max_length=32)
    base_units_per_unit: int = Field(strict=True, gt=0, le=100000)
    confirmed: bool
    idempotency_key: str = Field(min_length=8, max_length=150)


class UnitConversionView(StrictModel):
    conversion_id: str
    product_id: str
    unit: str
    base_unit: str
    base_units_per_unit: int
    created_at: datetime


class InwardInterpretRequest(StrictModel):
    utterance: str = Field(min_length=1, max_length=240)
    source_channel: Literal["text", "voice"] = "text"
    idempotency_key: str = Field(min_length=8, max_length=150)


class InwardInterpretResponse(StrictModel):
    status: Literal["proposal", "clarification"]
    message: str | None = None
    parsed_by: str | None
    proposal: ProposalView | None
    writes_performed: Literal[False] = False
