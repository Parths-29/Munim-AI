"""Inventory 2.0 models: product profiles, outflows (sales/wastage), overview, and reorder suggestions."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.domain.models import SourceChannel, StrictModel

OutflowReason = Literal["SALE", "WASTAGE", "SELF_USE", "RETURN_TO_SUPPLIER"]
StockStatus = Literal["OUT_OF_STOCK", "LOW", "OK", "NO_RECORDS"]


class ProductProfileWrite(StrictModel):
    category: str | None = Field(default=None, max_length=40)
    retail_price_paise: int | None = Field(default=None, strict=True, ge=0)
    reorder_level: int | None = Field(default=None, strict=True, ge=0)
    reorder_quantity: int | None = Field(default=None, strict=True, gt=0)
    lead_time_days: int | None = Field(default=None, strict=True, ge=0, le=60)
    confirmed: bool
    idempotency_key: str = Field(min_length=8, max_length=150)


class ProductProfileView(StrictModel):
    product_id: str
    category: str | None
    retail_price_paise: int | None
    reorder_level: int | None
    reorder_quantity: int | None
    lead_time_days: int | None
    updated_at: datetime | None


class OutflowLine(StrictModel):
    product_id: str = Field(min_length=1, max_length=100)
    quantity: int = Field(strict=True, gt=0, le=100000)
    unit_text: str | None = Field(default=None, max_length=32)
    unit_price_paise: int | None = Field(default=None, strict=True, ge=0)


class OutflowBatchWrite(StrictModel):
    reason: OutflowReason
    lines: list[OutflowLine] = Field(min_length=1, max_length=30)
    confirmed: bool
    idempotency_key: str = Field(min_length=8, max_length=150)
    source_channel: SourceChannel = "text"
    source_utterance: str | None = Field(default=None, max_length=240)


class OutflowLineResult(StrictModel):
    movement_id: str
    product_id: str
    product_name: str
    reason: OutflowReason
    entered_quantity: int
    entered_unit: str
    quantity_delta: int
    unit: str
    unit_price_paise: int | None
    amount_paise: int | None
    on_hand_before: int
    on_hand_after: int
    low_stock_after: bool


class OutflowBatchView(StrictModel):
    batch_id: str
    reason: OutflowReason
    lines: list[OutflowLineResult]
    total_amount_paise: int | None
    idempotent_replay: bool = False


class ProductStockRow(StrictModel):
    product_id: str
    name: str
    category: str | None
    unit: str
    on_hand_quantity: int
    status: StockStatus
    retail_price_paise: int | None
    last_unit_cost_paise: int | None
    stock_value_at_cost_paise: int | None
    stock_value_at_retail_paise: int | None
    margin_percent: float | None
    sold_last_14_days: int
    avg_daily_sales: float
    days_of_cover: float | None
    reorder_level: int | None
    suggested_reorder_quantity: int
    last_counted_at: datetime | None
    last_movement_at: datetime | None


class CategorySummary(StrictModel):
    category: str
    product_count: int
    low_or_out_count: int
    stock_value_at_cost_paise: int


class InventoryOverview(StrictModel):
    shop_id: str
    as_of: datetime
    product_count: int
    out_of_stock: list[str]
    low_stock: list[str]
    stock_value_at_cost_paise: int
    stock_value_at_retail_paise: int
    sales_last_7_days_paise: int
    wastage_last_30_days_paise: int
    top_movers: list[str]
    slow_movers: list[str]
    categories: list[CategorySummary]
    products: list[ProductStockRow]
    caveats: list[str]


class ReorderSuggestion(StrictModel):
    product_id: str
    name: str
    unit: str
    on_hand_quantity: int
    avg_daily_sales: float
    lead_time_days: int
    reorder_level: int | None
    suggested_quantity: int
    estimated_cost_paise: int | None
    reason: str


class ProductMovement(StrictModel):
    kind: Literal["PHYSICAL_COUNT", "STOCK_RECEIPT", "SALE", "WASTAGE", "SELF_USE", "RETURN_TO_SUPPLIER"]
    quantity_delta: int
    unit: str
    occurred_at: datetime
    detail: str | None


class ProductHistory(StrictModel):
    product_id: str
    name: str
    unit: str
    on_hand_quantity: int
    movements: list[ProductMovement]
