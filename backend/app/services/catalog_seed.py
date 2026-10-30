"""Synthetic shop catalogs with 30 days of simulated stock history (kirana, tea stall, medical store).

Everything here is clearly synthetic demo data. Seeding is deterministic and
replay-safe: every row has a stable ID/idempotency key and is inserted with
INSERT OR IGNORE, so running it twice changes nothing. Products that already
have stock movements (for example a merchant's own data) never get history.
"""

import hashlib
import json
import random
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.domain.models import CustomerCreate, ProductCreate, SupplierCreate
from app.domain.stock import ProductProfileWrite
from app.services.database import SHOPS, connect, use_shop
from app.services.inventory import create_product
from app.services.ledger import create_customer, normalize_alias
from app.services.stock import set_profile
from app.services.suppliers import create_supplier

TZ = ZoneInfo("Asia/Kolkata")
HISTORY_DAYS = 30


@dataclass(frozen=True)
class Item:
    sku: str
    name: str
    unit: str
    category: str
    retail: int          # selling price per unit, paise (merchant-set)
    cost: int            # supplier cost per unit, paise
    daily: float         # average units sold per day
    reorder_level: int
    reorder_qty: int
    supplier: str
    aliases: tuple[str, ...] = ()
    lead: int = 2
    wastage: float = 0.0  # share of daily sales wasted (perishables)
    end_state: str = "normal"  # normal | low | out | slow
    key: str | None = None    # reuse an existing seed product key


KIRANA = [
    Item("atta5", "Aashirvaad Atta 5kg", "packet", "Staples", 28500, 25600, 1.2, 4, 10, "Sharma Distributors", ("Atta", "आटा", "Aata")),
    Item("toor", "Toor Dal 1kg", "packet", "Staples", 16000, 14200, 1.5, 5, 10, "Sharma Distributors", ("Toor dal", "Arhar dal", "तूर दाल")),
    Item("rice", "Basmati Rice 1kg", "packet", "Staples", 12000, 10400, 1.4, 5, 10, "Sharma Distributors", ("Chawal", "Rice", "चावल")),
    Item("sugar", "Sugar 1kg", "packet", "Staples", 4800, 4300, 3.0, 8, 20, "Sharma Distributors", ("Cheeni", "Chini", "चीनी", "Shakkar")),
    Item("salt", "Tata Salt 1kg", "packet", "Staples", 2800, 2400, 1.8, 6, 20, "Sharma Distributors", ("Namak", "Salt", "नमक")),
    Item("oil", "Fortune Sunflower Oil 1L", "bottle", "Staples", 16500, 15000, 1.6, 4, 12, "Sharma Distributors", ("Oil", "Tel", "तेल", "Sunflower oil")),
    Item("mustard", "Mustard Oil 1L", "bottle", "Staples", 17500, 15800, 0.8, 3, 6, "Sharma Distributors", ("Sarson tel", "Mustard oil")),
    Item("besan", "Besan 500g", "packet", "Staples", 6000, 5200, 0.7, 3, 10, "Sharma Distributors", ("Besan", "बेसन"), end_state="low"),
    Item("poha", "Poha 500g", "packet", "Staples", 4500, 3800, 0.9, 3, 10, "Sharma Distributors", ("Poha", "पोहा")),
    Item("milk", "Amul Taaza 500ml", "packet", "Dairy", 2800, 2500, 14.0, 10, 30, "Gupta Dairy", ("Amul Taaza", "Amul Taaza 500 ml", "Taaza", "Doodh", "दूध"),
         lead=1, wastage=0.03, key="seed-product-amul-taaza-v1"),
    Item("dahi", "Dahi", "cup", "Dairy", 3500, 3000, 6.0, 6, 20, "Gupta Dairy", ("Curd", "Dahi", "दही"), lead=1, wastage=0.04,
         key="seed-product-dahi-v1"),
    Item("butter", "Amul Butter 100g", "packet", "Dairy", 6000, 5400, 1.1, 4, 10, "Gupta Dairy", ("Butter", "Makhan", "मक्खन")),
    Item("paneer", "Paneer 200g", "packet", "Dairy", 9000, 7800, 1.3, 3, 8, "Gupta Dairy", ("Paneer", "पनीर"), lead=1, wastage=0.05),
    Item("eggs", "Eggs", "piece", "Dairy", 700, 560, 24.0, 30, 90, "Gupta Dairy", ("Anda", "Ande", "Egg", "अंडा"), lead=1, end_state="low"),
    Item("bread", "Bread", "packet", "Bakery", 4500, 3800, 5.0, 5, 15, "Modern Bakery", ("Bread", "Double roti", "ब्रेड"), lead=1, wastage=0.06),
    Item("rusk", "Rusk", "packet", "Bakery", 4000, 3200, 1.0, 3, 10, "Modern Bakery", ("Toast", "Rusk")),
    Item("maggi", "Maggi", "pack", "Snacks", 1400, 1150, 6.0, 12, 48, "Sharma Distributors", ("Maggi noodles", "noodles", "मैगी"),
         key="seed-product-maggi-v1"),
    Item("parleg", "Parle-G", "packet", "Snacks", 1000, 820, 9.0, 15, 48, "Sharma Distributors", ("Parle G", "Parle", "पारले जी")),
    Item("goodday", "Good Day", "packet", "Snacks", 3000, 2550, 2.5, 6, 24, "Sharma Distributors", ("Good day biscuit",)),
    Item("lays", "Lays Classic", "packet", "Snacks", 2000, 1650, 3.5, 10, 30, "Sharma Distributors", ("Lays", "Chips")),
    Item("kurkure", "Kurkure", "packet", "Snacks", 2000, 1650, 3.0, 10, 30, "Sharma Distributors", ("Kurkure", "कुरकुरे"), end_state="out"),
    Item("bhujia", "Haldiram Bhujia 200g", "packet", "Snacks", 5500, 4700, 0.8, 3, 10, "Sharma Distributors", ("Bhujia", "Namkeen", "भुजिया")),
    Item("tea", "Tata Tea Premium 250g", "packet", "Beverages", 14500, 12800, 1.2, 4, 12, "Sharma Distributors", ("Chai patti", "Tea", "चाय पत्ती")),
    Item("coffee", "Bru Coffee 50g", "packet", "Beverages", 11000, 9600, 0.3, 2, 6, "Sharma Distributors", ("Coffee", "Bru"), end_state="slow"),
    Item("coke", "Coca-Cola 750ml", "bottle", "Beverages", 4000, 3300, 2.0, 6, 24, "Sharma Distributors", ("Coke", "Coca cola", "Cold drink")),
    Item("thumsup", "Thums Up 750ml", "bottle", "Beverages", 4000, 3300, 2.2, 6, 24, "Sharma Distributors", ("Thums up", "Thumbs up")),
    Item("frooti", "Frooti 200ml", "piece", "Beverages", 1000, 800, 4.0, 10, 40, "Sharma Distributors", ("Frooti", "Mango drink")),
    Item("water", "Bisleri 1L", "bottle", "Beverages", 2000, 1500, 5.0, 12, 36, "Sharma Distributors", ("Paani", "Water", "Bisleri", "पानी")),
    Item("soap", "Lifebuoy Soap", "piece", "Personal Care", 3500, 2900, 1.5, 6, 24, "Sharma Distributors", ("Sabun", "Lifebuoy", "साबुन")),
    Item("paste", "Colgate 100g", "piece", "Personal Care", 6000, 5100, 1.0, 4, 12, "Sharma Distributors", ("Colgate", "Toothpaste", "Manjan")),
    Item("shampoo", "Clinic Plus Sachet", "sachet", "Personal Care", 200, 150, 10.0, 24, 96, "Sharma Distributors", ("Shampoo", "Clinic plus")),
    Item("hairoil", "Parachute Oil 100ml", "bottle", "Personal Care", 5000, 4300, 0.6, 3, 10, "Sharma Distributors", ("Nariyal tel", "Parachute")),
    Item("surf", "Surf Excel 1kg", "packet", "Household", 14000, 12300, 0.6, 3, 8, "Sharma Distributors", ("Surf", "Detergent", "सर्फ")),
    Item("vim", "Vim Bar", "piece", "Household", 1000, 820, 1.8, 6, 24, "Sharma Distributors", ("Vim",)),
    Item("agarbatti", "Agarbatti", "packet", "Household", 2000, 1500, 1.2, 4, 20, "Sharma Distributors", ("Agarbatti", "अगरबत्ती")),
    Item("matchbox", "Matchbox", "piece", "Household", 200, 140, 4.0, 20, 100, "Sharma Distributors", ("Machis", "Matchbox", "माचिस")),
]

TEA_STALL = [
    Item("milk", "Doodh 1L", "packet", "Dairy", 6600, 6000, 9.0, 6, 20, "Verma Dairy", ("Doodh", "Milk", "दूध"), lead=1, wastage=0.02),
    Item("chaipatti", "Chai Patti 250g", "packet", "Tea Supplies", 14000, 12500, 1.1, 3, 8, "Balaji Traders", ("Chai patti", "Patti", "चाय पत्ती", "Tea leaves")),
    Item("cheeni", "Cheeni 1kg", "packet", "Tea Supplies", 4800, 4300, 2.0, 4, 10, "Balaji Traders", ("Cheeni", "Chini", "Sugar", "चीनी")),
    Item("adrak", "Adrak 250g", "packet", "Tea Supplies", 4000, 3000, 1.5, 3, 8, "Balaji Traders", ("Adrak", "Ginger", "अदरक"), lead=1, wastage=0.05),
    Item("elaichi", "Elaichi 50g", "packet", "Tea Supplies", 15000, 13000, 0.3, 2, 4, "Balaji Traders", ("Elaichi", "Cardamom", "इलायची"), end_state="low"),
    Item("cups", "Paper Cup", "piece", "Disposables", 100, 60, 140.0, 150, 500, "Balaji Traders", ("Cup", "Paper cup", "Glass", "कप")),
    Item("kulhad", "Kulhad", "piece", "Disposables", 500, 300, 25.0, 40, 200, "Balaji Traders", ("Kulhad", "कुल्हड़"), wastage=0.04),
    Item("parleg", "Parle-G", "packet", "Snacks", 1000, 820, 8.0, 12, 48, "Balaji Traders", ("Parle G", "Parle", "पारले जी")),
    Item("goodday", "Good Day", "packet", "Snacks", 1000, 820, 4.0, 8, 24, "Balaji Traders", ("Good day",)),
    Item("rusk", "Rusk", "packet", "Snacks", 4000, 3200, 1.5, 3, 10, "Balaji Traders", ("Rusk", "Toast")),
    Item("bunmaska", "Bun", "piece", "Bakery", 1500, 1000, 12.0, 10, 40, "Verma Dairy", ("Bun", "Bun maska", "Pav"), lead=1, wastage=0.06),
    Item("mathri", "Mathri", "packet", "Snacks", 3000, 2200, 1.2, 3, 10, "Balaji Traders", ("Mathri", "मठरी"), end_state="slow"),
    Item("maggi", "Maggi", "pack", "Snacks", 1400, 1150, 5.0, 10, 48, "Balaji Traders", ("Maggi", "मैगी")),
    Item("water", "Bisleri 1L", "bottle", "Beverages", 2000, 1500, 6.0, 12, 36, "Balaji Traders", ("Paani", "Water", "Bisleri")),
    Item("matchbox", "Matchbox", "piece", "Supplies", 200, 140, 2.0, 10, 50, "Balaji Traders", ("Machis", "Matchbox")),
    Item("gas", "LPG Refill", "piece", "Supplies", 0, 90000, 0.07, 1, 1, "Balaji Traders", ("Gas", "Cylinder", "LPG", "सिलेंडर"), lead=1, end_state="slow"),
]

MEDICAL = [
    Item("pcm", "Paracetamol 500mg", "strip", "Fever & Pain", 3000, 2100, 6.0, 15, 50, "Medi Wholesale", ("Paracetamol", "PCM", "Dolo")),
    Item("crocin", "Crocin Advance", "strip", "Fever & Pain", 3500, 2500, 3.0, 10, 30, "Medi Wholesale", ("Crocin",)),
    Item("ors", "ORS Sachet", "sachet", "Hydration", 2000, 1400, 4.0, 15, 50, "Medi Wholesale", ("ORS", "Electral")),
    Item("dettol", "Dettol 125ml", "bottle", "First Aid", 7000, 5600, 0.8, 3, 10, "Medi Wholesale", ("Dettol",)),
    Item("bandaid", "Band-Aid", "packet", "First Aid", 5000, 3800, 1.0, 4, 12, "Medi Wholesale", ("Bandage", "Band aid")),
    Item("vicks", "Vicks VapoRub 25ml", "piece", "Cold & Cough", 9500, 7800, 1.2, 4, 12, "Medi Wholesale", ("Vicks",), end_state="low"),
    Item("digene", "Digene Tablets", "strip", "Digestive", 4000, 3000, 1.5, 5, 20, "Medi Wholesale", ("Digene", "Gas ki goli")),
    Item("syrup", "Cough Syrup 100ml", "bottle", "Cold & Cough", 11000, 8800, 0.9, 3, 10, "Medi Wholesale", ("Cough syrup", "Khansi ki dawai")),
]

CATALOGS = {"kirana": KIRANA, "tea_stall": TEA_STALL, "medical_store": MEDICAL}
SUPPLIER_ALIASES = {
    "Sharma Distributors": ("Sharma Distributors", "Sharma ji distributor"),
    "Gupta Dairy": ("Gupta Dairy", "Gupta doodh wale"),
    "Modern Bakery": ("Modern Bakery", "Bread wale"),
    "Verma Dairy": ("Verma Dairy", "Verma doodh wale"),
    "Balaji Traders": ("Balaji Traders", "Balaji"),
    "Medi Wholesale": ("Medi Wholesale",),
}
SUPPLIER_KEYS = {"Sharma Distributors": "seed-supplier-sharma-distributors-v1", "Gupta Dairy": "seed-supplier-gupta-dairy-v1"}
# (display name, aliases, [(days_ago, CREDIT|REPAYMENT, paise)])
CUSTOMERS = {
    "kirana": [
        ("Meena ben", ("Meena", "Meena ben", "मीना बेन"), [(19, "CREDIT", 42000), (6, "CREDIT", 18000)]),
        ("Patil kaka", ("Patil", "Patil kaka", "पाटील काका"), [(26, "CREDIT", 115000), (12, "REPAYMENT", 50000), (3, "CREDIT", 20000)]),
        ("Asha didi", ("Asha", "Asha didi"), [(8, "CREDIT", 26000)]),
        ("Iqbal bhai", ("Iqbal", "Iqbal bhai"), [(22, "CREDIT", 30000), (9, "REPAYMENT", 30000)]),
    ],
    "tea_stall": [
        ("Ramesh driver", ("Ramesh", "Ramesh driver", "रमेश"), [(20, "CREDIT", 18000), (11, "CREDIT", 9000)]),
        ("Sunita didi", ("Sunita", "Sunita didi"), [(5, "CREDIT", 6000)]),
        ("Office wale Sharma ji", ("Sharma ji", "Office Sharma"), [(17, "CREDIT", 45000), (2, "REPAYMENT", 15000)]),
    ],
    "medical_store": [
        ("Joshi uncle", ("Joshi", "Joshi uncle"), [(16, "CREDIT", 64000)]),
    ],
}


def _id(prefix: str, *parts: str) -> str:
    return f"{prefix}_{hashlib.sha1(':'.join(parts).encode()).hexdigest()[:12]}"


def _stamp(day: datetime, hour: int) -> str:
    return datetime.combine(day.date(), time(hour, 0), tzinfo=TZ).astimezone(timezone.utc).isoformat()


def seed_catalog(persona: str, now: datetime | None = None) -> dict:
    """Seed one persona shop. Returns counts of what exists afterwards."""
    shop_id = SHOPS[persona]
    items = CATALOGS[persona]
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(TZ)
    rng = random.Random(f"munim-{persona}-v1")
    with use_shop(shop_id):
        suppliers = {}
        for name in sorted({item.supplier for item in items}):
            legacy = persona == "kirana" and name in SUPPLIER_KEYS
            supplier = create_supplier(SupplierCreate(
                display_name=name, aliases=[name] if legacy else list(SUPPLIER_ALIASES.get(name, (name,))), confirmed=True,
                idempotency_key=SUPPLIER_KEYS.get(name, f"seed-{persona}-supplier-{normalize_alias(name)}-v1") if persona == "kirana"
                else f"seed-{persona}-supplier-{normalize_alias(name)}-v1",
            ))
            suppliers[name] = supplier.supplier_id
        products = {}
        for item in items:
            if item.key and persona == "kirana":
                product = _existing_or_create(item)  # replay the original demo product exactly (aliases unchanged)
            else:
                product = create_product(ProductCreate(name=item.name, unit=item.unit, aliases=list(item.aliases), confirmed=True,
                                                       idempotency_key=f"seed-{persona}-product-{item.sku}-v1"))
            products[item.sku] = product.product_id
            set_profile(product.product_id, ProductProfileWrite(
                category=item.category, retail_price_paise=item.retail or None, reorder_level=item.reorder_level,
                reorder_quantity=item.reorder_qty, lead_time_days=item.lead, confirmed=True,
                idempotency_key=f"seed-{persona}-profile-{item.sku}-v1",
            ))

        with connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for item in items:
                product_id = products[item.sku]
                has_history = connection.execute(
                    """SELECT (SELECT COUNT(*) FROM inventory_movements WHERE shop_id = ? AND product_id = ?)
                            + (SELECT COUNT(*) FROM stock_receipt_movements WHERE shop_id = ? AND product_id = ?)
                            + (SELECT COUNT(*) FROM stock_outflow_movements WHERE shop_id = ? AND product_id = ?)""",
                    (shop_id, product_id) * 3,
                ).fetchone()[0]
                if has_history:
                    continue
                _simulate(connection, shop_id, persona, item, product_id, suppliers[item.supplier], today, rng)
        for name, aliases, entries in CUSTOMERS.get(persona, []):
            customer = create_customer(CustomerCreate(display_name=name, aliases=list(aliases), confirmed=True,
                                                      idempotency_key=f"seed-{persona}-customer-{normalize_alias(name)}-v1"))
            with connect() as connection:
                for index, (days_ago, kind, paise) in enumerate(entries):
                    moment = _stamp(today - timedelta(days=days_ago), 18)
                    key = f"seed-{persona}-ledger-{normalize_alias(name)}-{index}-v1"
                    connection.execute(
                        """INSERT OR IGNORE INTO ledger_entries (entry_id, shop_id, customer_id, entry_type, amount_paise, source_event_id,
                           idempotency_key, status, created_at, occurred_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'POSTED', ?, ?)""",
                        (_id("entry", key), shop_id, customer.customer_id, kind, paise, key, key, moment, moment),
                    )
        with connect() as connection:
            counts = {table: connection.execute(f"SELECT COUNT(*) FROM {table} WHERE shop_id = ?", (shop_id,)).fetchone()[0]
                      for table in ("products", "stock_outflow_movements", "stock_receipts", "supplier_payable_entries", "customers")}
    return counts


def _existing_or_create(item: Item):
    return create_product(ProductCreate(name=_legacy_name(item), unit=item.unit if item.sku != "maggi" else "pack",
                                        aliases=list(_legacy_aliases(item)), confirmed=True, idempotency_key=item.key))


def _legacy_name(item: Item) -> str:
    # The original seed created these with shorter names; replaying their keys must use identical data.
    return {"seed-product-amul-taaza-v1": "Amul Taaza", "seed-product-dahi-v1": "Dahi", "seed-product-maggi-v1": "Maggi"}[item.key]


def _legacy_aliases(item: Item) -> tuple[str, ...]:
    return {"seed-product-amul-taaza-v1": ("Amul Taaza 500 ml", "Taaza"), "seed-product-dahi-v1": ("Curd",),
            "seed-product-maggi-v1": ("Maggi noodles", "noodles")}[item.key]


def _simulate(connection, shop_id, persona, item: Item, product_id, supplier_id, today: datetime, rng: random.Random) -> None:
    """Day-by-day: opening count, deliveries when stock hits the reorder level, daily sales, perishables wastage."""
    start = today - timedelta(days=HISTORY_DAYS)
    stock = item.reorder_qty + item.reorder_level
    base_unit = item.unit
    count_key = f"seed-{persona}-{item.sku}-opening-count-v1"
    connection.execute(
        """INSERT OR IGNORE INTO inventory_movements (movement_id, shop_id, product_id, quantity_delta, counted_quantity, unit, reason,
           source_event_id, idempotency_key, status, created_at) VALUES (?, ?, ?, ?, ?, ?, 'PHYSICAL_COUNT', ?, ?, 'POSTED', ?)""",
        (_id("movement", count_key), shop_id, product_id, stock, stock, base_unit, count_key, count_key, _stamp(start, 8)),
    )
    pending_delivery = None
    for offset in range(HISTORY_DAYS):
        day = start + timedelta(days=offset + 1)
        last_days = HISTORY_DAYS - offset
        if pending_delivery is not None and offset >= pending_delivery:
            if not (item.end_state == "out" and last_days <= 4):
                stock += _deliver(connection, shop_id, persona, item, product_id, supplier_id, day, offset, rng, stock)
            pending_delivery = None
        weekend = 1.15 if day.weekday() >= 5 else 1.0
        rate = item.daily * weekend
        if item.end_state == "slow":
            rate = 0 if last_days <= 15 else rate * 0.5
        demand = max(0, round(rng.gauss(rate, max(rate * 0.35, 0.5)))) if rate > 0 else 0
        if item.end_state == "out" and last_days <= 4:
            demand = max(demand, stock)  # sold through, delivery not yet arrived
        sold = min(demand, stock)
        if sold:
            key = f"seed-{persona}-{item.sku}-sale-{offset}-v1"
            _outflow(connection, shop_id, product_id, base_unit, "SALE", sold, item.retail or None, key, day, 19)
            stock -= sold
        if item.wastage and stock > 0 and rng.random() < item.wastage * 6:
            wasted = min(stock, max(1, round(item.daily * item.wastage * 4)))
            key = f"seed-{persona}-{item.sku}-waste-{offset}-v1"
            _outflow(connection, shop_id, product_id, base_unit, "WASTAGE", wasted, None, key, day, 21)
            stock -= wasted
        trigger = item.reorder_level + round(item.daily * (item.lead + 1))
        threshold = trigger if item.end_state != "low" or last_days > 6 else -1
        if stock <= threshold and pending_delivery is None:
            pending_delivery = offset + item.lead
    if item.end_state == "low" and stock > item.reorder_level:
        # Planted "running low" item: today's sales bring it just under the reorder level.
        extra = stock - max(item.reorder_level - 1, 1)
        _outflow(connection, shop_id, product_id, base_unit, "SALE", extra, item.retail or None,
                 f"seed-{persona}-{item.sku}-sale-final-v1", today, 12)
        stock -= extra
    if item.end_state in ("normal", "slow") and stock <= item.reorder_level + round(item.daily * (item.lead + 1)):
        # Normal items end the month comfortably stocked: a final delivery arrives today.
        stock += _deliver(connection, shop_id, persona, item, product_id, supplier_id, today, HISTORY_DAYS, rng, stock)


def _outflow(connection, shop_id, product_id, unit, reason, quantity, price, key, day, hour) -> None:
    moment = _stamp(day, hour)
    connection.execute(
        """INSERT OR IGNORE INTO stock_outflow_movements (movement_id, shop_id, batch_id, product_id, quantity_delta, unit,
           entered_quantity, entered_unit, reason, unit_price_paise, amount_paise, source_channel, source_utterance,
           source_event_id, idempotency_key, status, occurred_at, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'system', 'synthetic history', ?, ?, 'POSTED', ?, ?)""",
        (_id("omove", key), shop_id, _id("outbatch", key), product_id, -quantity, unit, quantity, unit, reason, price,
         price * quantity if price is not None else None, key, key, moment, moment),
    )


def _deliver(connection, shop_id, persona, item: Item, product_id, supplier_id, day, offset, rng, on_hand_before: int) -> int:
    """A supplier delivery as a confirmed receipt with its payable; some paid in full, some partly."""
    key = f"seed-{persona}-{item.sku}-delivery-{offset}-v1"
    quantity = item.reorder_qty
    total = quantity * item.cost
    paid_now = total if rng.random() < 0.45 else (total // 2 if rng.random() < 0.5 else 0)
    moment = _stamp(day, 10)
    proposal_id, receipt_id = _id("proposal", key), _id("receipt", key)
    draft = {"supplier": {"supplier_id": supplier_id}, "invoice": {"total_paise": total},
             "lines": [{"line_id": "line_seed", "product_id": product_id, "quantity": quantity}]}
    connection.execute(
        """INSERT OR IGNORE INTO intake_proposals (proposal_id, shop_id, source_kind, status, version, content_hash, draft_json,
           extraction_json, image_sha256, source_utterance, idempotency_key, posted_receipt_id, created_at, updated_at, expires_at)
           VALUES (?, ?, 'manual_invoice', 'CONFIRMED', 1, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, ?)""",
        (proposal_id, shop_id, hashlib.sha256(key.encode()).hexdigest(), json.dumps(draft),
         json.dumps({"provider": "synthetic_seed", "status": "NOT_REQUESTED", "notes": []}), key, receipt_id, moment, moment, moment),
    )
    payable_id = None
    due = total - paid_now
    due_before = int(connection.execute(
        """SELECT COALESCE(SUM(CASE WHEN entry_type IN ('INVOICE_CREDIT','ADJUSTMENT_INCREASE') THEN amount_paise ELSE -amount_paise END), 0)
           FROM supplier_payable_entries WHERE shop_id = ? AND supplier_id = ?""", (shop_id, supplier_id)).fetchone()[0])
    if due > 0:
        payable_id = _id("spay", key)
        connection.execute(
            """INSERT OR IGNORE INTO supplier_payable_entries (entry_id, shop_id, supplier_id, entry_type, amount_paise, source_kind,
               source_document_id, note, source_event_id, idempotency_key, status, created_at)
               VALUES (?, ?, ?, 'INVOICE_CREDIT', ?, 'invoice_receipt', ?, 'Synthetic delivery', ?, ?, 'POSTED', ?)""",
            (payable_id, shop_id, supplier_id, due, receipt_id, f"{key}:payable", f"{key}:payable", moment),
        )
    connection.execute(
        """INSERT OR IGNORE INTO stock_receipts (receipt_id, shop_id, proposal_id, proposal_version, content_hash, source_kind,
           supplier_id, supplier_label, invoice_number, invoice_number_normalized, invoice_date, total_paise, paid_now_paise,
           payable_entry_id, supplier_due_before_paise, line_count, source_channel, source_event_id, idempotency_key, created_at)
           VALUES (?, ?, ?, 1, ?, 'manual_invoice', ?, NULL, ?, ?, ?, ?, ?, ?, ?, 1, 'system', ?, ?, ?)""",
        (receipt_id, shop_id, proposal_id, hashlib.sha256(key.encode()).hexdigest(), supplier_id, f"SYN-{offset:02d}-{item.sku.upper()}",
         f"syn{offset:02d}{item.sku}", day.date().isoformat(), total, paid_now, payable_id, due_before, f"receipt:{key}", key, moment),
    )
    connection.execute(
        """INSERT OR IGNORE INTO stock_receipt_movements (movement_id, shop_id, receipt_id, line_id, product_id, quantity_delta, unit,
           received_quantity, received_unit, base_units_per_unit, unit_cost_paise, line_total_paise, source_text, on_hand_before,
           reason, status, created_at) VALUES (?, ?, ?, 'line_seed', ?, ?, ?, ?, ?, 1, ?, ?, 'synthetic delivery', ?, 'STOCK_RECEIPT', 'POSTED', ?)""",
        (_id("rmove", key), shop_id, receipt_id, product_id, quantity, item.unit, quantity, item.unit, item.cost, total,
         on_hand_before, moment),
    )
    return quantity


def seed_all_catalogs() -> dict:
    return {persona: seed_catalog(persona) for persona in CATALOGS}
