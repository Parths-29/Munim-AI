# Munim-AI — Backend-First Next Phases PRD

**Document purpose:** Handoff brief for Claude Code to analyze and implement the next product capabilities in the existing repository.

**Date:** 2026-10-30

**Current branch to start from:** `codex/sarvam-voice-input`

**Current implementation snapshot:** `11389a4`

**Primary constraint:** Complete domain, API, persistence, validation, and operational logic first. Do not redesign or extend the UI in these phases.

> This is a product/engineering brief for a hackathon prototype. It does not grant access to live Paytm systems, real customer contact data, or permission to message customers. All current data is synthetic/demo data. Production integrations require separate credentials, consent, policy review, and deployment approval.

## 1. Product context

Munim-AI is a merchant copilot for small Indian retailers, scoped to the Paytm Build for India AI Hackathon **Merchant Growth AI** track. Its purpose is to reduce the work and mistakes involved in keeping shop records across customer credit, UPI/payment events, and physical inventory.

The current project already has a FastAPI backend, SQLite demo database, Expo/React Native client, deterministic customer ledger and inventory events, synthetic payment review, merchant insights, Sarvam transcription, bounded Gemini interpretation/explanation, and explicit confirmation flows. See [`PROJECT_BRIEF_AND_CURRENT_STATE.md`](PROJECT_BRIEF_AND_CURRENT_STATE.md) for the current-state handoff, [`BUILD_LOG.md`](BUILD_LOG.md) for evidence, and [`contracts/backend-api-v0.md`](contracts/backend-api-v0.md) for current API behavior.

### Product principle

AI may extract or classify information into a proposal. Deterministic code validates identities, quantities, money, eligibility, and totals. The backend writes only after explicit merchant approval. Ambiguity is returned for review; it is never silently guessed.

## 2. Problem statement

Small retailers often receive stock on paper invoices or informal verbal drop-offs, while separately tracking what they owe suppliers. The shopkeeper may have to re-enter the same delivery twice: once into stock records and again into a supplier credit notebook. Handwritten invoices, varying product names, pack/case units, partial payments, and taxes make transcription error-prone.

The shopkeeper also has customer credit (`udhaar`) that may remain unpaid. A reminder can help, but contacting someone based on guessed identity, an incorrect balance, an assumed visit history, or missing consent can damage trust and create privacy/compliance problems.

### Product problem statement

**How might Munim-AI help a shopkeeper capture incoming stock from paper bills or speech, update inventory and supplier dues from the same verified delivery, and follow up on unpaid customer credit at the right time—without inventing line items, amounts, identities, visit history, or permission to contact?**

## 3. Target scope and explicit non-goals

### In scope for the next backend-first build

1. Supplier profiles and a supplier payable ledger distinct from customer receivables.
2. Invoice/receipt image upload and multimodal extraction into a draft proposal.
3. Merchant-reviewed, atomic posting of accepted invoice lines to inventory and supplier payable records.
4. Voice-based quick stock inward for informal deliveries, with explicit product/unit resolution.
5. A 15-day overdue reminder eligibility engine, merchant review queue, audit trail, and mock notification outbox.
6. API contracts, migrations, domain/service logic, safe provider adapters, tests, and runbooks.

### Out of scope in these phases

- UI redesign or new screens. Expose APIs and domain behavior; current UI can remain unchanged.
- Real supplier payments, bank transfers, Paytm payment APIs, or automatic debt settlement.
- Automatic customer messaging to real phone numbers. Build an auditable mock adapter and a disabled-by-default provider boundary only.
- Inferring visits from UPI transactions. A missing payment event does not mean the customer did not visit or pay cash.
- Automatic stock inference from sales, invoices without merchant confirmation, or supplier price changes to retail selling prices.
- Autonomous invoice posting, arbitrary agent tool execution, or AI-created IDs.
- Production GST/tax compliance claims. Extract displayed invoice fields and label uncertainty; do not certify tax correctness.
- MongoDB migration unless the repository owner explicitly chooses it. Current backend uses SQLite.

## 4. Feature requirements

## Feature A — Supplier accounts and supplier credit khata

The system needs supplier records and a payable ledger separate from the existing customer ledger. Customer balances mean the shop is owed money; supplier balances mean the shop owes money. Do not mix these entry types or reuse a customer balance API for supplier debts.

### Required domain concepts

- `Supplier`: shop-scoped supplier ID, display name, exact aliases, optional business contact details only if explicitly supplied, active status, created timestamp.
- `SupplierPayableEntry`: append-only entries such as `INVOICE_CREDIT`, `PAYMENT`, `DEBIT_NOTE`, and `ADJUSTMENT`; integer paise; source document/event; idempotency key; status; timestamp.
- Derived supplier balance: sum of posted payable credits minus posted supplier payments/credits, with a documented sign convention. Prefer a non-negative `amount_due_paise` field in the response and expose the entry breakdown.
- Supplier invoice records should reference one supplier and one posting operation; a supplier invoice must not create duplicate stock or debt if submitted again.

### Rules

- Supplier matching must be exact or explicitly selected from candidates.
- Do not assume a supplier name from “doodh wale” or “bread wale” maps to a specific legal entity. Allow a merchant-entered label, ask for selection, or record “supplier not identified” without attaching payable debt.
- Keep supplier payable data separate from customer receivables and payment-event reconciliation.
- All money is integer paise in persistence/API calculations. Convert to display rupees only at the client boundary.
- Supplier payments are recorded only after explicit merchant confirmation; this phase does not transfer money.

## Feature B — Paper invoice / delivery bill scanner (primary stock inflow)

### Intended flow

1. Merchant uploads a photo of a distributor tax invoice or handwritten delivery slip.
2. Backend validates file type, size, and image dimensions before passing it to a vision/OCR adapter.
3. The adapter extracts a **draft proposal only**: supplier label, invoice number/date if visible, invoice total, tax/discount/freight/rounding fields if visible, and line items.
4. Each line contains the original text snippet, parsed product description, quantity, unit, unit cost, line total, confidence, warnings, and a product match state.
5. Deterministic validation checks numeric formatting, non-negative values, quantity/unit validity, duplicate invoice signals, and whether the totals reconcile within a small explicit rounding tolerance.
6. Unmatched or low-confidence lines remain unresolved. The API returns candidates and asks the merchant to choose/create a product or edit the field. It does not guess silently.
7. The merchant confirms the full proposal or corrects it. Confirmation triggers one atomic posting operation: accepted quantities become inventory movements and the unpaid invoice portion becomes supplier payable.
8. The system returns the posting IDs and a before/after summary. Replaying the same confirmed operation is idempotent.

### Proposal shape (initial contract; refine after repository audit)

```json
{
  "proposal_id": "draft-generated-by-server",
  "status": "NEEDS_REVIEW",
  "source_kind": "invoice_image",
  "supplier": {
    "display_name": "Sharma Distributors",
    "supplier_id": null,
    "confidence": 0.91
  },
  "invoice": {
    "invoice_number": "INV-204",
    "invoice_date": "2026-10-30",
    "currency": "INR",
    "subtotal_paise": 125000,
    "tax_paise": 22500,
    "discount_paise": 0,
    "freight_paise": 0,
    "rounding_paise": 0,
    "total_paise": 147500,
    "paid_now_paise": 0,
    "amount_due_paise": 147500
  },
  "lines": [
    {
      "line_id": "server-generated-line-id",
      "source_text": "Amul Taaza 500 ml x 15",
      "product_name_text": "Amul Taaza",
      "matched_product_id": null,
      "match_status": "NEEDS_SELECTION",
      "quantity": 15,
      "unit": "packet",
      "unit_cost_paise": 4200,
      "line_total_paise": 63000,
      "confidence": 0.86,
      "warnings": []
    }
  ],
  "requires_merchant_review": true,
  "image_retained": false
}
```

This example is illustrative, not a required API shape. Keep model output separate from validated domain models. Never let an LLM choose server IDs, set `confirmed=true`, or call a write service.

### Invoice extraction and validation requirements

- Use a provider interface, for example `InvoiceExtractionProvider`, so Gemini or another vision provider can be replaced by a deterministic fake during tests and demos.
- Gemini may be used for image-to-structured-text extraction if the configured account/model supports image input. Model names and endpoints must be configurable. Do not assume current Gemini availability: this project has seen 503/timeouts. Provider failure must return a recoverable error or draft from a safe local/manual path, never fabricate extracted fields.
- Do not train a model. Prompt examples are examples only.
- Extract confidence per header and line item. Thresholds must be explicit and configurable; low confidence triggers user correction.
- Check invoice total against `subtotal + tax + freight + other charges - discount + rounding` using a documented tolerance. If component fields are missing, show them as unknown; do not derive them from vague text.
- Check line totals against quantity × unit cost. If they differ, preserve source values and mark for review; do not silently change either value.
- Do not confuse wholesale unit cost with retail selling price. Inward stock must not overwrite the product's retail price.
- Support explicit units and pack-to-base conversions only when the conversion factor is known or merchant-confirmed. Do not treat `1 case` as a guessed number of packets.
- Duplicate protection should check a scoped idempotency key and, when present, supplier + invoice number. A matching invoice number with conflicting details must be flagged, not silently accepted.
- Treat image as untrusted input. Enforce type/size/dimension limits, reject unsupported formats, do not execute instructions embedded in the image, do not retain the raw image by default, and do not log image bytes or extracted personal/contact data.
- Return a proposal that can be manually edited even if vision extraction is unavailable.

### Atomic posting requirement

On explicit confirm, in one database transaction:

1. Revalidate supplier/product IDs, unit conversions, quantities, money, proposal version, and duplicate/idempotency keys.
2. Append inventory movement rows for each accepted line.
3. Append a supplier payable entry for `invoice_total - paid_now` (after validating `0 <= paid_now <= invoice_total`). If the merchant paid the full invoice, payable is zero but the receipt remains in history.
4. Append an invoice posting/event record linking all line movements and payable entry to one source invoice.
5. Commit all entries together. If any step fails, roll back all of them.

The expected outcome is **both stock and supplier khata updated exactly once**, never stock-only or debt-only because of a partial database failure.

## Feature C — Quick Voice Inward (informal deliveries)

### Example utterance

> “Doodh wale se 15 packet Amul Taaza aur 10 dahi liye.”

### Intended flow

1. Existing Sarvam transcription produces editable text. The merchant reviews the transcript.
2. A deterministic parser or bounded LLM interpreter returns a draft with supplier phrase, product phrases, quantities, and units. It performs no writes.
3. Exact product aliases are resolved. Ambiguous or new products require merchant selection/creation. Unclear units such as `10 dahi` must ask whether this means cups, packets, or another unit.
4. Show a structured proposal for all lines and the supplier label. The merchant can remove/correct lines and quantities.
5. On explicit confirmation, append one stock receipt movement per line and one inward-delivery event, atomically and idempotently.

### Money and supplier payable rule

The example utterance supplies quantities but no unit costs or invoice total. **Do not create a supplier payable amount from this utterance.** Record inventory inward only, and label cost/payable as not supplied. If the merchant provides a verified total or unit costs in a separate step, show it in the proposal and require confirmation before posting a supplier payable.

### Natural language safety

- Parse only one delivery proposal at a time.
- Preserve the original utterance and parsed spans for audit, but avoid logging personally identifying audio/transcripts unnecessarily.
- If quantities, product boundaries, units, or supplier are ambiguous, return clarification. No partial write before confirmation.
- “Liye” or “received” means goods were received; it does not imply payment status.
- A voice instruction never bypasses the same preview and confirmation rules as a typed entry.

## Feature D — 15-day customer credit reminders

### Product interpretation and eligibility policy

The requested behavior is interpreted as a reminder for a customer who has a positive unpaid balance whose oldest outstanding credit is at least **15 calendar days old**. This is an overdue rule, not an inference that the customer failed to visit the shop.

The current system does not record visits, so it cannot truthfully determine “has not come to the shop.” Do not infer a missed visit from absent UPI data: the customer may have visited, paid cash, or paid through another app. If visit-aware reminders are desired later, first add an explicit, merchant-recorded visit/contact event and define its reliability.

### Eligibility logic

- Derived current balance is greater than zero.
- Determine age from the oldest still-unpaid credit portion, not simply the date of the last ledger row. Repayments may partially reduce the oldest debt; the implementation must define and document the allocation policy (prefer FIFO against oldest open credits).
- The 15-day threshold uses the shop timezone, configurable per shop, and a scheduler that is safe across restarts.
- A customer is eligible only if they have a verified contact method, explicit reminder opt-in/consent, no opt-out, and the applicable contact channel is available.
- Eligibility is a proposal, not authorization to send. A merchant reviews the name, exact due, oldest due date, proposed neutral message, channel, and reason before approving a reminder.
- Do not include sensitive transaction details in notification text. Never shame, threaten, disclose debt to a third party, or send a message to an unverified number.
- Respect quiet hours, configurable frequency/rate limits, idempotency, opt-out, and duplicate prevention. The same eligible debt must not create a new reminder every scheduler run.

### Notification architecture

- Build an append-only `notification_outbox`/reminder record with states such as `ELIGIBLE`, `PENDING_APPROVAL`, `APPROVED_MOCK`, `SENT`, `DELIVERED`, `FAILED`, `CANCELLED`, and `OPTED_OUT` (refine to the repository's conventions).
- Separate eligibility generation, merchant approval, provider send, and delivery receipt handling.
- Default adapter in hackathon mode is `MockNotificationProvider`; it records a simulated send and clearly labels it as mocked. It does not contact a real number.
- Any real WhatsApp/SMS provider must be disabled by default and require an explicit opt-in configuration, verified recipient, provider credentials, approved templates/policies where required, and an auditable consent record. Do not include real send keys in `.env.example` or commit them.
- Add endpoints/services for consent updates, eligibility preview/list, approve/cancel, mock send, and outcome/status lookup. Use an admin/merchant authorization boundary before production; current prototype has no authentication, so do not expose real sending in this build.
- Message example for mock preview only: “Hello Rajju, our records show an outstanding shop balance. Please contact the shop if you’d like to review it.” The amount should be omitted by default; if the merchant chooses to include it, show it in the approval preview and use a verified private channel only.

## 5. Phased implementation plan (no UI work)

Claude Code should first inspect and write a short repository-specific plan, then execute these phases in order. Each phase must include API/domain/schema changes as needed, tests, runbook updates, a build-log entry, and a clean commit. Do not mark phase complete until acceptance criteria pass.

### Phase 0 — Repository and safety audit

**Goal:** Understand the actual starting tree and prevent accidental breakage.

- Read `AGENTS.md` files, README files, current-state brief, API contract, build log, branch status, database schema, Pydantic models, and service/API patterns.
- Confirm branch/commit and inspect dirty files before editing. Do not reset, clean, or overwrite user data.
- Identify current schema migration approach (if none, design a small versioned migration path that remains compatible with existing SQLite databases).
- Verify `.env` is ignored; check for accidentally tracked secrets without printing secret values. Never read or echo actual key contents into reports.
- Map customer ledger, inventory movements, business events, idempotency, and exact alias resolution.
- Produce a phase plan with touched files, migrations, API contracts, and risks before implementation; then continue automatically unless a blocking product decision is genuinely required.

**Exit criteria:** concise repo audit saved under `docs/` and a checked-in checklist mapping each phase to acceptance criteria.

### Phase 1 — Supplier domain and payable ledger

**Goal:** Add supplier identity and a supplier payable ledger independent from customer receivables.

- Define request/response models and database schema/indexes/append-only protection.
- Add supplier create/resolve APIs with exact aliases and idempotent confirmation.
- Add supplier payable balance/history read APIs and confirmed payable/payment write services as appropriate.
- Preserve integer-paise arithmetic, shop scoping, source event IDs, idempotency, and event audit trails.
- Add migration and seed fixtures for synthetic suppliers; do not alter existing customer or product demo balances.

**Acceptance:** Two suppliers with similar aliases resolve as ambiguous; supplier credit does not affect customer balances; exact duplicate retries create one entry; conflicting idempotency reuse fails; balance totals are derived from append-only entries.

### Phase 2 — Invoice image intake and extraction proposal

**Goal:** Accept invoice images and return a validated, editable proposal without writing stock or supplier debt.

- Add upload validation, a provider abstraction, JSON schema/typed extraction draft, confidence and warnings, manual fallback, duplicate hints, and total/line checks.
- Use Gemini vision only through backend-only credentials and configurable model/provider. Provider outage produces a safe recoverable failure/manual draft, not invented output.
- Keep image bytes out of database and logs; process in memory or secure temporary storage with cleanup. Ensure no public upload URL.
- Add a deterministic fake extraction provider for tests and a synthetic fixture image/text. Never ship a test invoice that contains real personal data.

**Acceptance:** Valid supported image returns a proposal only; malformed/oversized image is rejected; low-confidence/unmatched lines require review; inconsistent totals are flagged; provider outage has no DB writes; duplicate invoice is flagged; uploaded bytes are cleaned up.

### Phase 3 — Confirm invoice and post inventory + payable atomically

**Goal:** Turn an approved proposal into one atomic, auditable receipt.

- Add proposal version/hash to prevent confirmation of a stale edited draft.
- Revalidate all fields at confirmation; do not trust client-supplied IDs, totals, or `confirmed` flags without validation.
- In one DB transaction append invoice, stock movement rows, supplier payable entry, and business events linked by source invoice ID.
- Support `paid_now_paise` as explicit merchant data; payable = invoice total − paid now. Never infer payment from invoice status alone.
- Use robust duplicate protection by supplier/invoice number and idempotency key.
- If any insert fails, all parts roll back.

**Acceptance:** Confirmed invoice updates inventory and supplier payable exactly once; repeated retry is idempotent; edited amount cannot be substituted after preview without version refresh; injected mid-transaction failure leaves no partial stock/debt; purchase cost never changes retail price.

### Phase 4 — Quick voice inward

**Goal:** Turn a voice transcript into a stock receipt proposal; keep the feature useful when no price is known.

- Add bounded `stock_inward` command intent with supplier phrase and multiple line items.
- Parse quantities, names, and units into exact text spans; allow the existing deterministic parser first and LLM interpretation only for unsupported phrasing.
- Resolve products and units exactly; ambiguous units/product names produce clarification.
- Confirm atomically before movement writes. Add payable only when explicit verified prices/total are provided and merchant-approved.

**Acceptance:** Example utterance produces two correct line proposals; ambiguous `10 dahi` asks for unit; provider/parser outage creates no writes; quantity-only inward changes stock only; explicit confirmed cost also creates one payable; retries do not duplicate.

### Phase 5 — Consent-aware 15-day reminder engine and mock outbox

**Goal:** Detect eligible overdue customer credit and let the merchant review a mock reminder.

- Define FIFO oldest-unpaid-credit age calculation and test partial repayments.
- Add verified contact + consent/opt-out data model with audit metadata and channel; do not infer consent.
- Add scheduler-safe eligibility creation, timezone handling, idempotency, quiet hours, rate limits, and state transitions.
- Add merchant-facing API endpoints only; no UI. Default provider is mock-only. Real provider code must be disabled and not callable without explicit configuration plus authorization.
- Add message content rules and a safe delivery-status model.

**Acceptance:** Due under 15 days is not eligible; due at/over 15 days is eligible once; partial payment retains correct age on remaining amount; full repayment cancels pending reminder; opt-out/unverified contact blocks sending; retries create no duplicate; no provider call occurs in mock mode; events record eligibility, approval, cancellation, and mocked delivery.

### Phase 6 — Integration, data migration, and handoff

**Goal:** Make the new backend flows safe to run against existing and clean demo databases.

- Exercise existing endpoints and data after schema migration; run clean-seed and existing-db upgrade rehearsals.
- Verify API docs/contracts, migration rollback/recovery notes, provider config docs, and sample synthetic fixtures.
- Add explicit security and privacy checks; check that logs do not contain secrets, raw images, or unnecessary contact information.
- Update `docs/BUILD_LOG.md`, `docs/HACKATHON_EXECUTION_PLAN.md`, API contract, backend README, and this PRD with verified results.
- Keep the frontend unchanged. Provide `curl`/PowerShell examples or Swagger steps for API verification.

**Acceptance:** All phase checks pass on a clean DB and preserved DB; no live messaging; no secret values in Git; existing ledger/inventory/payment behavior remains intact; current user can hand off the branch and operate the new backend APIs from documented commands.

## 6. API/service boundary proposal

Names are provisional. Claude Code should align with the repository conventions rather than blindly copying this list.

| Area | Possible endpoints | Writes? |
|---|---|---|
| Suppliers | `POST /suppliers`, `GET /suppliers/resolve`, `GET /suppliers/{id}/balance`, `GET /suppliers/{id}/entries` | Profile/ledger writes require confirmation. |
| Invoice scan | `POST /invoices/proposals` (multipart image), `GET /invoices/proposals/{id}` | Extraction route is draft-only. |
| Invoice posting | `POST /invoices/proposals/{id}/confirm` | Merchant-confirmed atomic write. |
| Voice inward | `POST /inventory/inward/proposals`, `POST /inventory/inward/{id}/confirm` | Draft then explicit confirmation. |
| Reminder consent | `PUT /customers/{id}/reminder-consent` | Explicit merchant-recorded consent evidence; no inferred opt-in. |
| Reminder eligibility | `POST /reminders/eligibility/run` (internal/admin guarded), `GET /reminders/eligible` | Creates proposals/outbox only; no external send. |
| Reminder approval/mock | `POST /reminders/{id}/approve`, `POST /reminders/{id}/mock-send`, `POST /reminders/{id}/cancel` | Approval and mock state transitions; no external send. |

Avoid unauthenticated public endpoints that can trigger external messages. Since the prototype lacks authentication, all notification send operations must stay mock-only.

## 7. Data model and integrity requirements

- Keep monetary values as integer paise with INR currency explicitly stated.
- Use shop-scoped supplier/product/customer IDs; never accept model-generated IDs.
- Keep customer receivables and supplier payables in separate tables/services and response fields.
- Keep inventory quantities with explicit unit and conversion metadata; do not store ambiguous unit strings as interchangeable.
- Keep append-only ledger/movement rows; corrections are compensating entries, not updates/deletes.
- Every write records source event, source channel, actor/confirmation, idempotency key, and timestamps.
- Use DB transactions for any operation that affects more than one subsystem.
- Model proposal state (`DRAFT`, `NEEDS_REVIEW`, `READY`, `CONFIRMED`, `REJECTED`, `EXPIRED`) and version/hash if needed.
- Enforce uniqueness for shop-scoped idempotency keys and invoice identity; define conflict behavior explicitly.
- Store provider/model name, request correlation ID, confidence, and validation outcome where useful, but never API keys or raw audio/image payloads.
- Avoid schema changes that silently rewrite existing demo rows. Migrations must be additive and tested on a copy/fixture.

## 8. Non-functional requirements

- Provider timeouts are bounded; retry behavior is explicit and cannot duplicate writes.
- LLM/OCR output is treated as untrusted input and validated against strict schemas.
- Upload content type is not trusted alone; size and image dimension limits are enforced.
- No image, audio, phone number, or credential appears in logs or build output.
- Use deterministic fake providers for repeatable tests; do not depend on a live API for core correctness.
- API errors are useful to the merchant/operator but do not leak provider secrets or raw upstream responses.
- Keep local SQLite support. Do not introduce MongoDB or a new infrastructure service without a documented reason.
- No UI work in these phases; maintain backward compatibility for current mobile requests.

## 9. Environment and setup for the friend’s laptop

### Clone and select the branch

```powershell
git clone https://github.com/Parths-29/Munim-AI.git
cd Munim-AI
git fetch origin
git switch --track origin/codex/sarvam-voice-input
```

If that local tracking branch already exists:

```powershell
git switch codex/sarvam-voice-input
git pull
```

### Install current backend and mobile dependencies

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
cd ..\mobile
npm ci
```

### Local environment variables

- Copy root `.env.example` to root `.env` on the friend’s machine. `.env` is ignored by Git.
- `SARVAM_API_KEY`: needed only to use live Sarvam speech transcription.
- `GEMINI_API_KEY`: optional for facts explanation and proposed image/document extraction. Command interpretation uses Sarvam Chat Completions with `SARVAM_API_KEY`.
- `GEMINI_MODEL`: optional configurable model name only if implementation adds/uses it; do not assume a model is enabled for the account.
- `MUNIM_DB_PATH`: optional local SQLite path for an isolated demo database. Use a new timestamped path for experiments; never point at the original user DB on the friend’s laptop.
- `MONGODB_URI`: **not required**. MongoDB is not used by the current backend; leave blank.
- `EXPO_PUBLIC_API_BASE_URL`: set in mobile config only to the backend base URL, never put provider secrets in a `VITE_*` or `EXPO_PUBLIC_*` variable.

Do not send credentials in the Claude Code prompt, GitHub issue, commit, or chat. Share new test keys directly through the friend’s local ignored `.env` or the OS secret store. Credentials previously pasted into chat/shared logs should be rotated before reuse. `.env.example` contains placeholders only.

## 10. Copy/paste prompt for Claude Code

```text
You are continuing the Munim-AI / KiranaOS hackathon prototype in this cloned repository. Work from the existing implementation; do not reimagine the product or start a replacement app.

PRODUCT CONTEXT
The project targets the Merchant Growth AI track. It helps a small retailer keep customer udhaar, stock, supplier obligations, payment events, and useful next actions in a reliable shop memory. Current backend is FastAPI + SQLite; current client is Expo/React Native. Synthetic data only. There is no production Paytm integration, no MongoDB persistence, no authentication, and no real customer messaging.

FIRST: REPOSITORY AUDIT
1. Read all applicable AGENTS.md files, README.md files, docs/PROJECT_BRIEF_AND_CURRENT_STATE.md, docs/HACKATHON_EXECUTION_PLAN.md, docs/BUILD_LOG.md, docs/contracts/backend-api-v0.md, and backend/mobile code relevant to database schema, ledger, inventory, events, command parsing, speech, and provider configuration.
2. Confirm current branch, commit, and clean/dirty state. Preserve existing user changes and database files. Do not reset, clean, force-push, or delete data.
3. Inspect `.gitignore` and `.env.example`; check whether secrets are tracked without printing their contents. Never read out, copy, log, or commit actual key values. Do not ask me to paste keys into this prompt.
4. Before changing code, write `docs/NEXT_PHASES_AUDIT.md` with actual architecture, migration approach, current behavior, risks, touched files, proposed endpoint contracts, and phase acceptance checklist. Then continue implementation without waiting unless a genuinely blocking product choice is missing.

PRODUCT REQUIREMENTS TO IMPLEMENT (BACKEND/DOMAIN FIRST; NO UI WORK)

A. SUPPLIER ACCOUNTS AND PAYABLE KHATA
- Add supplier records, exact alias resolution, and a supplier payable ledger. Keep it separate from customer receivables and the existing customer ledger.
- Derive balances from append-only integer-paise entries; support invoice credit and confirmed supplier payment/adjustment entries with idempotency and audit events.
- Never infer a supplier identity from a generic phrase like “doodh wala.” Ask for exact merchant selection or keep supplier unresolved.

B. PAPER INVOICE / DELIVERY BILL SCANNER
- Add an image upload/extraction proposal API. Use an adapter boundary for a multimodal provider; Gemini vision may be used only from the backend and must be configurable. Provider outage must not fabricate data or block manual correction.
- Extract draft supplier, invoice metadata, totals/tax/discount/freight if visible, and multiple line items with source snippets and per-field confidence. Treat OCR/LLM output as untrusted.
- Validate file bytes/type/dimensions, line amounts, quantity × unit cost, invoice arithmetic, duplicate invoice signals, exact product matching, and unit conversions. Unknown values remain unknown; ambiguous products/units require review.
- Do not change retail prices from wholesale unit cost. Do not store raw images by default; clean temporary files; do not log image or secrets.
- Draft endpoint must not mutate stock or payables. Return a versioned proposal requiring merchant edits/confirmation.
- On confirmation, one database transaction must append inventory movements, invoice record, supplier payable for total minus an explicitly entered amount paid now, and linked business events. Any error rolls back every effect. Idempotent retry creates one posting only.

C. QUICK VOICE INWARD
- Add a bounded `stock_inward` proposal intent for reviewed transcript/text like “Doodh wale se 15 packet Amul Taaza aur 10 dahi liye.”
- Parse multiple product lines, quantities, units, and optional supplier phrase. Exact product/unit resolution only; `10 dahi` must ask whether this means cups, packets, etc. if no exact unit exists.
- Return a structured proposal and require explicit merchant confirmation before stock movements.
- The example has no cost or invoice total: post stock only. Never invent supplier payable. If the merchant adds explicit price data, preview and confirm payable separately/in the same atomic receipt.
- Sarvam transcription remains editable; voice never bypasses preview/confirmation.

D. CUSTOMER REMINDER FOR OVERDUE UDHAAR
- Implement eligibility for a positive balance whose oldest still-unpaid credit portion is at least 15 calendar days old in the shop timezone. Define FIFO allocation of repayments to oldest credits and test partial repayments.
- Do not claim the customer has not visited. The app has no reliable visit history and absence of UPI data is not evidence of no visit. If visit status is required, add explicit visit events later; do not infer it.
- Require verified contact + explicit opt-in + no opt-out before any customer contact. The merchant must review recipient, amount/due date, channel, and message and explicitly approve.
- Build an idempotent notification/outbox state machine and a `MockNotificationProvider` only. NO REAL SMS/WhatsApp sending in this work: repository has no authentication and we have not supplied provider approval/configuration. Real adapters must be disabled by default and impossible to call in mock mode.
- Add quiet hours, rate limits, duplicate suppression, cancellation when fully repaid, and an auditable delivery status model.

IMPLEMENTATION ORDER
Phase 1: supplier/payable schema/services/API and migration.
Phase 2: invoice image draft extraction and validation, no writes.
Phase 3: atomic confirmed invoice posting to stock + supplier payable.
Phase 4: voice inward proposal and confirmed stock receipt.
Phase 5: 15-day eligibility, consent, merchant approval API, and mock outbox.
Phase 6: migration rehearsal, integration checks, API docs, runbook/build log/handoff.

QUALITY BAR
- Do not change UI, screens, styling, or navigation. Backend and API documentation only.
- Preserve current endpoints, balances, inventory, and demo DB. Use a separate temporary DB for tests/rehearsals.
- Use strict Pydantic models, integer paise, shop scoping, idempotency, exact-match resolution, append-only records, transactions, bounded provider timeouts, and safe fallback.
- Add/run focused automated checks for domain logic, migrations, duplicate retries, transaction rollback, confidence/ambiguity, consent, 15-day boundaries, and partial repayment FIFO. Use fake providers; tests must not call live Gemini/Sarvam/SMS APIs.
- No test may send a real notification or mutate the user's existing demo database.
- Update docs/contracts/backend-api-v0.md, backend/README.md, docs/HACKATHON_EXECUTION_PLAN.md, and docs/BUILD_LOG.md after each completed phase. Record verified facts, not assumptions.
- Work in small coherent commits on the existing feature branch. Push normally; never force-push. If origin advanced, fetch and merge safely before pushing. Do not open/merge a PR unless I explicitly ask.
- After each phase, report changed files, schema changes, commands/checks run, results, known limitations, commit SHA, and exact next phase. Continue automatically to the next phase unless blocked by a material decision or external credential approval.

ENVIRONMENT
Use `.env.example` as the template. SARVAM_API_KEY is only for speech; GEMINI_API_KEY is optional for server-side interpretation/vision; MONGODB_URI is unused and not required. Keep all secrets in the local ignored `.env` or OS secret store. Never put secrets in this prompt, mobile config, logs, screenshots, or Git.

Start by reading the repository and current branch; then produce the audit document and execute Phase 1. Do not implement any UI changes.
```

## 11. Decisions to revisit after repository audit

Claude Code should document a recommendation and proceed with the safe default unless a choice affects real customer contact, legal policy, or irreversible production data:

1. **Invoice images:** Use ephemeral processing and discard by default; ask before adding retention.
2. **Supplier invoice status:** Treat invoice total as payable evidence, but record any paid-now amount only when the merchant explicitly enters/confirms it.
3. **Units:** Require a known conversion or exact merchant choice; do not convert cartons/cases by assumption.
4. **15-day rule:** Oldest unpaid-credit age is the initial eligibility trigger. “No visit” cannot be represented until explicit visit logging exists.
5. **Notification provider:** Mock-only. Real send requires consent evidence, authentication, authorized provider configuration, and separate approval.
6. **Persistence:** Continue SQLite for this prototype. Do not add MongoDB just because a URI variable exists.

## 12. Completion definition

The backend-first roadmap is complete when invoice proposals never write before confirmation; an approved invoice atomically changes both stock and supplier payable once; voice inward correctly handles multiple lines and clarifies ambiguous units; the reminder engine respects 15-day age, FIFO repayment aging, consent, opt-out, and mock-only sending; existing customer/payment/inventory features remain intact; clean and existing SQLite databases upgrade safely; and another developer can run the APIs from the written setup without seeing any secret values.


## 13. Implementation status (verified 2026-10-30)

All six phases are implemented on `codex/sarvam-voice-input`, backend only, with the UI unchanged. Evidence: `docs/NEXT_PHASES_AUDIT.md` (acceptance → test map), `docs/NEXT_PHASES_RUNBOOK.md` (setup, rehearsal, API walk-through), `docs/BUILD_LOG.md`, and `docs/contracts/backend-api-v0.md` (v0.9).

- 67 automated tests pass on temporary databases, with all outbound network calls blocked.
- A clean DB rehearsal and an upgraded copy of a DB created by pre-change commit `5bec501` both pass end to end. On the upgraded copy, existing balances, stock, and synthetic transactions are unchanged.
- Decisions taken (section 11 defaults): invoice images are processed in memory and never retained (only a SHA-256 digest for duplicate hints). Paid-now is explicit at confirm. Pack conversions are merchant-confirmed. The reminder rule is oldest-unpaid-credit age with FIFO repayment and no visit inference. Notifications are mock-only. Storage remains SQLite.
- Stock receipts use a new append-only `stock_receipt_movements` table rather than rebuilding `inventory_movements` (its CHECK constraint only allows `PHYSICAL_COUNT`). On-hand is the sum of both tables.
- `stock_inward` is a dedicated endpoint (`/inventory/inward/proposals`) rather than a new `/commands/interpret` intent, so the mobile client's closed intent union is unaffected.
- Not verified: live Gemini vision extraction (provider recently returned 503/timeouts), and on-device use of the new APIs (no UI yet).
