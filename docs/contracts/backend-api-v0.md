# Backend API contract v0.2

This is the implemented synthetic single-shop backend slice on branch `codex/phase-2-ledger-api`. It supplements the AI proposal schemas; it is not a Paytm API contract.

Base URL for local development: `http://127.0.0.1:8000`. Money is integer paise. The demo shop is fixed to `shop_synth_01`; there is no authentication or multi-shop isolation in this prototype.

## `GET /health`

Returns local liveness only:

```json
{"status":"ok","phase":"phase-2-ledger","data_mode":"synthetic-only"}
```

## `POST /customers`

Create a shop-scoped customer after the UI has confirmed the action. The `idempotency_key` should be the command ID.

```json
{
  "display_name": "Raju bhai",
  "aliases": ["Raju", "Raju bhai"],
  "confirmed": true,
  "idempotency_key": "cmd_create_raju_01"
}
```

Returns `customer_id`, `display_name`, and aliases. Replaying the same key and same customer data returns the same customer. Reusing the key with different data returns `409`.

## `GET /customers/resolve?query=Raju%20bhai`

Exact normalized alias resolution only. Response status is `RESOLVED` (one match), `AMBIGUOUS` (multiple matches), or `NOT_FOUND`. No fuzzy guess is made.

## `GET /ledger/customers/{customer_id}/balance`

Returns `balance_due_paise`, currency `INR`, and posted-entry count. Balance is computed as the sum of credits minus repayments; it is not stored as an independently editable number.

## `POST /ledger/credits` and `POST /ledger/repayments`

The request body is:

```json
{
  "customer_id": "cust_example",
  "amount_paise": 5000,
  "source_event_id": "event_demo_credit_01",
  "idempotency_key": "cmd_demo_credit_01",
  "confirmed": true
}
```

The route determines whether this is `CREDIT` or `REPAYMENT`. `confirmed` must be true. A repayment greater than the currently derived balance returns `409` with code `REPAYMENT_EXCEEDS_BALANCE`; no ledger entry is posted. Replaying the same idempotency key or source event with the same operation returns the existing entry with `idempotent_replay: true`. Reusing either key with different operation details returns `409`.

## Explicitly not implemented in v0.2

Stock/product APIs, the activity timeline, mocked payment intake and allocation, voice/LLM parsing, business insight facts, action publication, authentication, and production payment integration. Do not build mobile screens that imply these backend behaviors already exist.
