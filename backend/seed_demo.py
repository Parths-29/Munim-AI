"""Create the repeatable synthetic Raju fixture for local demos."""

import sys

from app.domain.models import CustomerCreate, LedgerWrite, ProductCreate, StockCountCreate
from app.services.database import DEMO_SHOP_ID, initialize_database
from app.services.inventory import create_product, record_stock_count
from app.services.ledger import create_customer, get_balance, post_credit


def main() -> None:
    # Windows consoles may default to cp1252, which cannot print the rupee sign.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    initialize_database()
    customer = create_customer(
        CustomerCreate(
            display_name="Raju bhai",
            aliases=["Raju", "Raju bhai"],
            confirmed=True,
            idempotency_key="seed-customer-raju-v1",
        )
    )
    post_credit(
        LedgerWrite(
            customer_id=customer.customer_id,
            amount_paise=50000,
            source_event_id="seed-opening-credit-raju-v1",
            idempotency_key="seed-opening-credit-v1",
            confirmed=True,
        )
    )
    maggi = create_product(
        ProductCreate(
            name="Maggi",
            aliases=["Maggi noodles", "noodles"],
            unit="pack",
            confirmed=True,
            idempotency_key="seed-product-maggi-v1",
        )
    )
    record_stock_count(
        StockCountCreate(
            product_id=maggi.product_id,
            counted_quantity=12,
            source_event_id="seed-opening-stock-maggi-v1",
            idempotency_key="seed-opening-stock-maggi-v1",
            confirmed=True,
        )
    )
    balance = get_balance(customer.customer_id)
    print(f"Data mode: synthetic ({DEMO_SHOP_ID})")
    print(f"Customer: {customer.display_name} [{customer.customer_id}]")
    print(f"Opening balance due: ₹{balance.balance_due_paise / 100:.2f}")
    print(f"Product: {maggi.name} [{maggi.product_id}] · opening stock: 12 {maggi.unit}s")


if __name__ == "__main__":
    main()
