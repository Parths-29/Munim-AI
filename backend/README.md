# Munim-AI backend scaffold

The current backend slice provides deterministic synthetic merchant facts, synthetic-shop customer/alias records, an append-only credit/repayment ledger, verified stock counts, stockout observations, mock payment intake/review, and an append-only activity timeline. It does not implement voice/LLM commands or live Paytm integrations.

## Requirements

- Python 3.11 or a compatible Python version supported by the team environment.

## Run on Windows PowerShell

From the repository root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/health` or `http://127.0.0.1:8000/docs`.

## Run on macOS/Linux

From the repository root:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The health response confirms only that the local API process is responding. It does not indicate a Paytm connection or a ready database.

## Current endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Local API liveness and synthetic-only mode. |
| `GET` | `/insights/facts?persona=kirana` | Deterministic evidence-linked facts for kirana, tea-stall, or medical-store demo data. |
| `POST` | `/customers` | Add a synthetic customer and aliases after explicit confirmation. |
| `GET` | `/customers/resolve?query=Raju%20bhai` | Exact alias lookup; returns `RESOLVED`, `AMBIGUOUS`, or `NOT_FOUND`. |
| `GET` | `/ledger/customers/{customer_id}/balance` | Derive balance from posted ledger entries. |
| `POST` | `/ledger/credits` | Append a confirmed credit entry. |
| `POST` | `/ledger/repayments` | Append a confirmed repayment, rejecting amounts above the current due balance. |
| `POST` | `/products` | Add a confirmed synthetic product with aliases and a unit. |
| `GET` | `/products/resolve?query=Maggi` | Exact product alias lookup; does not guess. |
| `GET` | `/inventory/products/{product_id}/stock` | Derive on-hand quantity from posted stock movements. |
| `POST` | `/inventory/stockout-observations` | Record a merchant stockout report without changing on-hand quantity. |
| `POST` | `/inventory/counts` | Record a confirmed physical count as an append-only movement. |
| `GET` | `/events?limit=50` | Read recent business events, source, status, and summary. |
| `POST` | `/payments/payer-mappings` | Link a synthetic payer token to a demo customer after confirmation. |
| `POST` | `/payments/intake` | Accept a provider-mock event; auto-allocate only on exact mapping and safe outstanding balance. |
| `GET` | `/payments/review` | List unmatched or review-required successful mock payments. |
| `POST` | `/payments/{event_id}/allocate` | Manually allocate a reviewed event after merchant confirmation and balance validation. |

Customer, ledger, and inventory writes use a stable `idempotency_key`, a unique `source_event_id`, and explicit `confirmed` state. Use the accepted command ID as the idempotency key. Replaying either key or source event has one effect; reusing one for different operation details returns `409 Conflict`. Payment endpoints have their own documented event and confirmation rules below.

Example credit request:

```json
{
  "customer_id": "cust_example",
  "amount_paise": 5000,
  "source_event_id": "event_demo_credit_01",
  "idempotency_key": "cmd_demo_credit_01",
  "confirmed": true
}
```

The SQLite database is created at `backend/data/munim.sqlite3` by default. On API startup, an empty database receives a repeatable 90-day synthetic payment fixture for three shop personas. Override the database location with `MUNIM_DB_PATH`. It is ignored by Git and should contain synthetic demo data only.

## Seed the demo customer

From the repository root, after installing backend requirements:

```powershell
cd backend
python seed_demo.py
```

The seed command is designed to be replay-safe. It creates the synthetic Raju customer and a ₹500 opening credit, plus a Maggi product with 12 packs counted on hand. It prints the generated IDs and balances for the mobile demo.

Mock payment events never claim a live provider connection. Non-success events are ignored for ledger allocation; missing payer mapping and over-balance amounts go to review. Manual allocation requires explicit confirmation, and the full payment amount must fit the outstanding balance; this prototype does not create automatic partial allocations.
