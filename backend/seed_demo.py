"""Create the repeatable synthetic Raju fixture for local demos."""

from app.domain.models import CustomerCreate, LedgerWrite
from app.services.database import DEMO_SHOP_ID, initialize_database
from app.services.ledger import create_customer, get_balance, post_credit


def main() -> None:
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
    balance = get_balance(customer.customer_id)
    print(f"Data mode: synthetic ({DEMO_SHOP_ID})")
    print(f"Customer: {customer.display_name} [{customer.customer_id}]")
    print(f"Opening balance due: ₹{balance.balance_due_paise / 100:.2f}")


if __name__ == "__main__":
    main()
