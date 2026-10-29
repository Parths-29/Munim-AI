"""Read-only, deterministic business facts and facts-only AI explanation for the merchant brief."""

from typing import Literal

from fastapi import APIRouter, Query

from app.domain.models import BriefExplanationResponse, BusinessFactsView
from app.services.explainer import explain_business_facts
from app.services.insights import get_business_facts

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/facts", response_model=BusinessFactsView)
def business_facts_route(
    persona: Literal["kirana", "tea_stall", "medical_store"] = Query(default="kirana"),
) -> BusinessFactsView:
    return get_business_facts(persona)


@router.get("/explanation", response_model=BriefExplanationResponse)
@router.post("/explain", response_model=BriefExplanationResponse)
def business_explanation_route(
    persona: Literal["kirana", "tea_stall", "medical_store"] = Query(default="kirana"),
) -> BriefExplanationResponse:
    facts = get_business_facts(persona)
    return explain_business_facts(facts)
