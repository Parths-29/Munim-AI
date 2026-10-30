"""Product, stock observation, and verified count routes."""

from fastapi import APIRouter, Query, status

from app.domain.intake import UnitConversionCreate, UnitConversionView
from app.domain.models import (
    InventoryMovementView,
    ProductCreate,
    ProductResolution,
    ProductView,
    StockBalanceView,
    StockCountCreate,
    StockoutObservationCreate,
    StockoutObservationView,
)
from app.services.inventory import (
    create_product,
    create_unit_conversion,
    list_unit_conversions,
    get_stock_balance,
    record_stock_count,
    record_stockout_observation,
    resolve_product,
)

router = APIRouter(tags=["inventory"])


@router.post("/products", response_model=ProductView, status_code=status.HTTP_201_CREATED)
def create_product_route(request: ProductCreate) -> ProductView:
    return create_product(request)


@router.get("/products/resolve", response_model=ProductResolution)
def resolve_product_route(query: str = Query(min_length=1, max_length=100)) -> ProductResolution:
    return resolve_product(query)


@router.get("/inventory/products/{product_id}/stock", response_model=StockBalanceView)
def stock_balance_route(product_id: str) -> StockBalanceView:
    return get_stock_balance(product_id)


@router.post("/inventory/stockout-observations", response_model=StockoutObservationView, status_code=status.HTTP_201_CREATED)
def stockout_observation_route(request: StockoutObservationCreate) -> StockoutObservationView:
    return record_stockout_observation(request)


@router.post("/inventory/counts", response_model=InventoryMovementView, status_code=status.HTTP_201_CREATED)
def stock_count_route(request: StockCountCreate) -> InventoryMovementView:
    return record_stock_count(request)


@router.post("/products/{product_id}/unit-conversions", response_model=UnitConversionView, status_code=status.HTTP_201_CREATED)
def create_unit_conversion_route(product_id: str, request: UnitConversionCreate) -> UnitConversionView:
    return create_unit_conversion(product_id, request)


@router.get("/products/{product_id}/unit-conversions", response_model=list[UnitConversionView])
def list_unit_conversions_route(product_id: str) -> list[UnitConversionView]:
    return list_unit_conversions(product_id)
