"""Voice-first merchant agent: one turn in, one answer / proposal / clarification out.

The interpreter (Gemini, or the deterministic fallback) only proposes. Application code resolves
IDs, computes paise, checks business rules, and nothing is written until the merchant confirms.
"""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.domain.models import StrictModel

ActionKind = Literal["customer_create", "credit", "repayment", "sale", "stock_count", "stockout"]
ReadKind = Literal["balance", "stock_check", "payment_summary", "timeline_summary", "supplier_balance", "guidance"]


class AgentChoice(StrictModel):
    slot_id: str = Field(min_length=1, max_length=80)
    option_id: str = Field(min_length=1, max_length=120)


class AgentTurnRequest(StrictModel):
    utterance: str = Field(default="", max_length=400)
    session_id: str | None = Field(default=None, max_length=80)
    source_channel: Literal["text", "voice"] = "text"
    # The raw speech-to-text output before the merchant edited it (voice only); kept for the audit trail.
    transcript_original: str | None = Field(default=None, max_length=400)
    choice: AgentChoice | None = None


class TranscriptView(StrictModel):
    original: str | None
    used: str
    model_corrected: str | None = None


class ChoiceOption(StrictModel):
    option_id: str
    label: str
    detail: str | None = None


class Clarification(StrictModel):
    question: str
    missing: list[str] = Field(default_factory=list)
    slot_id: str | None = None
    choices: list[ChoiceOption] = Field(default_factory=list)


class AgentAnswer(StrictModel):
    kind: ReadKind
    customer_id: str | None = None
    customer_name: str | None = None
    balance_due_paise: int | None = None
    product_id: str | None = None
    product_name: str | None = None
    on_hand_quantity: int | None = None
    unit: str | None = None
    supplier_id: str | None = None
    supplier_name: str | None = None
    supplier_due_paise: int | None = None
    feature: str | None = None
    notes: list[str] = Field(default_factory=list)


class ProposedAction(StrictModel):
    index: int
    kind: ActionKind
    summary: str
    customer_id: str | None = None
    customer_name: str | None = None
    creates_customer_ref: int | None = None
    amount_paise: int | None = None
    amount_text: str | None = None
    balance_before_paise: int | None = None
    balance_after_paise: int | None = None
    product_id: str | None = None
    product_name: str | None = None
    quantity: int | None = None
    unit: str | None = None
    on_hand_before: int | None = None
    on_hand_after: int | None = None
    inferred: list[str] = Field(default_factory=list)


class AgentProposal(StrictModel):
    proposal_id: str
    content_hash: str
    actions: list[ProposedAction]
    inferred_notes: list[str] = Field(default_factory=list)
    expires_at: datetime


class ProviderStatus(StrictModel):
    provider: Literal["gemini"] = "gemini"
    status: Literal["ok", "disabled", "not_configured", "unreachable", "auth_error", "model_not_found", "quota", "bad_request",
                    "server_error", "invalid_output"]
    detail: str | None = None
    key_slot: str | None = None  # which configured key answered (name only, never the value)
    attempts: int = 0


class AgentTurnResponse(StrictModel):
    session_id: str
    turn_index: int
    status: Literal["answer", "proposal", "clarification", "cancelled", "info"]
    message: str
    interpreted_by: Literal["gemini", "deterministic", "context", "choice"]
    llm: ProviderStatus
    transcript: TranscriptView
    answer: AgentAnswer | None = None
    proposal: AgentProposal | None = None
    clarification: Clarification | None = None
    writes_performed: Literal[False] = False
    reply_text: str = ""  # what to speak: built from verified backend results (optionally worded by Gemini)
    reply_language: str = "en-IN"
    reply_worded_by: Literal["gemini", "template"] = "template"


class AgentConfirm(StrictModel):
    confirmed: bool
    content_hash: str = Field(min_length=8, max_length=80)
    idempotency_key: str = Field(min_length=8, max_length=150)


class AppliedAction(StrictModel):
    index: int
    kind: ActionKind
    entity_id: str
    summary: str
    customer_name: str | None = None
    product_name: str | None = None
    amount_paise: int | None = None
    quantity: int | None = None
    unit: str | None = None
    balance_after_paise: int | None = None  # read back from the ledger after the write committed
    on_hand_after: int | None = None


class AgentConfirmResult(StrictModel):
    proposal_id: str
    status: Literal["APPLIED"] = "APPLIED"
    applied: list[AppliedAction]
    idempotent_replay: bool = False
    reply_text: str = ""
    reply_language: str = "en-IN"
    reply_worded_by: Literal["gemini", "template"] = "template"


class AgentSpeakRequest(StrictModel):
    text: str = Field(min_length=1, max_length=600)
    language_code: str | None = Field(default=None, min_length=5, max_length=5)


class AgentSpeakResponse(StrictModel):
    audio_base64: str
    mime_type: Literal["audio/wav"] = "audio/wav"
    provider: str
    model: str | None
    speaker: str | None
    language_code: str
    stored: Literal[False] = False


class AgentHealth(StrictModel):
    llm: ProviderStatus
    model: str
    key_configured: bool
    key_slots_configured: list[str] = Field(default_factory=list)
    voice_output: str = "off"  # live | fake | off
