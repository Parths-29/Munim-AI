"""Voice-first agent routes. Turns never write; confirm applies a stored proposal atomically."""

from fastapi import APIRouter, Query

from app.domain.agent import (
    AgentConfirm,
    AgentConfirmResult,
    AgentHealth,
    AgentSpeakRequest,
    AgentSpeakResponse,
    AgentTurnRequest,
    AgentTurnResponse,
)
from app.services import agent as service

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/turn", response_model=AgentTurnResponse)
def turn_route(request: AgentTurnRequest) -> AgentTurnResponse:
    """Interpret one request (or a choice) into an answer, a reviewable proposal, or one targeted question."""
    return service.turn(request)


@router.post("/proposals/{proposal_id}/confirm", response_model=AgentConfirmResult)
def confirm_route(proposal_id: str, request: AgentConfirm) -> AgentConfirmResult:
    """Apply every action in one transaction (all or nothing). Idempotent per confirm key."""
    return service.confirm(proposal_id, request)


@router.post("/proposals/{proposal_id}/cancel")
def cancel_route(proposal_id: str) -> dict:
    return service.cancel(proposal_id)


@router.post("/speak", response_model=AgentSpeakResponse)
def speak_route(request: AgentSpeakRequest) -> AgentSpeakResponse:
    """Sarvam Bulbul audio for a reply that is already shown as text. Returned, never stored. 503 with a clear message on failure."""
    return service.speak(request)


@router.get("/health", response_model=AgentHealth)
def health_route(refresh: bool = Query(default=False)) -> AgentHealth:
    """Gemini connectivity via a tiny synthetic request; reports a status category, never the key."""
    return service.health(refresh)
