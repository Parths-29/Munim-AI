# Backend API contract v0.9

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

## `GET /events/summary`

Returns deterministic aggregate counts and totals for ledger credits/repayments, mock payment statuses, successful events awaiting review, inventory observations/counts, the latest five payment events, and latest five timeline events. `period_label` explicitly identifies the covered synthetic demo history. Mock successful payments are reported separately from repayments actually posted to the ledger; no causal or live-feed claims are made.

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

## `POST /commands/interpret`

Gemini-assisted, read-only interpretation of one merchant utterance into a bounded supported intent and exact quoted name/amount/count spans. Supported intents include credit, repayment, balance, customer creation, stockout observation, stock lookup, physical count, payment summary, and timeline summary. Missing credentials, upstream errors, low confidence, or invalid spans return a clarification/unavailable result. This endpoint never writes; the client reparses locally, resolves an exact entity, previews every mutation, and requires explicit merchant confirmation.

## Suppliers and supplier payables (v0.9, Phase 1)

Supplier payables are money **the shop owes**. They are stored in `suppliers`, `supplier_aliases`, and append-only `supplier_payable_entries`, never in the customer ledger, and use their own routes and response fields (`amount_due_paise`, not `balance_due_paise`).

- `POST /suppliers` — `display_name`, optional exact `aliases`, optional merchant-supplied `contact_phone`/`contact_note`, `confirmed: true`, `idempotency_key`. Replay with identical data returns the same supplier; different data with the same key returns `409`. Responses only expose `contact_phone_masked`.
- `GET /suppliers` and `GET /suppliers/resolve?query=` — exact normalized alias lookup returning `RESOLVED`, `AMBIGUOUS`, or `NOT_FOUND`. Generic phrases such as “doodh wale” are not mapped to a supplier unless the merchant explicitly created that alias.
- `GET /suppliers/{id}/balance` — `amount_due_paise` (never negative), `entry_count`, `totals_by_type_paise`, and the documented `sign_convention`: `INVOICE_CREDIT + ADJUSTMENT_INCREASE − PAYMENT − DEBIT_NOTE − ADJUSTMENT_DECREASE`.
- `GET /suppliers/{id}/entries?limit=100` — entry history with `direction` (`INCREASES_DUE`/`DECREASES_DUE`), source kind, source document, and note.
- `POST /suppliers/{id}/payments` — records a payment the merchant says was already made (`amount_paise`, `source_event_id`, `idempotency_key`, `confirmed`, optional `note`). **No money is transferred.** Amount above current due returns `409` `SUPPLIER_DECREASE_EXCEEDS_DUE`.
- `POST /suppliers/{id}/adjustments` — `entry_type` `DEBIT_NOTE`, `ADJUSTMENT_INCREASE` (e.g. an opening balance), or `ADJUSTMENT_DECREASE`, with a required `note`.
- `INVOICE_CREDIT` entries are only created by the confirmed invoice/receipt posting flow (Phase 3).

Idempotency follows the ledger rules: replay of the same key/source event returns the original entry with `idempotent_replay: true`; reuse for different details returns `409`.

## Stock-inflow proposals: invoice photos and manual bills (v0.9, Phases 2–3)

A **proposal** is a versioned draft. Creating, reading, or revising one never changes stock or supplier dues. Validation is recomputed on every read, so a draft reflects current products, suppliers, conversions, and posted invoices.

### Create

- `POST /invoices/proposals` — multipart: `file` (JPEG/PNG/WebP), `idempotency_key`, optional `supplier_id`. The backend sniffs the real format from the bytes (the declared type must agree), reads dimensions, and enforces limits: default 8 MB (`MUNIM_INVOICE_MAX_BYTES`), sides 100–10,000 px, ≤ 50 MP. Errors: `400` empty, `413` too large, `415` unsupported or mismatched type, `422` malformed or too small. The image is processed in memory and discarded; only a SHA-256 digest is kept for duplicate-photo hints (`image_retained: false`). Replaying the key with the same image returns the same proposal; with a different image, `409`.
- `POST /invoices/proposals/manual` — the same content as JSON (`supplier`, `invoice`, `lines`, `idempotency_key`) for typed bills or when extraction is unavailable.

Extraction provider (`MUNIM_INVOICE_PROVIDER`): `gemini` (default; backend-only key, model `GEMINI_VISION_MODEL` → `GEMINI_MODEL` → `gemini-3.8-flash`, timeout `MUNIM_VISION_TIMEOUT_SECONDS`, default 20 s), `fake` (a deterministic synthetic bill for demos), or `none`. The model is asked to copy printed values as text. Deterministic code converts amounts to paise and quantities to whole numbers. Anything unreadable becomes `null` plus a note; a fractional quantity is never rounded and no value is invented. If the provider is down or times out, the response is still `201`: an empty draft with `extraction.status = "PROVIDER_UNAVAILABLE"`, ready for manual entry.

### Proposal view

`proposal_id`, `source_kind`, `status` (`NEEDS_REVIEW`, `READY`, `CONFIRMED`, `REJECTED`, `EXPIRED`; default expiry 7 days), `version`, `content_hash`, `supplier` (match status `RESOLVED`/`SELECTED`/`AMBIGUOUS`/`NOT_FOUND`/`NOT_PROVIDED` with candidates), `invoice` (number, date, subtotal/tax/discount/freight/other/rounding/total in paise, per-field confidence), `lines[]`, `issues[]`, `totals`, `ready_to_confirm`, `warnings_require_acknowledgement`, `extraction` (provider, model, status, correlation ID).

Each line has `source_text`, `product_name_text`, `matched_product_id`, `match_status` (`MATCHED` exact alias, `SELECTED` by the merchant, `NEEDS_SELECTION` with candidates, `NOT_FOUND`), `quantity`, `unit_text`, canonical `unit`, `unit_options`, `conversion_factor`, `base_quantity`, `base_unit`, `unit_cost_paise`, `line_total_paise`, `confidence`, `accepted`, and its own `issues`.

Issue severities:

- **blocking** — stops confirmation. Examples: `PRODUCT_UNRESOLVED`, `PRODUCT_AMBIGUOUS`, `QUANTITY_MISSING`, `UNIT_MISSING`, `UNIT_CONVERSION_UNKNOWN`, `LOW_CONFIDENCE` (below `MUNIM_INTAKE_MIN_CONFIDENCE`, default 0.80, until the merchant verifies), `LOW_CONFIDENCE_HEADER`, `SUPPLIER_AMBIGUOUS`, `DUPLICATE_INVOICE_ALREADY_POSTED`, `DUPLICATE_INVOICE_CONFLICT`, `NO_ACCEPTED_LINES`.
- **warning** — needs `acknowledge_warnings: true` at confirm. Examples: `LINE_TOTAL_MISMATCH` (quantity × unit cost ≠ line total), `INVOICE_TOTAL_MISMATCH` (subtotal + tax + freight + other − discount + rounding ≠ total), `LINES_SUBTOTAL_MISMATCH`, `POSSIBLE_DUPLICATE_*`, extraction notes.
- **info** — advisory. Examples: `COMPONENTS_UNKNOWN` (components not shown are never derived), `TOTAL_UNKNOWN`.

The arithmetic tolerance is `MUNIM_INVOICE_ROUNDING_TOLERANCE_PAISE` (default 100). Mismatched source values are kept as printed, never silently corrected.

Units: synonyms of the same unit are normalized (`pkt`/`packets` → `packet`). A different unit (`case`, `crate`, `dozen`) needs either a merchant-entered `conversion_factor` on the line or a saved conversion. `POST /products/{id}/unit-conversions` takes `{unit, base_units_per_unit, confirmed, idempotency_key}`; conversions are append-only and the latest one wins. Pack sizes are never assumed.

### Revise / reject

- `POST /invoices/proposals/{id}/revise` — `expected_version`, `supplier {supplier_id | label}`, `invoice {…, verified}`, and the full `lines[]` (keep `line_id` to edit a line, omit it to add one, set `accepted: false` to exclude one, and set `merchant_verified`). This increments `version`, recomputes `content_hash`, and appends to `intake_proposal_revisions`. A stale version returns `409 STALE_PROPOSAL`.
- `POST /invoices/proposals/{id}/reject` — `{expected_version, confirmed: true}`.

### Confirm (atomic posting)

`POST /invoices/proposals/{id}/confirm` with `{expected_version, content_hash, paid_now_paise, acknowledge_warnings, confirmed: true, idempotency_key}`.

1. The version and hash must match the current draft, otherwise `409 STALE_PROPOSAL`. An amount edited after the preview cannot be posted without a fresh preview.
2. The server revalidates everything. Blocking issues return `409 PROPOSAL_NOT_READY` with the issue list; unacknowledged warnings return `409 WARNINGS_NOT_ACKNOWLEDGED`.
3. When a total exists, `paid_now_paise` is required (0 if unpaid) and must satisfy `0 ≤ paid_now ≤ total`. It is never inferred from a "PAID" stamp. A positive unpaid amount requires a supplier, otherwise `409 SUPPLIER_REQUIRED_FOR_PAYABLE`.
4. **One transaction** appends:
   - a `stock_receipts` row;
   - one `stock_receipt_movements` row per accepted line (base-unit quantity, wholesale cost, on-hand-before snapshot);
   - an `INVOICE_CREDIT` supplier payable for `total − paid_now` when that is positive;
   - timeline events.

   It then marks the proposal `CONFIRMED`. Any failure rolls every part back.
5. The response is a `ReceiptView`: `receipt_id`, `payable_status` (`POSTED`, `FULLY_PAID_NOW`, `NOT_SUPPLIED`), supplier due before and after, per-line on-hand before and after, and `retail_price_changed: false`. Product rows are never updated.

Replaying the same key returns the same receipt with `idempotent_replay: true`. A different key on an already-confirmed proposal returns `409 PROPOSAL_ALREADY_CONFIRMED`. A unique index allows one posting per `(supplier, normalized invoice number)`. `GET /receipts/{id}` re-reads a receipt.

On-hand stock is now `SUM(physical-count deltas) + SUM(receipt movements)`, and a later physical count computes its delta against that combined figure.

## Explicitly not implemented in v0.5

Live action publication, authentication, and production payment integration. Voice transcription is an input convenience and is not guaranteed to recognize names or spoken amounts correctly; the transcript must be reviewed. The facts-only explanation and command interpretation endpoints do not imply live Paytm connectivity or autonomous writes.
