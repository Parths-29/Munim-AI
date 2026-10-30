"""Merchant-confirmed mock action records and honest outcome-window status."""

import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from app.domain.models import BusinessFactsView, MockActionCreate, MockActionView
from app.services.database import connect
from app.services.insights import get_business_facts
from app.services.synthetic_data import PERSONAS, TZ_NAME


def _view(row, *, now: datetime | None = None) -> MockActionView:
    tz = ZoneInfo(TZ_NAME)
    current = now or datetime.now(tz)
    measurement_start = datetime.fromisoformat(row["measurement_start"])
    measurement_end = datetime.fromisoformat(row["measurement_end"])
    outcome_rows = []
    outcome_status = "scheduled"
    outcome_total = None
    outcome_count = None
    change = None
    note = "The 7-day observation window is scheduled. This mock action has not been published."

    if current >= measurement_end:
        with connect() as connection:
            outcome_rows = connection.execute(
                """SELECT amount_paise FROM synthetic_transactions
                   WHERE shop_id = ? AND status = 'SUCCESS'
                     AND occurred_at >= ? AND occurred_at < ?""",
                (row["shop_id"], measurement_start.isoformat(), measurement_end.isoformat()),
            ).fetchall()
        if not outcome_rows:
            outcome_status = "insufficient_data"
            note = "The observation window ended, but no transactions are available for it. No result is inferred."
        else:
            outcome_status = "available"
            outcome_total = sum(item["amount_paise"] for item in outcome_rows)
            outcome_count = len(outcome_rows)
            change = outcome_total - row["baseline_collections_paise"]
            note = "Observed UPI collections during the window compared with the saved baseline. This difference does not show the action caused a change."

    return MockActionView(
        action_id=row["action_id"],
        action_type=row["action_type"],
        action_text=row["action_text"],
        status=row["status"],
        created_at=datetime.fromisoformat(row["created_at"]),
        baseline_start=datetime.fromisoformat(row["baseline_start"]),
        baseline_end=datetime.fromisoformat(row["baseline_end"]),
        baseline_collections_paise=row["baseline_collections_paise"],
        baseline_transaction_count=row["baseline_transaction_count"],
        measurement_start=measurement_start,
        measurement_end=measurement_end,
        outcome_status=outcome_status,
        outcome_collections_paise=outcome_total,
        outcome_transaction_count=outcome_count,
        collections_change_paise=change,
        outcome_note=note,
    )


def _get_by_key(connection, key: str):
    return connection.execute(
        "SELECT * FROM mock_actions WHERE idempotency_key = ?", (key,)
    ).fetchone()


def approve_mock_action(request: MockActionCreate) -> MockActionView:
    if not request.confirmed:
        raise HTTPException(status_code=400, detail="Merchant confirmation is required.")
    facts = get_business_facts(request.persona)
    collection_fact = next((fact for fact in facts.facts if fact.id == "payment_collections"), None)
    if collection_fact is None or collection_fact.value is None:
        raise HTTPException(status_code=409, detail="A collections baseline is unavailable.")

    shop_id = PERSONAS[request.persona][0]
    now = datetime.now(ZoneInfo(TZ_NAME)).replace(microsecond=0)
    measurement_end = now + timedelta(days=7)
    baseline_start = facts.period.start
    baseline_end = facts.period.end
    baseline_paise = int(round(float(collection_fact.value) * 100))
    baseline_count = int(collection_fact.count or 0)

    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        existing = _get_by_key(connection, request.idempotency_key)
        if existing:
            same_payload = (
                existing["persona"] == request.persona
                and existing["action_type"] == request.action_type
                and existing["action_text"] == request.action_text
            )
            if not same_payload:
                raise HTTPException(status_code=409, detail="Idempotency key was already used for a different action.")
            return _view(existing, now=now)

        action_id = f"mock_action_{uuid.uuid4().hex[:12]}"
        connection.execute(
            """INSERT INTO mock_actions
               (action_id, shop_id, persona, action_type, action_text, status,
                baseline_start, baseline_end, baseline_collections_paise,
                baseline_transaction_count, measurement_start, measurement_end,
                idempotency_key, created_at)
               VALUES (?, ?, ?, ?, ?, 'APPROVED_MOCK', ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                action_id, shop_id, request.persona, request.action_type, request.action_text,
                baseline_start.isoformat(), baseline_end.isoformat(), baseline_paise,
                baseline_count, now.isoformat(), measurement_end.isoformat(),
                request.idempotency_key, now.isoformat(),
            ),
        )
        row = connection.execute("SELECT * FROM mock_actions WHERE action_id = ?", (action_id,)).fetchone()
    return _view(row, now=now)


def get_latest_mock_action(persona: str) -> MockActionView | None:
    if persona not in PERSONAS:
        raise HTTPException(status_code=404, detail="Unknown synthetic merchant persona.")
    shop_id = PERSONAS[persona][0]
    with connect() as connection:
        row = connection.execute(
            """SELECT * FROM mock_actions WHERE shop_id = ?
               ORDER BY created_at DESC, action_id DESC LIMIT 1""",
            (shop_id,),
        ).fetchone()
    return _view(row) if row else None
