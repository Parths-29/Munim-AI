"""Read-only, deterministic business facts for the merchant brief."""

from typing import Literal

from fastapi import APIRouter, Query

from app.domain.models import BusinessFactsView
from app.services.insights import get_business_facts

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/facts", response_model=BusinessFactsView)
def business_facts_route(
    persona: Literal["kirana", "tea_stall", "medical_store"] = Query(default="kirana"),
) -> BusinessFactsView:
    return get_business_facts(persona)
