"""Append-only business-event timeline helpers."""

import uuid
from datetime import datetime, timezone
import sqlite3

from app.domain.models import BusinessEventView
from app.services.database import DEMO_SHOP_ID, connect


def append_event(
    connection: sqlite3.Connection,
    *,
    event_type: str,
    entity_type: str,
    entity_id: str,
    source_event_id: str,
    source_channel: str,
    source_utterance: str | None,
    status: str,
    summary: str,
    idempotency_key: str,
) -> None:
    connection.execute(
        """INSERT INTO business_events
           (event_id, shop_id, event_type, entity_type, entity_id, source_event_id,
            source_channel, source_utterance, status, summary, idempotency_key, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            f"event_{uuid.uuid4().hex[:12]}",
            DEMO_SHOP_ID,
            event_type,
            entity_type,
            entity_id,
            source_event_id,
            source_channel,
            source_utterance,
            status,
            summary,
            idempotency_key,
            datetime.now(timezone.utc).isoformat(),
        ),
    )


def list_events(limit: int = 50) -> list[BusinessEventView]:
    bounded_limit = min(max(limit, 1), 100)
    with connect() as connection:
        rows = connection.execute(
            """SELECT event_id, event_type, entity_type, entity_id, source_event_id,
                      source_channel, source_utterance, status, summary, created_at
               FROM business_events
               WHERE shop_id = ?
               ORDER BY created_at DESC, event_id DESC
               LIMIT ?""",
            (DEMO_SHOP_ID, bounded_limit),
        ).fetchall()
    return [
        BusinessEventView(
            event_id=row["event_id"],
            event_type=row["event_type"],
            entity_type=row["entity_type"],
            entity_id=row["entity_id"],
            source_event_id=row["source_event_id"],
            source_channel=row["source_channel"],
            source_utterance=row["source_utterance"],
            status=row["status"],
            summary=row["summary"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
        for row in rows
    ]
