"""Read-only activity timeline route."""

from fastapi import APIRouter, Query

from app.domain.models import ActivitySummaryView, BusinessEventView
from app.services.activity_summary import get_activity_summary
from app.services.events import list_events

router = APIRouter(prefix="/events", tags=["activity"])


@router.get("/summary", response_model=ActivitySummaryView)
def activity_summary_route() -> ActivitySummaryView:
    return get_activity_summary()


@router.get("", response_model=list[BusinessEventView])
def list_events_route(limit: int = Query(default=50, ge=1, le=100)) -> list[BusinessEventView]:
    return list_events(limit=limit)
