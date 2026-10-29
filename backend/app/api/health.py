"""Minimal liveness route for the Phase 1 scaffold."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    phase: str
    data_mode: str


@router.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    """Report that the local API process is responding."""
    return HealthResponse(status="ok", phase="payment-review", data_mode="synthetic-only")
