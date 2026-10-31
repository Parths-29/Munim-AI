# Next Phases — Repository Audit and Phase Checklist

**Date:** 2026-10-30 · **Branch:** `codex/sarvam-voice-input` · **Start commit:** `5bec501` (PRD commit on top of `11389a4`)
**Spec:** [`NEXT_PHASES_BACKEND_FIRST_PRD.md`](NEXT_PHASES_BACKEND_FIRST_PRD.md). Backend/API only; no UI changes.

## 1. Starting state (verified)

- Working tree clean on `main` at `8449bdf`; switched to tracking branch `codex/sarvam-voice-input` (`5bec501`). `origin/main` is one merge commit ahead with an identical tree apart from the PRD; nothing needed merging.
- No `AGENTS.md` files exist in the repository.
- `.env` is ignored (`.gitignore:12`, also `.env.*` with `!.env.example`). Only `.env.example` and `mobile/.env.example` are tracked; both hold placeholders. No `.db`/`.sqlite3` file is tracked. Secret values were not read.
- No local `backend/data/` database exists on this machine, so no user demo data is at risk here. All tests and rehearsals use temporary DB paths regardless.
- No automated test suite existed before this work. Global Python 3.12 has FastAPI 0.138, Pydantic 2.12, httpx, pytest.

## 2. Architecture as found

| Layer | Location | Notes |
|---|---|---|
| App/routers | `backend/app/main.py`, `backend/app/api/*.py` | Thin routers; CORS allows `GET, POST, OPTIONS` only. |
| Models | `backend/app/domain/models.py` | Pydantic v2 `StrictModel` (`extra="forbid"`), strict ints for paise. |
| Services | `backend/app/services/*.py` | Each write: `confirmed` check → `BEGIN IMMEDIATE` → idempotency lookup (key *or* source event) → insert → `append_event`. Conflicting reuse → `409`. |
| DB | `backend/app/services/database.py` | One SQLite file (`MUNIM_DB_PATH` override). `connect()` is autocommit-off-by-hand (`isolation_level=None`), commits on success, rolls back on exception. Schema is one `CREATE … IF NOT EXISTS` script; **no migration versioning**. |
| Append-only | DB triggers | `ledger_entries`, `inventory_movements`, `business_events`, payments, mock actions reject UPDATE/DELETE. |
| Resolution | `ledger.normalize_alias`, `inventory._normalize` | NFKC + casefold + whitespace collapse; exact alias match; `RESOLVED / AMBIGUOUS / NOT_FOUND`. |
| AI | `command_nlp.py`, `explainer.py` | Sarvam Chat Completions for command interpretation (`SARVAM_COMMAND_MODEL`, default `sarvam-105b-conversations`) with JSON-schema and literal-span validation; Gemini remains for facts explanation. Keys read from env or ignored `.env`. |
| Speech | `speech.py` | Sarvam, audio in memory only, 12 MB cap. |

### Constraints that shape the design

1. `inventory_movements.reason` has `CHECK (reason = 'PHYSICAL_COUNT')` and `counted_quantity NOT NULL`. SQLite cannot alter a CHECK without rebuilding the table. **Decision:** keep migrations additive — stock receipts go in a new append-only `stock_receipt_movements` table, and on-hand becomes `SUM(inventory_movements.quantity_delta) + SUM(stock_receipt_movements.quantity_delta)`. Physical counts compute their delta against the combined figure, so a later count still reconciles correctly.
2. `business_events.source_channel` is limited to `text|voice|provider_mock|system` and `status` to `POSTED|OBSERVED`; `source_event_id` and `idempotency_key` are unique. New flows reuse those values (merchant-confirmed postings use `text`/`voice`; scheduler uses `system`) and derive distinct event keys (`<key>:receipt`, `<key>:payable`). The precise origin (e.g. `invoice_image`) is stored on the domain row.
3. `products` has **no price column**, so wholesale cost cannot overwrite a retail price; tests assert product rows are unchanged by posting.
4. Mobile `ledgerClient.ts` types `/commands/interpret` intents as a closed union. To stay backward compatible, `stock_inward` is a dedicated proposal endpoint rather than a new value in that response.

## 3. Migration approach

New `backend/app/services/migrations.py`: a `schema_migrations(version, name, applied_at)` table and an ordered list of additive SQL migrations, each applied once inside a transaction. Migration 1 is the existing baseline script (idempotent `IF NOT EXISTS`), so existing databases upgrade in place and new ones build from scratch. No existing table is rebuilt or rewritten. Rollback = restore the pre-upgrade file copy (documented in backend README).

## 4. Proposed endpoints (implemented names)

| Area | Endpoint | Writes |
|---|---|---|
| Suppliers | `POST /suppliers`, `GET /suppliers`, `GET /suppliers/resolve`, `GET /suppliers/{id}/balance`, `GET /suppliers/{id}/entries`, `POST /suppliers/{id}/payments`, `POST /suppliers/{id}/adjustments` | Confirmed + idempotent only |
| Unit conversions | `POST /products/{id}/unit-conversions`, `GET /products/{id}/unit-conversions` | Confirmed, append-only |
| Invoice drafts | `POST /invoices/proposals` (multipart), `POST /invoices/proposals/manual`, `GET /invoices/proposals/{id}`, `POST /invoices/proposals/{id}/revise`, `POST /invoices/proposals/{id}/reject` | Draft table only |
| Invoice posting | `POST /invoices/proposals/{id}/confirm` | One transaction: receipt + movements + payable + events |
| Voice inward | `POST /inventory/inward/proposals`, `GET …/{id}`, `POST …/{id}/revise`, `POST …/{id}/confirm` | Draft, then same atomic posting |
| Reminders | `GET/POST /reminders/settings`, `GET/POST /customers/{id}/reminder-consent`, `GET /reminders/eligibility/preview`, `POST /reminders/eligibility/run`, `GET /reminders`, `GET /reminders/{id}`, `POST /reminders/{id}/approve`, `…/cancel`, `…/mock-send`, `…/mock-delivery-receipt` | Outbox/transition rows only; mock provider |

## 5. Risks

- **Provider instability (Gemini 503/timeouts):** extraction is behind `InvoiceExtractionProvider`; outage returns an empty manual draft flagged `PROVIDER_UNAVAILABLE`, never invented fields. Tests use a fake provider.
- **Stale edits:** proposals carry `version` + `content_hash`; confirm must quote both.
- **No auth:** run/send endpoints honour an optional `MUNIM_ADMIN_TOKEN`; real notification providers are not implemented and cannot be selected.
- **Contact data:** stored only when merchant-entered, masked in every response, never logged or put in event summaries.
- **Timezone:** day counts use the shop timezone (default `Asia/Kolkata`).

## 6. Phase checklist (acceptance → test evidence)

| Phase | Acceptance criterion | Test |
|---|---|---|
| 1 | Similar aliases resolve `AMBIGUOUS` | `test_suppliers.py::test_shared_alias_is_ambiguous` |
| 1 | Supplier entries never touch customer balances | `…::test_supplier_ledger_separate_from_customers` |
| 1 | Duplicate retry = one entry; conflicting key reuse = 409 | `…::test_payment_idempotency` |
| 1 | Balance derived from append-only entries | `…::test_balance_derived_and_append_only` |
| 2 | Valid image → proposal only (no writes) | `test_invoice_proposals.py::test_image_creates_draft_only` |
| 2 | Malformed / oversized / spoofed image rejected | `…::test_rejects_*` |
| 2 | Low-confidence / unmatched lines need review | `…::test_low_confidence_and_unmatched_block` |
| 2 | Inconsistent totals flagged | `…::test_total_mismatch_flagged` |
| 2 | Provider outage → manual draft, no stock/payable writes | `…::test_provider_outage_manual_draft` |
| 2 | Duplicate invoice flagged | `test_invoice_posting.py::test_duplicate_invoice_blocked` |
| 3 | Confirm updates stock + payable exactly once; retry idempotent | `test_invoice_posting.py::test_confirm_posts_once` |
| 3 | Stale version/hash rejected | `…::test_stale_confirmation_rejected` |
| 3 | Injected mid-transaction failure leaves nothing | `…::test_rollback_on_failure` |
| 3 | Product (retail) row unchanged | `…::test_confirm_posts_once` |
| 4 | Example utterance → two lines; `10 dahi` asks for unit | `test_voice_inward.py` |
| 4 | Parser outage → no writes; quantity-only → stock only; explicit cost → one payable | `test_voice_inward.py` |
| 5 | <15 days not eligible; ≥15 eligible once; FIFO partial repayment; full repayment cancels; opt-out/unverified blocks; mock only; events recorded | `test_reminders.py` |
| 6 | Clean DB + upgraded copy of a pre-migration DB pass; existing endpoints intact | `test_migrations.py`, `test_existing_behaviour.py` |

**Result (2026-10-30):** every row above has a passing automated test (`python -m pytest -q tests` → 67 passed, network blocked). Status of each row is recorded in [`HACKATHON_EXECUTION_PLAN.md`](HACKATHON_EXECUTION_PLAN.md) and [`BUILD_LOG.md`](BUILD_LOG.md) as phases complete.
