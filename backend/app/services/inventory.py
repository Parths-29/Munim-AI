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
from app.services.database import DEMO_SHOP_ID, connect
from app.services.events import append_event


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
                (DEMO_SHOP_ID, existing["product_id"]),
            ).fetchall()
            if {row["alias_normalized"] for row in stored_aliases} != {_normalize(alias) for alias in aliases}:
                raise HTTPException(status_code=409, detail="Idempotency key was already used with different product aliases.")
            return _product_view(connection, existing["product_id"])

        product_id = f"product_{uuid.uuid4().hex[:12]}"
        connection.execute(
            "INSERT INTO products(product_id, shop_id, name, unit, idempotency_key, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (product_id, DEMO_SHOP_ID, name, unit, request.idempotency_key, now),
        )
        for alias in aliases:
            connection.execute(
                "INSERT INTO product_aliases(alias_id, shop_id, product_id, alias, alias_normalized) VALUES (?, ?, ?, ?, ?)",
                (f"alias_{uuid.uuid4().hex[:12]}", DEMO_SHOP_ID, product_id, alias, _normalize(alias)),
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
            (DEMO_SHOP_ID, normalized),
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
            (DEMO_SHOP_ID, request.product_id),
        ).fetchone()
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found in this demo shop.")
        existing_rows = connection.execute(
            """SELECT * FROM stockout_observations
               WHERE idempotency_key = ? OR (shop_id = ? AND source_event_id = ?) LIMIT 2""",
            (request.idempotency_key, DEMO_SHOP_ID, request.source_event_id),
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
            (observation_id, DEMO_SHOP_ID, request.product_id, request.source_event_id, request.idempotency_key, request.source_utterance, now),
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
            (DEMO_SHOP_ID, request.product_id),
        ).fetchone()
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found in this demo shop.")
        existing_rows = connection.execute(
            """SELECT * FROM inventory_movements
               WHERE idempotency_key = ? OR (shop_id = ? AND source_event_id = ?) LIMIT 2""",
            (request.idempotency_key, DEMO_SHOP_ID, request.source_event_id),
        ).fetchall()
        if len(existing_rows) > 1:
            raise HTTPException(status_code=409, detail="Idempotency key and source event resolve to different stock movements.")
        if existing_rows:
            existing = existing_rows[0]
            if existing["product_id"] != request.product_id or existing["counted_quantity"] != request.counted_quantity:
                raise HTTPException(status_code=409, detail="Idempotency key was already used for a different stock count.")
            return _movement_view(existing, idempotent_replay=True)

        current_quantity = int(connection.execute(
            "SELECT COALESCE(SUM(quantity_delta), 0) FROM inventory_movements WHERE shop_id = ? AND product_id = ? AND status = 'POSTED'",
            (DEMO_SHOP_ID, request.product_id),
        ).fetchone()[0])
        delta = request.counted_quantity - current_quantity
        movement_id = f"movement_{uuid.uuid4().hex[:12]}"
        connection.execute(
            """INSERT INTO inventory_movements
               (movement_id, shop_id, product_id, quantity_delta, counted_quantity, unit, reason,
                source_event_id, idempotency_key, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'PHYSICAL_COUNT', ?, ?, 'POSTED', ?)""",
            (movement_id, DEMO_SHOP_ID, request.product_id, delta, request.counted_quantity, product["unit"], request.source_event_id, request.idempotency_key, now),
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
            (DEMO_SHOP_ID, product_id),
        ).fetchone()
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found in this demo shop.")
        stock = connection.execute(
            """SELECT COALESCE(SUM(quantity_delta), 0) AS on_hand, COUNT(*) AS movement_count
               FROM inventory_movements WHERE shop_id = ? AND product_id = ? AND status = 'POSTED'""",
            (DEMO_SHOP_ID, product_id),
        ).fetchone()
    return StockBalanceView(
        product_id=product["product_id"],
        product_name=product["name"],
        on_hand_quantity=int(stock["on_hand"]),
        unit=product["unit"],
        movement_count=int(stock["movement_count"]),
    )


def _product_view(connection, product_id: str) -> ProductView:
    product = connection.execute(
        "SELECT product_id, name, unit FROM products WHERE shop_id = ? AND product_id = ?",
        (DEMO_SHOP_ID, product_id),
    ).fetchone()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found in this demo shop.")
    aliases = connection.execute(
        "SELECT alias FROM product_aliases WHERE shop_id = ? AND product_id = ? ORDER BY alias",
        (DEMO_SHOP_ID, product_id),
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
