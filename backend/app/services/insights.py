"""Deterministic and evidence-linked merchant facts; no LLM arithmetic."""

from datetime import date, datetime, time, timedelta
from statistics import median
from zoneinfo import ZoneInfo

from app.domain.models import BusinessFactsView, FactPeriod, FactView
from app.services.database import connect
from app.services.synthetic_data import DEMO_END_DATE, PERSONAS, TZ_NAME


def get_business_facts(persona: str = "kirana") -> BusinessFactsView:
    if persona not in PERSONAS:
        raise ValueError("Unknown synthetic merchant persona.")

    shop_id = PERSONAS[persona][0]
    tz = ZoneInfo(TZ_NAME)
    current_start = DEMO_END_DATE - timedelta(days=6)
    current_end = DEMO_END_DATE + timedelta(days=1)  # exclusive bound
    baseline_start = current_start - timedelta(days=7)
    lookback_start = current_start - timedelta(days=28)

    def stamp(day: date) -> str:
        return datetime.combine(day, time.min, tzinfo=tz).isoformat()

    with connect() as connection:
        rows = connection.execute(
            """SELECT occurred_at, amount_paise, status, payer_token
               FROM synthetic_transactions
               WHERE shop_id = ? AND occurred_at >= ? AND occurred_at < ?
               ORDER BY occurred_at""",
            (shop_id, stamp(lookback_start), stamp(current_end)),
        ).fetchall()

    current_rows = [row for row in rows if stamp(current_start) <= row["occurred_at"] < stamp(current_end)]
    baseline_rows = [row for row in rows if stamp(baseline_start) <= row["occurred_at"] < stamp(current_start)]
    current_success = [row for row in current_rows if row["status"] == "SUCCESS"]
    baseline_success = [row for row in baseline_rows if row["status"] == "SUCCESS"]
    current_total = sum(row["amount_paise"] for row in current_success)
    baseline_total = sum(row["amount_paise"] for row in baseline_success)
    current_median = median([row["amount_paise"] for row in current_success]) if current_success else None
    baseline_median = median([row["amount_paise"] for row in baseline_success]) if baseline_success else None

    current_attempts = [row for row in current_rows if row["status"] in ("SUCCESS", "FAILED")]
    failed_count = sum(row["status"] == "FAILED" for row in current_attempts)
    failure_rate = (100 * failed_count / len(current_attempts)) if current_attempts else None

    prior_counts = {}
    for row in rows:
        if (row["payer_token"] is not None and stamp(lookback_start) <= row["occurred_at"] < stamp(current_start)
                and row["status"] == "SUCCESS"):
            prior_counts[row["payer_token"]] = prior_counts.get(row["payer_token"], 0) + 1
    current_payers = {
        row["payer_token"] for row in current_success if row["payer_token"] is not None
    }
    lapsed_count = sum(1 for token, n in prior_counts.items() if n >= 3 and token not in current_payers)

    comparison_label = f"{baseline_start.isoformat()} to {(current_start - timedelta(days=1)).isoformat()}"
    current_label = f"{current_start.isoformat()} to {DEMO_END_DATE.isoformat()}"
    revenue_change = ((current_total - baseline_total) * 100 / baseline_total) if baseline_total else None
    low_sample = len(current_success) < 10 or len(baseline_success) < 10
    facts = [
        FactView(
            id="payment_collections", label="Successful UPI collections", status="low_sample" if low_sample else "available",
            value=round(current_total / 100, 2), unit="INR", source="synthetic_transactions", count=len(current_success),
            comparison_value=round(baseline_total / 100, 2), comparison_period=comparison_label,
            definition=f"Successful payment amounts during {current_label}; compared with the preceding 7 full days.",
        ),
        FactView(
            id="collection_change_pct", label="Collections change", status="low_sample" if low_sample else ("available" if revenue_change is not None else "unavailable"),
            value=round(revenue_change, 1) if revenue_change is not None else None, unit="percent", source="synthetic_transactions",
            count=len(current_success), comparison_value=round(baseline_total / 100, 2), comparison_period=comparison_label,
            definition="Percentage change in successful UPI collections against the preceding comparable 7-day window.",
            reason_unavailable="baseline_is_zero" if baseline_total == 0 else None,
        ),
        FactView(
            id="median_ticket", label="Median payment amount", status="available" if current_median is not None and baseline_median is not None else "unavailable",
            value=round(current_median / 100, 2) if current_median is not None else None, unit="INR", source="synthetic_transactions",
            count=len(current_success), comparison_value=round(baseline_median / 100, 2) if baseline_median is not None else None,
            comparison_period=comparison_label, definition="Median successful UPI payment amount; this is not product price or profit.",
            reason_unavailable="no_successful_payments" if current_median is None else None,
        ),
        FactView(
            id="payment_failure_rate", label="Failed payment attempt rate", status="available" if failure_rate is not None else "unavailable",
            value=round(failure_rate, 1) if failure_rate is not None else None, unit="percent", source="synthetic_transactions",
            count=len(current_attempts), definition="Failed attempts divided by successful plus failed attempts in the current 7-day window.",
            reason_unavailable="no_success_or_failed_attempts" if failure_rate is None else None,
        ),
        FactView(
            id="lapsed_repeat_payers", label="Previously frequent payer tokens absent this week", status="available",
            value=lapsed_count, unit="payer_tokens", source="synthetic_transactions", count=len(prior_counts),
            definition="Merchant-scoped synthetic token had 3+ successful payments in the 28 days before this week and none in this week. No identity or reason is inferred.",
        ),
    ]

    return BusinessFactsView(
        shop_id=shop_id,
        data_mode="synthetic",
        period=FactPeriod(start=datetime.combine(current_start, time.min, tzinfo=tz), end=datetime.combine(current_end, time.min, tzinfo=tz), timezone=TZ_NAME),
        facts=facts,
        evidence_ids=[fact.id for fact in facts if fact.status in ("available", "low_sample")],
        caveats=[
            "This fixture is synthetic and does not represent actual Paytm merchant activity.",
            "UPI collections are not total shop revenue; cash, credit sales, inventory, footfall, and other apps are absent.",
            "A before/after difference does not prove why the number changed or that an action caused it.",
            "Payer counts use synthetic merchant-scoped tokens only; no contact details or individual identities are available.",
        ],
        allowed_actions=["counter_notice", "qr_offer_mock"],
    )
