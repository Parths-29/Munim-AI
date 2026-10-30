"""Deterministic summary of the synthetic shop timeline and mock payments."""

from datetime import datetime

from app.domain.models import ActivitySummaryView, RecentPaymentSummary
from app.services.database import DEMO_SHOP_ID, connect
from app.services.events import list_events


def _money(amount_paise: int) -> str:
    return f"₹{amount_paise / 100:,.2f}"


def get_activity_summary() -> ActivitySummaryView:
    with connect() as connection:
        event_count = int(connection.execute(
            "SELECT COUNT(*) FROM business_events WHERE shop_id = ?", (DEMO_SHOP_ID,)
        ).fetchone()[0])
        ledger = {
            row["entry_type"]: (int(row["entry_count"]), int(row["total_paise"] or 0))
            for row in connection.execute(
                """SELECT entry_type, COUNT(*) AS entry_count, COALESCE(SUM(amount_paise), 0) AS total_paise
                   FROM ledger_entries WHERE shop_id = ? AND status = 'POSTED' GROUP BY entry_type""",
                (DEMO_SHOP_ID,),
            ).fetchall()
        }
        payments = {
            row["payment_status"]: (int(row["event_count"]), int(row["total_paise"] or 0))
            for row in connection.execute(
                """SELECT payment_status, COUNT(*) AS event_count, COALESCE(SUM(amount_paise), 0) AS total_paise
                   FROM payment_events WHERE shop_id = ? GROUP BY payment_status""",
                (DEMO_SHOP_ID,),
            ).fetchall()
        }
        open_review = connection.execute(
            """SELECT COUNT(*) AS event_count, COALESCE(SUM(p.amount_paise), 0) AS total_paise
               FROM payment_events p
               WHERE p.shop_id = ? AND p.payment_status = 'SUCCESS'
                 AND p.resolution_status IN ('UNMATCHED', 'REVIEW')
                 AND NOT EXISTS (
                   SELECT 1 FROM payment_resolutions r
                   WHERE r.shop_id = p.shop_id AND r.event_id = p.event_id
                 )""",
            (DEMO_SHOP_ID,),
        ).fetchone()
        event_types = {
            row["event_type"]: int(row["event_count"])
            for row in connection.execute(
                """SELECT event_type, COUNT(*) AS event_count FROM business_events
                   WHERE shop_id = ? GROUP BY event_type""",
                (DEMO_SHOP_ID,),
            ).fetchall()
        }
        recent_payment_rows = connection.execute(
            """SELECT event_id, amount_paise, payment_status, resolution_status,
                      resolution_reason, occurred_at
               FROM payment_events WHERE shop_id = ?
               ORDER BY created_at DESC, event_id DESC LIMIT 5""",
            (DEMO_SHOP_ID,),
        ).fetchall()

    credit_count, credit_total = ledger.get("CREDIT", (0, 0))
    repayment_count, repayment_total = ledger.get("REPAYMENT", (0, 0))
    successful_count, successful_total = payments.get("SUCCESS", (0, 0))
    pending_count, pending_total = payments.get("PENDING", (0, 0))
    failed_count, failed_total = payments.get("FAILED", (0, 0))
    reversed_count, reversed_total = payments.get("REVERSED", (0, 0))
    review_count, review_total = int(open_review["event_count"]), int(open_review["total_paise"])

    lines = [f"Recorded ledger: {credit_count} credits totaling {_money(credit_total)} and {repayment_count} repayments totaling {_money(repayment_total)}."]
    lines.append(f"Mock payment feed: {successful_count} successful payments totaling {_money(successful_total)}.")
    if pending_count:
        lines.append(f"{pending_count} payments totaling {_money(pending_total)} are pending.")
    if failed_count:
        lines.append(f"{failed_count} failed payments total {_money(failed_total)}.")
    if reversed_count:
        lines.append(f"{reversed_count} reversed payments total {_money(reversed_total)}.")
    if review_count:
        lines.append(f"{review_count} successful payment(s) totaling {_money(review_total)} still need review.")
    else:
        lines.append("No successful mock payments are waiting for review.")
    stockout_count = event_types.get("STOCKOUT_OBSERVED", 0)
    count_event_count = event_types.get("STOCK_COUNT_RECORDED", 0)
    lines.append(f"Inventory history: {stockout_count} stockout observations and {count_event_count} physical count events.")

    return ActivitySummaryView(
        data_mode="synthetic",
        period_label="All recorded demo events; not a live daily Paytm feed.",
        recorded_event_count=event_count,
        credit_entry_count=credit_count,
        credit_total_paise=credit_total,
        repayment_entry_count=repayment_count,
        repayment_total_paise=repayment_total,
        payment_event_count=sum(item[0] for item in payments.values()),
        successful_payment_count=successful_count,
        successful_payment_total_paise=successful_total,
        pending_payment_count=pending_count,
        pending_payment_total_paise=pending_total,
        failed_payment_count=failed_count,
        failed_payment_total_paise=failed_total,
        open_review_payment_count=review_count,
        open_review_payment_total_paise=review_total,
        reversed_payment_count=reversed_count,
        reversed_payment_total_paise=reversed_total,
        stockout_observation_count=stockout_count,
        physical_count_event_count=count_event_count,
        recent_payments=[
            RecentPaymentSummary(
                event_id=row["event_id"],
                amount_paise=row["amount_paise"],
                payment_status=row["payment_status"],
                resolution_status=row["resolution_status"],
                reason=row["resolution_reason"],
                occurred_at=datetime.fromisoformat(row["occurred_at"]),
            )
            for row in recent_payment_rows
        ],
        latest_events=list_events(5),
        summary_text=" ".join(lines),
        caveats=[
            "This summary covers all records in the synthetic demo shop, not a live daily Paytm feed.",
            "Successful payment totals are mock events and are separate from ledger repayment totals; an event is counted in the ledger only after allocation.",
            "Cash sales, other UPI apps, external settlements, refunds outside this fixture, and customer identities are not included.",
        ],
    )
