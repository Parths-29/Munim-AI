# Backend API contract v0.8

This describes the synthetic single-shop backend slice on the current task branch. It supplements the AI proposal schemas; it is not a Paytm API contract.

Base URL for local development: `http://127.0.0.1:8000`. Money is integer paise. The demo shop is fixed to `shop_synth_01`; there is no authentication or multi-shop isolation in this prototype.

Expo Web development origins default to `http://localhost:8081` and `http://127.0.0.1:8081`. Set backend-only `MUNIM_CORS_ORIGINS` to a comma-separated allowlist if the web dev server uses a different origin; do not use a wildcard in a deployed environment.

## `POST /commands/interpret`

Optional read-only NLP assist for a typed command or an already-created speech transcript. The client calls it only when its deterministic parser cannot classify the request. It returns a structured draft (`intent`, exact `entity_text`, exact `amount_text`, and confidence) or asks for clarification. It never resolves IDs or writes to the ledger/inventory. The client re-parses the returned spans locally, then uses the same exact-entity lookup, preview, and explicit confirmation flow as other commands. If Gemini is missing or unavailable, the route returns a controlled fallback after an 8-second request timeout. `GEMINI_MODEL` can override the default `gemini-3.8-flash` model ID.

Request: `{ "utterance": "what does Raju owe?", "source_channel": "text" }`. A successful interpretation returns `status: "ready"`, `intent: "balance"`, `entity_text: "Raju"`, `amount_text: null`, and a confidence score. For credit/repayment, `amount_text` must quote an explicit rupee amount from the utterance. A fallback returns `status: "unavailable"` and `provider_used: "fallback"`.

The prompt uses a small set of synthetic Hinglish/English command examples stored in `backend/app/services/command_nlp.py`. These are few-shot examples only; they do not train or fine-tune Gemini. No ledger rows, transaction history, customer IDs, or product IDs are sent to Gemini. When enabled, the submitted utterance itself is sent to Google's Gemini API, so users should avoid including unrelated sensitive details.

## `POST /speech/transcribe`

Accepts a multipart form field named `file` with a supported audio MIME type and returns `{ "transcript", "language_code", "request_id", "provider" }`. Browser WebM uploads are normalized from codec-qualified, generic-binary, or `video/webm` metadata to `audio/webm`; a known file extension is used as a fallback for generic binary uploads. Audio is forwarded server-to-server to Sarvam's short-form `/speech-to-text` REST endpoint using model `saaras:v4` and `mode=translit`, which keeps Hindi/Hinglish commands compatible with the current Latin-script parser. The backend requires `SARVAM_API_KEY` as an environment variable or in a gitignored backend/root `.env`; the key is never sent to the mobile app. Uploads are capped at 12 MB, the app caps recordings at 20 seconds, and audio is not written to the database or disk by the endpoint. The transcript only fills the input box; sending it runs the existing parser, and any write still needs merchant confirmation. If Sarvam is unconfigured or unavailable, typed input remains available.

## `GET /health`

Returns local liveness only:

```json
{"status":"ok","phase":"payment-review","data_mode":"synthetic-only"}
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

## Facts-only explanation (current hardening branch)

`POST /insights/explain` accepts `{"persona":"kirana"}` (supported personas: `kirana`, `tea_stall`, `medical_store`) and returns an explanation, evidence IDs, a permitted action type, and backend-owned action copy. The backend may call Gemini server-side; missing credentials, upstream errors, or invalid model output use a deterministic fallback. The model does not write to the database or publish an action. This route is part of `main` after PR #9; see [`../BUILD_LOG.md`](../BUILD_LOG.md) for current verification status.

## Merchant-approved mock action and outcome window

`POST /actions/mock` records a merchant-confirmed mock action. Request fields are `persona`, `action_type` (`counter_notice` or `qr_offer_mock`), `action_text`, `confirmed: true`, and an `idempotency_key`. The backend snapshots the latest available 7-day synthetic UPI collections baseline and schedules a 7-day observation window beginning at approval time. The action is append-only and visibly marked `APPROVED_MOCK`; no offer is published or sent. A repeated request with the same key and same action returns the original record; using that key for different action details returns `409`.

`GET /actions/latest?persona=kirana` restores the most recent saved action for the persona. Its `outcome_status` is `scheduled` until the observation window ends, `available` only when the window has transaction rows, or `insufficient_data` when the window ended without rows. An available comparison reports raw UPI collections/count and the difference from the saved baseline, but never claims causation. Current demo fixtures end on 2026-10-29, so newly approved actions remain scheduled and later resolve to insufficient data unless post-approval transaction rows are supplied. There is no live payment feed in this prototype.

## Mocked payment intake and review

`POST /payments/payer-mappings` accepts `payer_token`, `customer_id`, `confirmed`, and `idempotency_key`. It creates one merchant-scoped synthetic-token mapping only after confirmation; conflicting mappings return `409`.

`POST /payments/intake` accepts `event_id`, `amount_paise`, `status`, timezone-aware `occurred_at`, `idempotency_key`, optional `payer_token`, and `source: "provider_mock"`. Shop scope is fixed to the synthetic demo shop; the API does not connect to Paytm. Duplicate event IDs are idempotent only when the payload matches.

An event is automatically allocated as a repayment only when its status is `SUCCESS`, its payer token has an exact confirmed mapping, and its full amount is no greater than that customer's outstanding balance. Failed, pending, or reversed events do not change the ledger. Missing mapping, no balance, or amount above balance is not auto-allocated. `GET /payments/review` lists unresolved successful events. `POST /payments/{event_id}/allocate` allows a merchant-confirmed manual allocation to a selected demo customer after checking that the full amount fits the outstanding balance. Neither path performs partial allocation. Payment events and manual resolutions are append-only; ledger balances remain derived from ledger entries.

## Explicitly not implemented in v0.5

Voice/LLM command parsing, live action publication, authentication, and production payment integration. The facts-only explanation endpoint above is read-only and does not imply these behaviors exist.
