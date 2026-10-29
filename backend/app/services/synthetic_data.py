"""Deterministic, visibly synthetic payment rows for the hackathon demo."""

import random
import sqlite3
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.services.database import DEMO_SHOP_ID


TZ_NAME = "Asia/Kolkata"
DEMO_END_DATE = date(2026, 10, 29)
PERSONAS = {
    "kirana": (DEMO_SHOP_ID, 46, 14500),
    "tea_stall": ("shop_synth_tea", 34, 6500),
    "medical_store": ("shop_synth_medical", 25, 22500),
}


def seed_synthetic_transactions(connection: sqlite3.Connection) -> None:
    """Insert a repeatable 90-day fixture once; never overwrite merchant data."""
    connection.execute("BEGIN IMMEDIATE")
    count = connection.execute("SELECT COUNT(*) FROM synthetic_transactions").fetchone()[0]
    if count:
        return

    rng = random.Random(1029)
    tz = ZoneInfo(TZ_NAME)
    rows = []
    start_date = DEMO_END_DATE - timedelta(days=89)
    for persona, (shop_id, average_daily_count, base_amount) in PERSONAS.items():
        payer_pool = [f"payer_{persona}_{index:03d}" for index in range(1, 121)]
        for day_index in range(90):
            day = start_date + timedelta(days=day_index)
            recent_kirana_decline = persona == "kirana" and day > DEMO_END_DATE - timedelta(days=7)
            multiplier = 0.68 if recent_kirana_decline else 1.0
            weekday_multiplier = 1.12 if day.weekday() in (5, 6) else 1.0
            daily_count = max(8, int(average_daily_count * multiplier * weekday_multiplier + rng.randint(-7, 7)))
            for index in range(daily_count):
                if persona == "tea_stall":
                    hour = rng.choices([7, 8, 9, 10, 16, 17, 18, 19, 20], [1, 2, 3, 2, 1, 2, 4, 4, 3])[0]
                else:
                    hour = rng.choices(range(8, 22), [1, 1, 2, 3, 4, 4, 3, 3, 2, 2, 3, 4, 4, 2])[0]
                minute = rng.randrange(60)
                occurred_at = datetime.combine(day, time(hour, minute), tzinfo=tz).isoformat()
                amount = max(1000, int(rng.lognormvariate(0, 0.55) * base_amount))
                status = "FAILED" if rng.random() < 0.035 else "SUCCESS"
                payer = rng.choice(payer_pool) if rng.random() < 0.78 else None
                transaction_id = f"syntx_{persona}_{day:%Y%m%d}_{index:03d}"
                rows.append((transaction_id, shop_id, occurred_at, amount, status, payer, "synthetic"))

    connection.executemany(
        """INSERT INTO synthetic_transactions
           (transaction_id, shop_id, occurred_at, amount_paise, status, payer_token, source)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
