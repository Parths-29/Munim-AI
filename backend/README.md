# Munim-AI backend scaffold

The backend provides deterministic synthetic merchant facts, an append-only ledger and inventory record, mock payment review, merchant-approved mock actions, and short Sarvam speech transcription. Voice transcription returns text only; it does not execute commands. There is no live Paytm integration.

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

Voice transcription is optional and requires `SARVAM_API_KEY` in a backend-only environment variable or the ignored root/backend `.env` file. Never place this key in `mobile/.env` or an `EXPO_PUBLIC_*` variable. The app records at most 20 seconds, and the backend forwards the audio to Sarvam without saving it.

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

For Expo Web, local CORS origins default to `http://localhost:8081` and `http://127.0.0.1:8081`. Override them with the comma-separated backend variable `MUNIM_CORS_ORIGINS` when the web dev server uses another origin. Native phone builds do not use CORS.

## Current endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Local API liveness and synthetic-only mode. |
| `GET` | `/insights/facts?persona=kirana` | Deterministic evidence-linked facts for kirana, tea-stall, or medical-store demo data. |
| `POST` | `/speech/transcribe` | Transcribe a short audio upload using server-side Sarvam credentials; returns text only. |
| `POST` | `/actions/mock` | Save a confirmed mock action and schedule its outcome window. |
| `GET` | `/actions/latest?persona=kirana` | Restore the latest mock action and its observation-window status. |
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
| `POST` | `/suppliers` | Add a supplier with exact aliases after confirmation (contact details optional, masked in responses). |
| `GET` | `/suppliers`, `/suppliers/resolve?query=` | List suppliers; exact alias lookup (`RESOLVED`/`AMBIGUOUS`/`NOT_FOUND`). |
| `GET` | `/suppliers/{id}/balance`, `/suppliers/{id}/entries` | Derived amount the shop owes the supplier, with entry breakdown. |
| `POST` | `/suppliers/{id}/payments`, `/suppliers/{id}/adjustments` | Record a confirmed payment already made (no transfer) or a debit note/adjustment. |
| `POST` | `/products/{id}/unit-conversions` | Save a merchant-confirmed pack size (e.g. 1 case = 24 packet). |
| `POST` | `/invoices/proposals` | Upload a bill photo; returns a validated, editable draft. No stock/payable writes; image not retained. |
| `POST` | `/invoices/proposals/manual` | Same draft from typed JSON (also the fallback when extraction is unavailable). |
| `GET` | `/invoices/proposals`, `/invoices/proposals/{id}` | List or read drafts with recomputed issues. |
| `POST` | `/invoices/proposals/{id}/revise`, `/reject` | Merchant edits (versioned) or rejection. |
| `POST` | `/invoices/proposals/{id}/confirm` | Atomic posting: stock movements + supplier payable (total minus paid now) + events. |
| `GET` | `/receipts/{id}` | Read a posted stock receipt. |
| `POST` | `/inventory/inward/proposals` | Reviewed transcript/text → stock-receipt draft or clarification (no writes). |
| `GET`/`POST` | `/inventory/inward/proposals/{id}`, `/revise`, `/reject`, `/confirm` | Review and confirm an inward delivery; stock only unless a verified total is added. |

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

## Invoice extraction provider

`MUNIM_INVOICE_PROVIDER` selects how bill photos are read: `gemini` (default; backend-only `GEMINI_API_KEY`, optional `GEMINI_VISION_MODEL` and `MUNIM_VISION_TIMEOUT_SECONDS`), `fake` (deterministic synthetic bill for demos without credentials), or `none` (always a manual draft). If the provider fails, the API still returns an empty editable draft; it never invents fields.

## Tests

Tests use a fresh temporary SQLite file per test and fake providers; they never read the demo database or call Gemini, Sarvam, SMS, or WhatsApp.

```powershell
cd backend
python -m pip install -r requirements-dev.txt
python -m pytest -q tests
```

## Schema migrations

`initialize_database()` applies versioned, additive migrations from `app/services/migrations.py` and records them in `schema_migrations`. Migration 1 is the original schema, so an existing demo database upgrades in place without rewriting rows. Before upgrading a database you care about, copy the file; to roll back, stop the API and restore the copy.

## Seed the demo customer

From the repository root, after installing backend requirements:

```powershell
cd backend
python seed_demo.py
```

The seed command is designed to be replay-safe. It creates the synthetic Raju customer and a ₹500 opening credit, plus a Maggi product with 12 packs counted on hand, two synthetic suppliers (Sharma Distributors, Gupta Dairy) with zero payable, and inward products Amul Taaza (packet) and Dahi (cup). It prints the generated IDs and balances for the mobile demo.

Mock payment events never claim a live provider connection. Non-success events are ignored for ledger allocation; missing payer mapping and over-balance amounts go to review. Manual allocation requires explicit confirmation, and the full payment amount must fit the outstanding balance; this prototype does not create automatic partial allocations.
