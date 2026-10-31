"""Create the repeatable synthetic Raju fixture for local demos."""

import sys

from app.domain.models import CustomerCreate, LedgerWrite, ProductCreate, StockCountCreate, SupplierCreate
from app.services.database import DEMO_SHOP_ID, initialize_database
from app.services.inventory import create_product, record_stock_count
from app.services.ledger import create_customer, get_balance, post_credit
from app.services.suppliers import create_supplier
from app.services.catalog_seed import seed_all_catalogs


def main() -> None:
    # Windows consoles may default to cp1252, which cannot print the rupee sign.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    initialize_database()
    # Full synthetic catalogs with 30 days of stock history for every persona shop.
    catalog_counts = seed_all_catalogs()
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
    # Synthetic suppliers and inward products. No payable is seeded; supplier dues
    # only arise from merchant-confirmed invoices, payments, or adjustments.
    suppliers = [
        create_supplier(SupplierCreate(
            display_name="Sharma Distributors", aliases=["Sharma Distributors"],
            confirmed=True, idempotency_key="seed-supplier-sharma-distributors-v1",
        )),
        create_supplier(SupplierCreate(
            display_name="Gupta Dairy", aliases=["Gupta Dairy"],
            confirmed=True, idempotency_key="seed-supplier-gupta-dairy-v1",
        )),
    ]
    inward_products = [
        create_product(ProductCreate(
            name="Amul Taaza", aliases=["Amul Taaza 500 ml", "Taaza"], unit="packet",
            confirmed=True, idempotency_key="seed-product-amul-taaza-v1",
        )),
        create_product(ProductCreate(
            name="Dahi", aliases=["Curd"], unit="cup",
            confirmed=True, idempotency_key="seed-product-dahi-v1",
        )),
    ]
    balance = get_balance(customer.customer_id)
    print(f"Data mode: synthetic ({DEMO_SHOP_ID})")
    print(f"Customer: {customer.display_name} [{customer.customer_id}]")
    print(f"Opening balance due: ₹{balance.balance_due_paise / 100:.2f}")
    print(f"Product: {maggi.name} [{maggi.product_id}] · opening stock: 12 {maggi.unit}s")
    for supplier in suppliers:
        print(f"Supplier: {supplier.display_name} [{supplier.supplier_id}] · payable starts at ₹0.00")
    for product in inward_products:
        print(f"Inward product: {product.name} [{product.product_id}] · unit: {product.unit}")
    for persona, counts in catalog_counts.items():
        print(f"{persona}: {counts['products']} products, {counts['stock_outflow_movements']} sales/wastage rows, "
              f"{counts['stock_receipts']} deliveries, {counts['customers']} customers (synthetic)")


if __name__ == "__main__":
    main()
