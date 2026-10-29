"""Typed ledger routes; no generic database-write endpoint is exposed."""

from fastapi import APIRouter, status

from app.domain.models import CustomerBalance, LedgerEntryView, LedgerWrite
from app.services.ledger import get_balance, post_credit, post_repayment

router = APIRouter(prefix="/ledger", tags=["ledger"])


@router.get("/customers/{customer_id}/balance", response_model=CustomerBalance)
def customer_balance_route(customer_id: str) -> CustomerBalance:
    return get_balance(customer_id)


@router.post("/credits", response_model=LedgerEntryView, status_code=status.HTTP_201_CREATED)
def create_credit_route(request: LedgerWrite) -> LedgerEntryView:
    return post_credit(request)


@router.post("/repayments", response_model=LedgerEntryView, status_code=status.HTTP_201_CREATED)
def record_repayment_route(request: LedgerWrite) -> LedgerEntryView:
    return post_repayment(request)
