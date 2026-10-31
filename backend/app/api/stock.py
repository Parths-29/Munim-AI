"""Inventory 2.0 routes: profiles, sales/wastage, overview, low stock, reorder suggestions, history."""

from datetime import datetime

from fastapi import APIRouter, Query, status

from app.domain.stock import (
    InventoryOverview,
    OutflowBatchView,
    OutflowBatchWrite,
    ProductHistory,
    ProductProfileView,
    ProductProfileWrite,
    ReorderSuggestion,
)
from app.services import stock as service

router = APIRouter(tags=["inventory"])


@router.get("/inventory/overview", response_model=InventoryOverview)
def overview_route(as_of: datetime | None = Query(default=None)) -> InventoryOverview:
    """Whole-shop stock picture: on-hand, value, low/out of stock, top and slow movers, categories."""
    return service.inventory_overview(as_of)


@router.get("/inventory/reorder-suggestions", response_model=list[ReorderSuggestion])
def reorder_route(as_of: datetime | None = Query(default=None)) -> list[ReorderSuggestion]:
    """Arithmetic suggestions only; nothing is ordered."""
    return service.reorder_suggestions(as_of)


@router.post("/inventory/outflows", response_model=OutflowBatchView, status_code=status.HTTP_201_CREATED)
def outflows_route(request: OutflowBatchWrite) -> OutflowBatchView:
    """Record a confirmed sale, wastage, self-use, or supplier return for one or more products atomically."""
    return service.record_outflows(request)


@router.get("/inventory/products/{product_id}/history", response_model=ProductHistory)
def history_route(product_id: str, limit: int = Query(default=50, ge=1, le=200)) -> ProductHistory:
    return service.product_history(product_id, limit)


@router.get("/products/{product_id}/profile", response_model=ProductProfileView)
def get_profile_route(product_id: str) -> ProductProfileView:
    return service.get_profile(product_id)


@router.post("/products/{product_id}/profile", response_model=ProductProfileView)
def set_profile_route(product_id: str, request: ProductProfileWrite) -> ProductProfileView:
    """Merchant-set category, selling price, reorder level/quantity, and supplier lead time."""
    return service.set_profile(product_id, request)
