"""Product lookup, stockout observations, and verified stock counts."""

import unicodedata
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from app.domain.models import (
    InventoryMovementView,
    ProductCreate,
    ProductResolution,
    ProductView,
    StockBalanceView,
    StockCountCreate,
    StockoutObservationCreate,
    StockoutObservationView,
)
from app.services.database import connect, current_shop
from app.services.events import append_event


RECEIPT_SUM_SQL = """SELECT COALESCE(SUM(quantity_delta), 0), COUNT(*) FROM stock_receipt_movements
    WHERE shop_id = ? AND product_id = ? AND status = 'POSTED'"""
COUNT_SUM_SQL = """SELECT COALESCE(SUM(quantity_delta), 0), COUNT(*) FROM inventory_movements
    WHERE shop_id = ? AND product_id = ? AND status = 'POSTED'"""


OUTFLOW_SUM_SQL = """SELECT COALESCE(SUM(quantity_delta), 0), COUNT(*) FROM stock_outflow_movements
    WHERE shop_id = ? AND product_id = ? AND status = 'POSTED'"""


def on_hand_quantity(connection, product_id: str) -> tuple[int, int]:
    """Derived on-hand = physical-count deltas + stock receipts + outflows (sales, wastage, ...).

    Returns (quantity, movement_count).
    """
    total, rows = 0, 0
    for sql in (COUNT_SUM_SQL, RECEIPT_SUM_SQL, OUTFLOW_SUM_SQL):
        quantity, count = connection.execute(sql, (current_shop(), product_id)).fetchone()
        total += int(quantity)
        rows += int(count)
    return total, rows


def _normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def create_product(request: ProductCreate) -> ProductView:
    if not request.confirmed:
        raise HTTPException(status_code=409, detail="Merchant confirmation is required before creating a product.")
    name = request.name.strip()
    unit = request.unit.strip()
    if not name or not unit:
        raise HTTPException(status_code=422, detail="Product name and unit cannot be blank.")
    aliases = list(dict.fromkeys([name, *(alias.strip() for alias in request.aliases if alias.strip())]))
    now = datetime.now(timezone.utc).isoformat()
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        existing_rows = connection.execute(
            "SELECT product_id, name, unit FROM products WHERE idempotency_key = ?",
            (request.idempotency_key,),
        ).fetchall()
        if existing_rows:
            existing = existing_rows[0]
            if existing["name"] != name or existing["unit"] != unit:
                raise HTTPException(status_code=409, detail="Idempotency key was already used for different product data.")
            stored_aliases = connection.execute(
                "SELECT alias_normalized FROM product_aliases WHERE shop_id = ? AND product_id = ?",
                (current_shop(), existing["product_id"]),
            ).fetchall()
            if {row["alias_normalized"] for row in stored_aliases} != {_normalize(alias) for alias in aliases}:
                raise HTTPException(status_code=409, detail="Idempotency key was already used with different product aliases.")
            return _product_view(connection, existing["product_id"])

        product_id = f"product_{uuid.uuid4().hex[:12]}"
        connection.execute(
            "INSERT INTO products(product_id, shop_id, name, unit, idempotency_key, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (product_id, current_shop(), name, unit, request.idempotency_key, now),
        )
        for alias in aliases:
            connection.execute(
                "INSERT INTO product_aliases(alias_id, shop_id, product_id, alias, alias_normalized) VALUES (?, ?, ?, ?, ?)",
                (f"alias_{uuid.uuid4().hex[:12]}", current_shop(), product_id, alias, _normalize(alias)),
            )
        append_event(
            connection,
            event_type="PRODUCT_CREATED",
            entity_type="PRODUCT",
            entity_id=product_id,
            source_event_id=request.idempotency_key,
            source_channel=request.source_channel,
            source_utterance=request.source_utterance,
            status="POSTED",
            summary=f"Product record created for {name}.",
            idempotency_key=request.idempotency_key,
        )
        return _product_view(connection, product_id)


def resolve_product(query: str) -> ProductResolution:
    normalized = _normalize(query)
    with connect() as connection:
        rows = connection.execute(
            """SELECT DISTINCT p.product_id
               FROM products p
               JOIN product_aliases a ON a.shop_id = p.shop_id AND a.product_id = p.product_id
               WHERE p.shop_id = ? AND a.alias_normalized = ?
               ORDER BY p.name""",
            (current_shop(), normalized),
        ).fetchall()
        matches = [_product_view(connection, row["product_id"]) for row in rows]
    status = "NOT_FOUND" if not matches else "RESOLVED" if len(matches) == 1 else "AMBIGUOUS"
    return ProductResolution(status=status, query=query, matches=matches)


def record_stockout_observation(request: StockoutObservationCreate) -> StockoutObservationView:
    if not request.confirmed:
        raise HTTPException(status_code=409, detail="Merchant confirmation is required to record a stockout observation.")
    now = datetime.now(timezone.utc).isoformat()
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        product = connection.execute(
            "SELECT product_id FROM products WHERE shop_id = ? AND product_id = ?",
            (current_shop(), request.product_id),
        ).fetchone()
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found in this demo shop.")
        existing_rows = connection.execute(
            """SELECT * FROM stockout_observations
               WHERE idempotency_key = ? OR (shop_id = ? AND source_event_id = ?) LIMIT 2""",
            (request.idempotency_key, current_shop(), request.source_event_id),
        ).fetchall()
        if len(existing_rows) > 1:
            raise HTTPException(status_code=409, detail="Idempotency key and source event resolve to different observations.")
        if existing_rows:
            existing = existing_rows[0]
            if existing["product_id"] != request.product_id or existing["source_utterance"] != request.source_utterance:
                raise HTTPException(status_code=409, detail="Idempotency key was already used for a different stockout observation.")
            return _stockout_view(existing, idempotent_replay=True)

        observation_id = f"stockout_{uuid.uuid4().hex[:12]}"
        connection.execute(
            """INSERT INTO stockout_observations
               (observation_id, shop_id, product_id, source_event_id, idempotency_key, source_utterance, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'OBSERVED', ?)""",
            (observation_id, current_shop(), request.product_id, request.source_event_id, request.idempotency_key, request.source_utterance, now),
        )
        append_event(
            connection,
            event_type="STOCKOUT_OBSERVED",
            entity_type="PRODUCT",
            entity_id=request.product_id,
            source_event_id=request.source_event_id,
            source_channel=request.source_channel,
            source_utterance=request.source_utterance,
            status="OBSERVED",
            summary="Merchant reported a stockout; on-hand quantity has not been changed.",
            idempotency_key=request.idempotency_key,
        )
        row = connection.execute(
            "SELECT * FROM stockout_observations WHERE observation_id = ?",
            (observation_id,),
        ).fetchone()
    return _stockout_view(row)


def record_stock_count(request: StockCountCreate) -> InventoryMovementView:
    if not request.confirmed:
        raise HTTPException(status_code=409, detail="Merchant confirmation is required before recording a physical stock count.")
    now = datetime.now(timezone.utc).isoformat()
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        product = connection.execute(
            "SELECT product_id, name, unit FROM products WHERE shop_id = ? AND product_id = ?",
            (current_shop(), request.product_id),
        ).fetchone()
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found in this demo shop.")
        existing_rows = connection.execute(
            """SELECT * FROM inventory_movements
               WHERE idempotency_key = ? OR (shop_id = ? AND source_event_id = ?) LIMIT 2""",
            (request.idempotency_key, current_shop(), request.source_event_id),
        ).fetchall()
        if len(existing_rows) > 1:
            raise HTTPException(status_code=409, detail="Idempotency key and source event resolve to different stock movements.")
        if existing_rows:
            existing = existing_rows[0]
            if existing["product_id"] != request.product_id or existing["counted_quantity"] != request.counted_quantity:
                raise HTTPException(status_code=409, detail="Idempotency key was already used for a different stock count.")
            return _movement_view(existing, idempotent_replay=True)

        current_quantity, _ = on_hand_quantity(connection, request.product_id)
        delta = request.counted_quantity - current_quantity
        movement_id = f"movement_{uuid.uuid4().hex[:12]}"
        connection.execute(
            """INSERT INTO inventory_movements
               (movement_id, shop_id, product_id, quantity_delta, counted_quantity, unit, reason,
                source_event_id, idempotency_key, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'PHYSICAL_COUNT', ?, ?, 'POSTED', ?)""",
            (movement_id, current_shop(), request.product_id, delta, request.counted_quantity, product["unit"], request.source_event_id, request.idempotency_key, now),
        )
        append_event(
            connection,
            event_type="STOCK_COUNT_RECORDED",
            entity_type="PRODUCT",
            entity_id=request.product_id,
            source_event_id=request.source_event_id,
            source_channel=request.source_channel,
            source_utterance=request.source_utterance,
            status="POSTED",
            summary=f"Physical count recorded: {request.counted_quantity} {product['unit']} of {product['name']}.",
            idempotency_key=request.idempotency_key,
        )
        row = connection.execute("SELECT * FROM inventory_movements WHERE movement_id = ?", (movement_id,)).fetchone()
    return _movement_view(row)


def get_stock_balance(product_id: str) -> StockBalanceView:
    with connect() as connection:
        product = connection.execute(
            "SELECT product_id, name, unit FROM products WHERE shop_id = ? AND product_id = ?",
            (current_shop(), product_id),
        ).fetchone()
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found in this demo shop.")
        on_hand, movement_count = on_hand_quantity(connection, product_id)
    return StockBalanceView(
        product_id=product["product_id"],
        product_name=product["name"],
        on_hand_quantity=on_hand,
        unit=product["unit"],
        movement_count=movement_count,
    )


def _product_view(connection, product_id: str) -> ProductView:
    product = connection.execute(
        "SELECT product_id, name, unit FROM products WHERE shop_id = ? AND product_id = ?",
        (current_shop(), product_id),
    ).fetchone()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found in this demo shop.")
    aliases = connection.execute(
        "SELECT alias FROM product_aliases WHERE shop_id = ? AND product_id = ? ORDER BY alias",
        (current_shop(), product_id),
    ).fetchall()
    return ProductView(product_id=product["product_id"], name=product["name"], aliases=[row["alias"] for row in aliases], unit=product["unit"])


def _stockout_view(row, idempotent_replay: bool = False) -> StockoutObservationView:
    return StockoutObservationView(
        observation_id=row["observation_id"],
        product_id=row["product_id"],
        status=row["status"],
        source_event_id=row["source_event_id"],
        created_at=datetime.fromisoformat(row["created_at"]),
        idempotent_replay=idempotent_replay,
    )


def _movement_view(row, idempotent_replay: bool = False) -> InventoryMovementView:
    return InventoryMovementView(
        movement_id=row["movement_id"],
        product_id=row["product_id"],
        quantity_delta=row["quantity_delta"],
        counted_quantity=row["counted_quantity"],
        unit=row["unit"],
        reason=row["reason"],
        status=row["status"],
        source_event_id=row["source_event_id"],
        created_at=datetime.fromisoformat(row["created_at"]),
        idempotent_replay=idempotent_replay,
    )


def create_unit_conversion(product_id: str, request):
    """Record a merchant-confirmed pack size, e.g. 1 case = 24 packet. Append-only; latest wins."""
    from app.domain.intake import UnitConversionView
    from app.services.units import canonical_unit

    if not request.confirmed:
        raise HTTPException(status_code=409, detail="Merchant confirmation is required before saving a unit conversion.")
    unit = canonical_unit(request.unit)
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        product = connection.execute(
            "SELECT product_id, name, unit FROM products WHERE shop_id = ? AND product_id = ?", (current_shop(), product_id)
        ).fetchone()
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found in this demo shop.")
        if unit == canonical_unit(product["unit"]):
            raise HTTPException(status_code=422, detail="That is already the product's base unit.")
        existing = connection.execute(
            "SELECT * FROM product_unit_conversions WHERE idempotency_key = ?", (request.idempotency_key,)
        ).fetchone()
        if existing:
            if existing["product_id"] != product_id or existing["unit"] != unit or existing["base_units_per_unit"] != request.base_units_per_unit:
                raise HTTPException(status_code=409, detail="Idempotency key was already used for a different conversion.")
            row = existing
        else:
            conversion_id = f"conv_{uuid.uuid4().hex[:12]}"
            connection.execute(
                """INSERT INTO product_unit_conversions (conversion_id, shop_id, product_id, unit, base_units_per_unit, idempotency_key, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (conversion_id, current_shop(), product_id, unit, request.base_units_per_unit, request.idempotency_key,
                 datetime.now(timezone.utc).isoformat()),
            )
            append_event(
                connection,
                event_type="UNIT_CONVERSION_RECORDED",
                entity_type="PRODUCT",
                entity_id=product_id,
                source_event_id=request.idempotency_key,
                source_channel="text",
                source_utterance=None,
                status="POSTED",
                summary=f"Merchant confirmed 1 {unit} of {product['name']} = {request.base_units_per_unit} {product['unit']}.",
                idempotency_key=request.idempotency_key,
            )
            row = connection.execute("SELECT * FROM product_unit_conversions WHERE conversion_id = ?", (conversion_id,)).fetchone()
        return UnitConversionView(
            conversion_id=row["conversion_id"], product_id=product_id, unit=row["unit"], base_unit=product["unit"],
            base_units_per_unit=row["base_units_per_unit"], created_at=datetime.fromisoformat(row["created_at"]),
        )


def list_unit_conversions(product_id: str):
    from app.domain.intake import UnitConversionView

    with connect() as connection:
        product = connection.execute(
            "SELECT product_id, unit FROM products WHERE shop_id = ? AND product_id = ?", (current_shop(), product_id)
        ).fetchone()
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found in this demo shop.")
        rows = connection.execute(
            "SELECT * FROM product_unit_conversions WHERE shop_id = ? AND product_id = ? ORDER BY created_at DESC",
            (current_shop(), product_id),
        ).fetchall()
    return [UnitConversionView(
        conversion_id=row["conversion_id"], product_id=product_id, unit=row["unit"], base_unit=product["unit"],
        base_units_per_unit=row["base_units_per_unit"], created_at=datetime.fromisoformat(row["created_at"]),
    ) for row in rows]
