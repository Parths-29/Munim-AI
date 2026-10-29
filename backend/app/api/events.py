"""Read-only activity timeline route."""

from fastapi import APIRouter, Query

from app.domain.models import BusinessEventView
from app.services.events import list_events

router = APIRouter(prefix="/events", tags=["activity"])


@router.get("", response_model=list[BusinessEventView])
def list_events_route(limit: int = Query(default=50, ge=1, le=100)) -> list[BusinessEventView]:
    return list_events(limit=limit)
