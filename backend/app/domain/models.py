"""Typed API models for the first customer/ledger slice."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CustomerCreate(StrictModel):
    display_name: str = Field(min_length=1, max_length=100)
    aliases: list[str] = Field(default_factory=list, max_length=12)
    confirmed: bool
    idempotency_key: str = Field(min_length=8, max_length=150)


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
