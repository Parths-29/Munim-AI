"""Supplier profile and supplier payable (shop owes supplier) routes."""

from fastapi import APIRouter, Query, status

from app.domain.models import (
    SupplierAdjustmentWrite,
    SupplierBalanceView,
    SupplierCreate,
    SupplierPayableEntryView,
    SupplierPaymentWrite,
    SupplierResolution,
    SupplierView,
)
from app.services.suppliers import (
    create_supplier,
    get_supplier_balance,
    list_supplier_entries,
    list_suppliers,
    record_supplier_adjustment,
    record_supplier_payment,
    resolve_supplier,
)

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


@router.post("", response_model=SupplierView, status_code=status.HTTP_201_CREATED)
def create_supplier_route(request: SupplierCreate) -> SupplierView:
    return create_supplier(request)


@router.get("", response_model=list[SupplierView])
def list_suppliers_route() -> list[SupplierView]:
    return list_suppliers()


@router.get("/resolve", response_model=SupplierResolution)
def resolve_supplier_route(query: str = Query(min_length=1, max_length=100)) -> SupplierResolution:
    return resolve_supplier(query)


@router.get("/{supplier_id}/balance", response_model=SupplierBalanceView)
def supplier_balance_route(supplier_id: str) -> SupplierBalanceView:
    return get_supplier_balance(supplier_id)


@router.get("/{supplier_id}/entries", response_model=list[SupplierPayableEntryView])
def supplier_entries_route(supplier_id: str, limit: int = Query(default=100, ge=1, le=200)) -> list[SupplierPayableEntryView]:
    return list_supplier_entries(supplier_id, limit)


@router.post("/{supplier_id}/payments", response_model=SupplierPayableEntryView, status_code=status.HTTP_201_CREATED)
def supplier_payment_route(supplier_id: str, request: SupplierPaymentWrite) -> SupplierPayableEntryView:
    """Record a payment already made outside the app. This never transfers money."""
    return record_supplier_payment(supplier_id, request)


@router.post("/{supplier_id}/adjustments", response_model=SupplierPayableEntryView, status_code=status.HTTP_201_CREATED)
def supplier_adjustment_route(supplier_id: str, request: SupplierAdjustmentWrite) -> SupplierPayableEntryView:
    return record_supplier_adjustment(supplier_id, request)
