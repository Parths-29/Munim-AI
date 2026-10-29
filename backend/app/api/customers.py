"""Customer lookup and creation routes for the single synthetic shop."""

from fastapi import APIRouter, Query, status

from app.domain.models import CustomerCreate, CustomerResolution, CustomerView
from app.services.ledger import create_customer, resolve_customer

router = APIRouter(prefix="/customers", tags=["customers"])


@router.post("", response_model=CustomerView, status_code=status.HTTP_201_CREATED)
def create_customer_route(request: CustomerCreate) -> CustomerView:
    return create_customer(request)


@router.get("/resolve", response_model=CustomerResolution)
def resolve_customer_route(query: str = Query(min_length=1, max_length=100)) -> CustomerResolution:
    return resolve_customer(query)
