# Growth Phases (N7–N12): Bahi-Khata Recovery, Settlement Concierge, Paytm Insights

These phases follow on from [`NEXT_PHASES_BACKEND_FIRST_PRD.md`](NEXT_PHASES_BACKEND_FIRST_PRD.md). They implement the team's idea notes:

- the bahi-khata scanner → udhaar recovery agent;
- the "Paise kyun kam aaye?" settlement explainer;
- the support root-cause miner, combined into a two-sided product.

The same trust contract applies throughout: AI proposes, deterministic code validates and computes every ₹, the merchant confirms, and everything is synthetic or mock unless stated otherwise.

| Phase | Scope | Status |
|---|---|---|
| N7 | Bahi-khata notebook scanner | **Done** |
| N8 | Recovery agent: language, Sarvam translate + Bulbul voice note, UPI link, WhatsApp click-to-send, payment-reference matching, recovery metrics | **Core done** (slice 1); voice note, WhatsApp link, metrics pending |
| N9 | "Paise kyun kam aaye?" settlement explainer + merchant concierge | Pending |
| N10 | Paytm-side root-cause insights | Pending |
| N11 | Mobile screens for N1–N10 | Pending |
| N12 | Integration, live provider smoke check, handoff | Pending |

## N7 — Bahi-khata notebook scanner

**Flow:** photo of a notebook page → `POST /ledger-pages` (multipart `file`, `idempotency_key`) → editable draft → merchant edits (`/revise`) or speaks a correction (`/voice-correction`, for example “Sharma ji, 1200 udhaar”) → `POST /ledger-pages/{id}/confirm`.

- **Extraction** (`MUNIM_NOTEBOOK_PROVIDER`, falling back to `MUNIM_INVOICE_PROVIDER`: `gemini` | `fake` | `none`). The model copies each row exactly as written: name (any script, plus a Latin transliteration if readable), amount text, the udhaar/jama marker word, and date text. Deterministic code then:
  - converts Devanagari, Gujarati, and other Indic digits to ASCII;
  - maps known marker words (`udhaar`/`उधार`/`baki`/`ઉધાર` → credit, `jama`/`जमा`/`mila`/`જમા` → repayment);
  - parses dates (ISO, or DD/MM/YYYY flagged when ambiguous).

  Unknown markers stay unset. Image validation is the same as for invoices, and the image is never retained. There is no confirmed Sarvam Vision API in this build. The provider slot is ready for it.
- **Validation** (recomputed on every read):
  - Exact customer match on either spelling: `MATCHED`, `AMBIGUOUS` (choose one), or `NOT_FOUND` (with suggestions). New customers are created only when the merchant sets `create_customer`.
  - Required amount and credit/repayment type.
  - Low confidence needs verification.
  - No future dates.
  - A repayment may not exceed the running balance (existing balance plus earlier rows on the page, in date order).
  - Possible-duplicate warnings, for the same customer/amount/date already in the ledger and for the same photo scanned twice.
- **Voice correction** applies the spoken amount (and udhaar/jama word, if said) to the one row whose name matches exactly, marks it verified, and saves a new version. Zero or several matches → clarification, with no change.
- **Confirm** is one transaction: create the chosen customers (aliases: both spellings), append one ledger entry per accepted row with `occurred_at` = the notebook date, timeline events, and a posting batch. Version + content hash are required. Warnings need `acknowledge_warnings`. Replays are idempotent. A repayment that settles a balance cancels pending reminders.
- **Aging:** reminder FIFO aging now uses `COALESCE(occurred_at, created_at)`. An old notebook udhaar therefore ages from its written date, not the scan date.
- **Schema (migration 5):** additive `ledger_entries.occurred_at`; `ledger_page_proposals`; append-only `ledger_page_revisions` and `ledger_page_postings`.

## N8 — Recovery concierge (slice 1: focused core)

**Flow:** set the shop UPI ID once → (optional) set the customer's language → `GET /customers/{id}/recovery-brief` → merchant reviews → `POST /reminders/{id}/approve` with the reviewed text and `include_payment_link` → mock send (unchanged) → the customer pays through the link → `POST /payments/intake` with `payment_reference` → matched and allocated.

- **Brief (read-only, writes nothing):** the balance, the open udhaar entries after FIFO repayment, the oldest unpaid date and age, eligibility with plain-language reasons (for example "reminders start at 15 days", "ask the customer at the counter"), the active reminder, past pay links with paid status, and a draft reminder.
- **Localized draft:** Sarvam Mayura translates the English reminder into the customer's language (`/customers/{id}/language`, default `en-IN`). If a translation changes any number, the draft falls back to English. The brief returns a ready `approve_payload`.
- **Approval guard:** `language_code` + `localized_message` are accepted only if the text carries exactly the same numbers as the current English reminder (Indic digits count as the same number). Otherwise `422 LOCALIZED_NUMBERS_MISMATCH` and the reminder stays `PENDING_APPROVAL`. This also catches a balance that changed after the brief. No network call happens inside the approval transaction.
- **UPI pay link:** with `include_payment_link`, approval creates an append-only `collection_request` with a unique reference (`MJ…`) and appends `upi://pay?pa=…&pn=…&tr=<ref>&tn=…&cu=INR` to the message. `am=` is included only when the merchant chose to include the amount. Without a shop UPI ID: `409 UPI_PROFILE_MISSING`.
- **Payment-reference matching:** `payment_reference` (case-insensitive) on a payment event resolves the customer through the collection request, under the same rules as payer tokens: allocate when ≤ balance, otherwise `REVIEW`. An unknown reference with no mapped payer is `UNMATCHED payment_reference_not_found`. A reference and a payer token that point to different customers go to `REVIEW payment_reference_conflicts_with_payer`. Full repayment cancels pending/approved reminders. A collection request reports `OPEN` / `PART_PAID` / `PAID`, including later manual allocations.
- **Boundaries:** sending stays mock-only; nothing contacts a customer. Live Sarvam is used only when `SARVAM_API_KEY` is set (tests force fake mode).
- **Schema (migration 8):** `customer_preferences`, `shop_payment_profiles`, append-only `collection_requests`; additive `payment_events.payment_reference` / `collection_request_id` and `reminder_transitions.language_code`.
- **Slice 2 (pending):** on-demand Bulbul voice note of the approved text (never stored), WhatsApp click-to-send link that the merchant taps themselves (the server never sends), and recovery metrics.
