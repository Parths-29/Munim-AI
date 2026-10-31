"""Inventory 2.0: product profiles, sales/wastage outflows, overview, low stock, and reorder suggestions.

All figures are derived from append-only movements. On-hand quantity is only as
good as the recorded counts, receipts, and outflows; the overview says so.
Reorder suggestions are arithmetic proposals, never automatic purchases.
"""

import math
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from app.domain.stock import (
    CategorySummary,
    InventoryOverview,
    OutflowBatchView,
    OutflowBatchWrite,
    OutflowLineResult,
    ProductHistory,
    ProductMovement,
    ProductProfileView,
    ProductProfileWrite,
    ProductStockRow,
    ReorderSuggestion,
)
from app.services.database import connect, current_shop
from app.services.events import append_event
from app.services.inventory import on_hand_quantity
from app.services.proposals import stored_conversion
from app.services.units import canonical_unit

SALES_WINDOW_DAYS = 14
DEFAULT_LEAD_DAYS = 2


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _product(connection, product_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT product_id, name, unit FROM products WHERE shop_id = ? AND product_id = ?", (current_shop(), product_id)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found in this shop.")
    return row


def latest_profile(connection, product_id: str) -> sqlite3.Row | None:
    return connection.execute(
        """SELECT * FROM product_profiles WHERE shop_id = ? AND product_id = ?
           ORDER BY created_at DESC, rowid DESC LIMIT 1""",
        (current_shop(), product_id),
    ).fetchone()


def _profile_view(product_id: str, row: sqlite3.Row | None) -> ProductProfileView:
    return ProductProfileView(
        product_id=product_id,
        category=row["category"] if row else None,
        retail_price_paise=row["retail_price_paise"] if row else None,
        reorder_level=row["reorder_level"] if row else None,
        reorder_quantity=row["reorder_quantity"] if row else None,
        lead_time_days=row["lead_time_days"] if row else None,
        updated_at=datetime.fromisoformat(row["created_at"]) if row else None,
    )


def set_profile(product_id: str, request: ProductProfileWrite, connection: sqlite3.Connection | None = None) -> ProductProfileView:
    """Merchant-set category, selling price, and reorder rules. Supplier invoices never call this."""
    if not request.confirmed:
        raise HTTPException(status_code=409, detail="Merchant confirmation is required to change a product profile.")

    def write(conn):
        product = _product(conn, product_id)
        existing = conn.execute("SELECT * FROM product_profiles WHERE idempotency_key = ?", (request.idempotency_key,)).fetchone()
        if existing:
            if existing["product_id"] != product_id or existing["retail_price_paise"] != request.retail_price_paise:
                raise HTTPException(status_code=409, detail="Idempotency key was already used for a different profile.")
            return _profile_view(product_id, existing)
        previous = latest_profile(conn, product_id)
        conn.execute(
            """INSERT INTO product_profiles (profile_id, shop_id, product_id, category, retail_price_paise, reorder_level,
               reorder_quantity, lead_time_days, idempotency_key, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (f"pprof_{uuid.uuid4().hex[:12]}", current_shop(), product_id, request.category, request.retail_price_paise,
             request.reorder_level, request.reorder_quantity, request.lead_time_days, request.idempotency_key,
             now_utc().isoformat()),
        )
        price_changed = previous is None or previous["retail_price_paise"] != request.retail_price_paise
        append_event(
            conn, event_type="PRODUCT_PROFILE_UPDATED", entity_type="PRODUCT", entity_id=product_id,
            source_event_id=request.idempotency_key, source_channel="text", source_utterance=None, status="POSTED",
            summary=f"Profile set for {product['name']}"
            + (f"; selling price {request.retail_price_paise} paise" if price_changed and request.retail_price_paise is not None else "")
            + (f"; reorder at {request.reorder_level} {product['unit']}" if request.reorder_level is not None else "") + ".",
            idempotency_key=request.idempotency_key,
        )
        return _profile_view(product_id, latest_profile(conn, product_id))

    if connection is not None:
        return write(connection)
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        return write(conn)


def get_profile(product_id: str) -> ProductProfileView:
    with connect() as connection:
        _product(connection, product_id)
        return _profile_view(product_id, latest_profile(connection, product_id))


def record_outflows(request: OutflowBatchWrite, occurred_at: datetime | None = None) -> OutflowBatchView:
    """Sales, wastage, self-use, or supplier returns, as one atomic batch.

    A line that would take recorded stock below zero is rejected (409) with the
    recorded quantity, so the merchant can count stock instead of hiding a gap.
    """
    if not request.confirmed:
        raise HTTPException(status_code=409, detail="Merchant confirmation is required before reducing stock.")
    moment = (occurred_at or now_utc()).astimezone(timezone.utc)
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        return record_outflows_in(connection, request, moment)


def record_outflows_in(connection: sqlite3.Connection, request: OutflowBatchWrite, moment: datetime) -> OutflowBatchView:
    """The outflow batch body, inside the caller's transaction (used by atomic multi-action confirms)."""
    existing = connection.execute(
        "SELECT * FROM stock_outflow_movements WHERE shop_id = ? AND batch_id = (SELECT batch_id FROM stock_outflow_movements WHERE idempotency_key = ?)",
        (current_shop(), f"{request.idempotency_key}:0"),
    ).fetchall()
    if existing:
        same = (len(existing) == len(request.lines) and existing[0]["reason"] == request.reason
                and all(row["product_id"] == line.product_id and row["entered_quantity"] == line.quantity
                        for row, line in zip(sorted(existing, key=lambda r: r["idempotency_key"]), request.lines)))
        if not same:
            raise HTTPException(status_code=409, detail="Idempotency key was already used for a different stock batch.")
        return _batch_view(connection, existing[0]["batch_id"], replay=True)

    batch_id = f"outbatch_{uuid.uuid4().hex[:12]}"
    running: dict[str, int] = {}
    for index, line in enumerate(request.lines):
        product = _product(connection, line.product_id)
        base_unit = product["unit"]
        unit = canonical_unit(line.unit_text) or canonical_unit(base_unit)
        if unit == canonical_unit(base_unit):
            factor = 1
        else:
            factor = stored_conversion(connection, line.product_id, unit)
            if factor is None:
                raise HTTPException(status_code=422, detail={
                    "code": "UNIT_CONVERSION_UNKNOWN",
                    "message": f"How many {base_unit} are in 1 {unit} of {product['name']}? Save a unit conversion first.",
                })
        base_quantity = line.quantity * factor
        if line.product_id not in running:
            running[line.product_id] = on_hand_quantity(connection, line.product_id)[0]
        if base_quantity > running[line.product_id]:
            raise HTTPException(status_code=409, detail={
                "code": "INSUFFICIENT_RECORDED_STOCK",
                "product_id": line.product_id,
                "product_name": product["name"],
                "recorded_on_hand": running[line.product_id],
                "requested": base_quantity,
                "message": f"Records show only {running[line.product_id]} {base_unit} of {product['name']}. Count the shelf to correct stock first.",
            })
        running[line.product_id] -= base_quantity
        price = line.unit_price_paise
        if price is None and request.reason == "SALE":
            profile = latest_profile(connection, line.product_id)
            price = profile["retail_price_paise"] if profile else None
            if price is not None and factor != 1:
                price *= factor  # selling price is per base unit
        amount = price * line.quantity if price is not None else None
        connection.execute(
            """INSERT INTO stock_outflow_movements (movement_id, shop_id, batch_id, product_id, quantity_delta, unit,
               entered_quantity, entered_unit, reason, unit_price_paise, amount_paise, source_channel, source_utterance,
               source_event_id, idempotency_key, status, occurred_at, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'POSTED', ?, ?)""",
            (f"omove_{uuid.uuid4().hex[:12]}", current_shop(), batch_id, line.product_id, -base_quantity, base_unit,
             line.quantity, unit, request.reason, price, amount, request.source_channel, request.source_utterance,
             f"outflow:{batch_id}:{index}", f"{request.idempotency_key}:{index}", moment.isoformat(), now_utc().isoformat()),
        )
    names = ", ".join(f"{line.quantity} {_product(connection, line.product_id)['name']}" for line in request.lines)
    append_event(
        connection, event_type=f"STOCK_{request.reason}_RECORDED", entity_type="STOCK_OUTFLOW", entity_id=batch_id,
        source_event_id=f"outflow:{batch_id}", source_channel=request.source_channel,
        source_utterance=request.source_utterance, status="POSTED",
        summary=f"{request.reason.replace('_', ' ').title()} recorded: {names}.", idempotency_key=f"{request.idempotency_key}:event",
    )
    return _batch_view(connection, batch_id)


def _batch_view(connection, batch_id: str, replay: bool = False) -> OutflowBatchView:
    rows = connection.execute(
        """SELECT m.*, p.name FROM stock_outflow_movements m JOIN products p ON p.shop_id = m.shop_id AND p.product_id = m.product_id
           WHERE m.shop_id = ? AND m.batch_id = ? ORDER BY m.idempotency_key""",
        (current_shop(), batch_id),
    ).fetchall()
    lines = []
    for row in rows:
        on_hand_now = on_hand_quantity(connection, row["product_id"])[0]
        later = connection.execute(
            "SELECT COALESCE(SUM(quantity_delta), 0) FROM stock_outflow_movements WHERE shop_id = ? AND product_id = ? AND rowid > ?",
            (current_shop(), row["product_id"], connection.execute("SELECT rowid FROM stock_outflow_movements WHERE movement_id = ?",
                                                                   (row["movement_id"],)).fetchone()[0]),
        ).fetchone()[0]
        after = on_hand_now - int(later)
        profile = latest_profile(connection, row["product_id"])
        reorder_level = profile["reorder_level"] if profile else None
        lines.append(OutflowLineResult(
            movement_id=row["movement_id"], product_id=row["product_id"], product_name=row["name"], reason=row["reason"],
            entered_quantity=row["entered_quantity"], entered_unit=row["entered_unit"], quantity_delta=row["quantity_delta"],
            unit=row["unit"], unit_price_paise=row["unit_price_paise"], amount_paise=row["amount_paise"],
            on_hand_before=after - row["quantity_delta"], on_hand_after=after,
            low_stock_after=reorder_level is not None and after <= reorder_level,
        ))
    amounts = [line.amount_paise for line in lines]
    return OutflowBatchView(
        batch_id=batch_id, reason=rows[0]["reason"], lines=lines,
        total_amount_paise=sum(amounts) if amounts and all(a is not None for a in amounts) else None,
        idempotent_replay=replay,
    )


# --- Read models ----------------------------------------------------------------

def _last_unit_cost(connection, product_id: str) -> int | None:
    row = connection.execute(
        """SELECT unit_cost_paise, base_units_per_unit FROM stock_receipt_movements
           WHERE shop_id = ? AND product_id = ? AND unit_cost_paise IS NOT NULL ORDER BY created_at DESC, rowid DESC LIMIT 1""",
        (current_shop(), product_id),
    ).fetchone()
    if row is None:
        return None
    return round(row["unit_cost_paise"] / row["base_units_per_unit"])


def _sold(connection, product_id: str, since: datetime) -> int:
    return -int(connection.execute(
        """SELECT COALESCE(SUM(quantity_delta), 0) FROM stock_outflow_movements
           WHERE shop_id = ? AND product_id = ? AND reason = 'SALE' AND occurred_at >= ?""",
        (current_shop(), product_id, since.isoformat()),
    ).fetchone()[0])


def _last_time(connection, sql: str, product_id: str) -> datetime | None:
    value = connection.execute(sql, (current_shop(), product_id)).fetchone()[0]
    return datetime.fromisoformat(value) if value else None


def _row(connection, product: sqlite3.Row, as_of: datetime) -> ProductStockRow:
    product_id = product["product_id"]
    on_hand, movement_count = on_hand_quantity(connection, product_id)
    profile = latest_profile(connection, product_id)
    retail = profile["retail_price_paise"] if profile else None
    reorder_level = profile["reorder_level"] if profile else None
    lead = profile["lead_time_days"] if profile and profile["lead_time_days"] is not None else DEFAULT_LEAD_DAYS
    cost = _last_unit_cost(connection, product_id)
    sold = _sold(connection, product_id, as_of - timedelta(days=SALES_WINDOW_DAYS))
    avg = round(sold / SALES_WINDOW_DAYS, 2)
    cover = round(on_hand / avg, 1) if avg > 0 else None
    if movement_count == 0:
        status = "NO_RECORDS"
    elif on_hand <= 0:
        status = "OUT_OF_STOCK"
    elif (reorder_level is not None and on_hand <= reorder_level) or (cover is not None and cover <= lead):
        status = "LOW"
    else:
        status = "OK"
    target = max(reorder_level or 0, math.ceil(avg * (lead + 7)))  # cover lead time plus about a week of sales
    suggested = max(0, target - on_hand) if status in ("LOW", "OUT_OF_STOCK") else 0
    if suggested and profile and profile["reorder_quantity"]:
        step = profile["reorder_quantity"]
        suggested = math.ceil(suggested / step) * step
    last_count = _last_time(connection, "SELECT MAX(created_at) FROM inventory_movements WHERE shop_id = ? AND product_id = ?", product_id)
    last_move = max(filter(None, [
        last_count,
        _last_time(connection, "SELECT MAX(created_at) FROM stock_receipt_movements WHERE shop_id = ? AND product_id = ?", product_id),
        _last_time(connection, "SELECT MAX(occurred_at) FROM stock_outflow_movements WHERE shop_id = ? AND product_id = ?", product_id),
    ]), default=None)
    return ProductStockRow(
        product_id=product_id, name=product["name"], category=profile["category"] if profile else None, unit=product["unit"],
        on_hand_quantity=on_hand, status=status, retail_price_paise=retail, last_unit_cost_paise=cost,
        stock_value_at_cost_paise=cost * max(on_hand, 0) if cost is not None else None,
        stock_value_at_retail_paise=retail * max(on_hand, 0) if retail is not None else None,
        margin_percent=round((retail - cost) * 100 / retail, 1) if retail and cost is not None else None,
        sold_last_14_days=sold, avg_daily_sales=avg, days_of_cover=cover, reorder_level=reorder_level,
        suggested_reorder_quantity=suggested, last_counted_at=last_count, last_movement_at=last_move,
    )


def inventory_overview(as_of: datetime | None = None) -> InventoryOverview:
    moment = as_of or now_utc()
    with connect() as connection:
        products = connection.execute(
            "SELECT product_id, name, unit FROM products WHERE shop_id = ? ORDER BY name", (current_shop(),)
        ).fetchall()
        rows = [_row(connection, product, moment) for product in products]
        week_sales = int(connection.execute(
            "SELECT COALESCE(SUM(amount_paise), 0) FROM stock_outflow_movements WHERE shop_id = ? AND reason = 'SALE' AND occurred_at >= ?",
            (current_shop(), (moment - timedelta(days=7)).isoformat()),
        ).fetchone()[0])
        wastage_rows = connection.execute(
            """SELECT product_id, -SUM(quantity_delta) AS qty FROM stock_outflow_movements
               WHERE shop_id = ? AND reason = 'WASTAGE' AND occurred_at >= ? GROUP BY product_id""",
            (current_shop(), (moment - timedelta(days=30)).isoformat()),
        ).fetchall()
    cost_by_product = {row.product_id: row.last_unit_cost_paise or 0 for row in rows}
    wastage = sum(int(w["qty"]) * cost_by_product.get(w["product_id"], 0) for w in wastage_rows)
    categories: dict[str, list[ProductStockRow]] = {}
    for row in rows:
        categories.setdefault(row.category or "Uncategorised", []).append(row)
    movers = sorted((row for row in rows if row.sold_last_14_days > 0), key=lambda r: r.sold_last_14_days, reverse=True)
    return InventoryOverview(
        shop_id=current_shop(), as_of=moment, product_count=len(rows),
        out_of_stock=[row.name for row in rows if row.status == "OUT_OF_STOCK"],
        low_stock=[row.name for row in rows if row.status == "LOW"],
        stock_value_at_cost_paise=sum(row.stock_value_at_cost_paise or 0 for row in rows),
        stock_value_at_retail_paise=sum(row.stock_value_at_retail_paise or 0 for row in rows),
        sales_last_7_days_paise=week_sales, wastage_last_30_days_paise=wastage,
        top_movers=[row.name for row in movers[:5]],
        slow_movers=[row.name for row in rows if row.sold_last_14_days == 0 and row.on_hand_quantity > 0][:5],
        categories=[CategorySummary(
            category=name, product_count=len(items),
            low_or_out_count=sum(1 for item in items if item.status in ("LOW", "OUT_OF_STOCK")),
            stock_value_at_cost_paise=sum(item.stock_value_at_cost_paise or 0 for item in items),
        ) for name, items in sorted(categories.items())],
        products=rows,
        caveats=[
            "Quantities come from recorded counts, deliveries, and sales/wastage entries; unrecorded sales are not visible.",
            "Stock value at cost uses the latest recorded supplier unit cost; products without a recorded cost are excluded.",
            "Reorder quantities are suggestions only; nothing is ordered automatically.",
        ],
    )


def reorder_suggestions(as_of: datetime | None = None) -> list[ReorderSuggestion]:
    moment = as_of or now_utc()
    overview = inventory_overview(moment)
    with connect() as connection:
        result = []
        for row in overview.products:
            if row.suggested_reorder_quantity <= 0:
                continue
            profile = latest_profile(connection, row.product_id)
            lead = profile["lead_time_days"] if profile and profile["lead_time_days"] is not None else DEFAULT_LEAD_DAYS
            reason = ("Out of stock" if row.status == "OUT_OF_STOCK" else
                      f"{row.on_hand_quantity} {row.unit} left" + (f", about {row.days_of_cover} days of sales" if row.days_of_cover else ""))
            result.append(ReorderSuggestion(
                product_id=row.product_id, name=row.name, unit=row.unit, on_hand_quantity=row.on_hand_quantity,
                avg_daily_sales=row.avg_daily_sales, lead_time_days=lead, reorder_level=row.reorder_level,
                suggested_quantity=row.suggested_reorder_quantity,
                estimated_cost_paise=row.last_unit_cost_paise * row.suggested_reorder_quantity if row.last_unit_cost_paise else None,
                reason=reason,
            ))
    return sorted(result, key=lambda s: (s.on_hand_quantity > 0, s.on_hand_quantity))


def product_history(product_id: str, limit: int = 50) -> ProductHistory:
    with connect() as connection:
        product = _product(connection, product_id)
        shop = current_shop()
        movements = []
        for row in connection.execute(
            "SELECT quantity_delta, unit, created_at, counted_quantity FROM inventory_movements WHERE shop_id = ? AND product_id = ?",
            (shop, product_id),
        ):
            movements.append(ProductMovement(kind="PHYSICAL_COUNT", quantity_delta=row["quantity_delta"], unit=row["unit"],
                                             occurred_at=datetime.fromisoformat(row["created_at"]),
                                             detail=f"Counted {row['counted_quantity']} {row['unit']}"))
        for row in connection.execute(
            "SELECT quantity_delta, unit, created_at, receipt_id, unit_cost_paise FROM stock_receipt_movements WHERE shop_id = ? AND product_id = ?",
            (shop, product_id),
        ):
            movements.append(ProductMovement(kind="STOCK_RECEIPT", quantity_delta=row["quantity_delta"], unit=row["unit"],
                                             occurred_at=datetime.fromisoformat(row["created_at"]), detail=f"Receipt {row['receipt_id']}"))
        for row in connection.execute(
            "SELECT quantity_delta, unit, occurred_at, reason, amount_paise FROM stock_outflow_movements WHERE shop_id = ? AND product_id = ?",
            (shop, product_id),
        ):
            movements.append(ProductMovement(kind=row["reason"], quantity_delta=row["quantity_delta"], unit=row["unit"],
                                             occurred_at=datetime.fromisoformat(row["occurred_at"]),
                                             detail=f"{row['amount_paise']} paise" if row["amount_paise"] is not None else None))
        on_hand = on_hand_quantity(connection, product_id)[0]
    movements.sort(key=lambda m: m.occurred_at, reverse=True)
    return ProductHistory(product_id=product_id, name=product["name"], unit=product["unit"], on_hand_quantity=on_hand,
                          movements=movements[:min(max(limit, 1), 200)])


def list_catalog() -> list[ProductStockRow]:
    return inventory_overview().products
