# Backend API contract v0.4

This describes the synthetic single-shop backend slice on the current task branch. It supplements the AI proposal schemas; it is not a Paytm API contract.

Base URL for local development: `http://127.0.0.1:8000`. Money is integer paise. The demo shop is fixed to `shop_synth_01`; there is no authentication or multi-shop isolation in this prototype.

## `GET /health`

Returns local liveness only:

```json
{"status":"ok","phase":"business-facts","data_mode":"synthetic-only"}
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

## `POST /products`

```json
{
  "name": "Maggi",
  "aliases": ["Maggi noodles", "noodles"],
  "unit": "pack",
  "confirmed": true,
  "idempotency_key": "cmd_create_maggi_01",
  "source_utterance": "Maggi ka product add karo",
  "source_channel": "text"
}
```

Aliases are shop-scoped exact matches. If the same alias maps to multiple products, resolution returns `AMBIGUOUS` and does not choose one.

## `GET /products/resolve?query=Maggi`

Exact normalized alias resolution only. Returns `RESOLVED`, `AMBIGUOUS`, or `NOT_FOUND`; it never picks between multiple products.

## `GET /inventory/products/{product_id}/stock`

Returns the current derived on-hand quantity, unit, and movement count. This is only as accurate as the physical counts recorded in the synthetic demo; no purchase or sale movements are inferred from UPI payments.

## `POST /inventory/stockout-observations`

The request identifies a known `product_id` and contains `source_event_id`, `idempotency_key`, `confirmed`, optional `source_utterance`, and `source_channel`. It records status `OBSERVED`. **It does not mutate inventory quantity.** Repeated event/key replays return the same observation; a key reused for different product/utterance details returns `409`.

## `POST /inventory/counts`

Request fields: `product_id`, non-negative integer `counted_quantity`, `source_event_id`, `idempotency_key`, `confirmed`, and optional source details. Backend derives the previous quantity by summing movements, then appends a `PHYSICAL_COUNT` movement with `quantity_delta = counted_quantity - previous_quantity`. A zero-delta count remains auditable. Never treat a stockout observation as a physical count.

## `GET /events?limit=50`

Returns recent event IDs, event types, related entity, source event/channel/utterance, status, summary, and timestamp. The endpoint is read-only; it does not expose payment-provider credentials or raw customer contact data.

## `GET /insights/facts?persona=kirana`

Returns facts in the shape defined by `docs/contracts/facts.schema.json`. Supported personas are `kirana`, `tea_stall`, and `medical_store`. The API seeds a deterministic 90-day synthetic transaction fixture when its local database is empty. The current window is the latest 7 full fixture days and the comparison is the preceding 7 full days. Values are computed in Python from rows; no LLM computes metrics. Raw payer tokens are never included in the response. Collections are UPI-only, lapsed-payer counts are synthetic-token counts, and before/after differences are not causal claims.

## Explicitly not implemented in v0.4

Mocked payment intake and allocation, voice/LLM parsing, business insight facts, action publication, authentication, and production payment integration. Do not build mobile screens that imply these backend behaviors already exist.
