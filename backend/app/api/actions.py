"""Merchant-confirmed mock action approval and observation status."""

from typing import Literal

from fastapi import APIRouter, Query

from app.domain.models import MockActionCreate, MockActionView
from app.services.mock_actions import approve_mock_action, get_latest_mock_action

router = APIRouter(prefix="/actions", tags=["merchant actions"])


@router.post("/mock", response_model=MockActionView)
def approve_mock_action_route(request: MockActionCreate) -> MockActionView:
    return approve_mock_action(request)


@router.get("/latest", response_model=MockActionView | None)
def latest_mock_action_route(
    persona: Literal["kirana", "tea_stall", "medical_store"] = Query(default="kirana"),
) -> MockActionView | None:
    return get_latest_mock_action(persona)
