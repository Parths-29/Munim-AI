# Munim-AI / KiranaOS — Project Brief and Current State

**Purpose:** Give a teammate, judge, or new coding agent enough context to understand the problem, the product decisions, what is implemented, what has been verified, and how to continue without relying on chat history.

**Current snapshot:** 2026-10-30

**Repository:** `Parths-29/Munim-AI`

**Active branch:** `codex/sarvam-voice-input`

**Implementation snapshot commit:** `f84584b` — `docs: record command summary endpoint verification`

**Product status:** Working local prototype using synthetic shop/payment data. Integrated demo readiness is still in progress.

> The project name Munim-AI describes the merchant-facing copilot. KiranaOS describes its structured shop memory and APIs. This is a hackathon prototype; it is not connected to Paytm production systems and does not process real payments.

## 1. Hackathon context and track

The team-provided event brief describes the Paytm Build for India AI Hackathon — Mumbai Edition as a fintech build event, with three tracks:

1. **Merchant Growth AI:** Build an AI business partner that helps Paytm merchants grow, run operations, and serve customers.
2. **AI-Powered Financial Journeys:** Make insurance, lending, and fintech journeys simpler for customers.
3. **Autonomous AI Teammates:** Build an AI teammate that understands context and completes measurable sales or customer-service work with people.

Munim-AI is scoped to **Track 1: Merchant Growth AI**. The event description above is paraphrased from the brief supplied by the team. This document does not claim to be the official judging rubric.

## 2. Problem statement

Small shops often keep important business information in separate places: a notebook or memory for customer credit, UPI apps for payments, manual shelf checks for stock, and conversations for customer requests. A payment notification can show that money arrived, but it does not reliably tell the shopkeeper which customer's balance to update, how much is still due, or whether the payment corresponds to a debt. UPI data alone also cannot tell the shop's total revenue, physical inventory, profit, or reason for a sales change.

Keeping these records linked takes time and creates avoidable mistakes. A system that guesses a customer, amount, stock quantity, or payment match can create real harm.

### Product problem statement

**How might we help a small retailer record everyday shop events in simple language, keep customer dues and stock history understandable, connect payment evidence cautiously, and see useful next steps—while asking the merchant to resolve uncertainty and approve every consequential change?**

### Target user and job to be done

- **Primary user:** An owner or staff member at a small Indian retail shop, such as a kirana, tea stall, or medical store.
- **Context:** They need quick answers while serving customers and may prefer speaking in Hindi/Hinglish or entering a short command.
- **Job:** “Let me record or check a shop detail quickly, then show me the evidence and exact change before you save anything important.”

## 3. Product proposal and intended distinction

Munim-AI is a **trusted shop memory and action copilot**, not a general chatbot and not a payment processor. Its core product idea is to combine:

- A simple text/voice entry point for everyday shop commands.
- Structured, append-only records for customer credit, repayments, stock observations/counts, payment events, and merchant actions.
- Deterministic calculations for balances, stock-on-hand, and business metrics.
- AI assistance constrained to interpreting a command or explaining supplied facts.
- Clear evidence, uncertainty, and caveats.
- A merchant preview and explicit confirmation before a write or outward-facing action.

Paytm already offers merchant analytics and payment/business tools. The prototype therefore does **not** claim that merchant analytics do not exist or that this concept is unique in the market. Its intended product distinction is the careful connection between conversational shop records, a transparent ledger/inventory memory, cautious payment review, and a merchant-controlled next step. Whether that distinction wins or improves real shop outcomes has not been proven.

## 4. The core product loop

1. **Ask or record:** The merchant types a command or records a short voice clip.
2. **Review transcript:** Sarvam returns text; the merchant can inspect/edit it before sending. Speech recognition can mishear names or numbers.
3. **Interpret:** A deterministic parser recognizes common supported commands. For an unsupported phrasing, a Gemini service may propose a bounded intent and exact quoted spans. The client validates and reparses the result.
4. **Resolve:** Customer and product names are matched by exact shop-scoped aliases. Missing or ambiguous matches stop for clarification; the system does not silently choose.
5. **Preview:** A write shows the exact customer/product, amount/count, and effect before it is saved.
6. **Confirm:** The merchant explicitly approves. The backend validates the operation and idempotency key.
7. **Remember and explain:** The backend appends a ledger/event record; summaries derive values from stored facts and make the data limits visible.

Read-only checks and summaries do not need a write confirmation. Credit, repayment, customer creation, stockout reports, physical counts, payment allocation, and mock action approval do.

## 5. Current implemented scope

### 5.1 Merchant command and ledger

- Customer aliases resolve exactly; ambiguous aliases require the merchant to select a record.
- Customer balances are computed from posted ledger entries.
- Credit and repayment commands pass through preview and explicit confirmation.
- A repayment cannot exceed the outstanding balance; rejected repayments do not add a ledger entry.
- New customer creation is supported as its own action. For example, `Add new customer Rajju Sharma` shows the exact spelling in a preview. Confirming creates the customer profile only; it does not create debt.
- Voice-originated commands retain their source channel and utterance for event history where supported.
- Repeated writes use idempotency keys/source event IDs to prevent duplicate effects.

### 5.2 Voice input and command understanding

- The app records a short clip and sends it to the FastAPI speech endpoint.
- The backend forwards audio to Sarvam STT and does not persist the audio. The returned transcript is editable in the app.
- The merchant reviews the transcript and presses Send. A transcript is not itself permission to change data.
- Voice and typed text share the same command parser, entity lookup, preview, and confirmation flow.
- Common phrasing uses deterministic parsing. Gemini command interpretation is an assist for unsupported phrasing; its response is restricted to a supported intent and verbatim entity/amount/count spans. It cannot write to the database.
- Current supported command families include:
  - Customer credit/udhaar and repayment/jama.
  - Customer balance/due lookup.
  - Add a new customer.
  - Report a product stockout.
  - Check the latest recorded stock count.
  - Propose a physical stock count.
  - Summarize recorded payment events.
  - Summarize recent shop activity/timeline.
- Voice name and number recognition is not guaranteed. Review and edit the transcript before sending, especially for money and customer names.

### 5.3 Inventory memory

- Product aliases resolve exactly; ambiguous matches do not select arbitrarily.
- “Stockout observed” is a merchant observation. It creates an event but does not change quantity.
- A physical count is a separate action. After preview and confirmation, the backend records the counted quantity and delta.
- Stock lookup returns the latest quantity derived from recorded movements. It is **not** a live shelf sensor and UPI transactions are not used to infer stock sold.
- Current demo snapshot (read-only check on 2026-10-30): Maggi is recorded at **0 packs**, which the user confirmed is intentional.

### 5.4 Mock payment intake and reconciliation

- The payment intake/review feature creates synthetic provider-mock payment events; it does not connect to Paytm or any UPI provider.
- Automatic ledger allocation is allowed only for a successful event with an exact confirmed synthetic payer-token mapping, a customer with positive due, and an amount that fits the full outstanding balance.
- Unmatched, ambiguous, excess, pending, failed, or reversed cases do not silently become repayments. Eligible unresolved successful events can be reviewed and manually allocated by the merchant.
- A payment event is not the same thing as a ledger repayment. The summary reports them separately.
- Current demo snapshot (read-only check on 2026-10-30): one mock payment event is recorded, no open review remains, and two repayments totaling **₹300** are posted in the ledger. This state may change as the demo continues.

### 5.5 Business insights and merchant-approved action

- A deterministic 90-day synthetic transaction fixture supports three personas: kirana, tea stall, and medical store.
- Facts are calculated in Python, not by an LLM. Current metrics include successful UPI collections, collection change versus the preceding comparable 7-day window, median payment amount, payment failure rate, and a count of synthetic payer tokens that were frequent in the prior 28 days but absent in the current 7-day window.
- The metric logic does not infer customer identity or why a metric changed. “Lapsed” refers to synthetic payer tokens, not known people.
- Gemini may explain only the supplied facts. Numeric validation rejects unsupported figures; action text is selected from server-owned templates. If the model fails or its output fails validation, deterministic text is used.
- The proposed action is a shop-side counter notice or mock QR offer. The merchant can edit it and must explicitly approve it.
- Approved actions are recorded as `APPROVED_MOCK`; nothing is sent or published to customers. The later comparison is observational and does not prove causality.

### 5.6 Payment and activity summaries

- `GET /events/summary` supplies deterministic totals for ledger credits/repayments, payment event status, successful events still awaiting review, inventory observations/counts, and recent payment/timeline entries.
- Home commands and Timeline display useful summary text and details.
- The scope is **all recorded synthetic demo history**, not live transactions and not a true current-day Paytm feed. The UI and API label this limit.

## 6. Example commands for the demo

Use text or a voice transcript, then follow the indicated flow:

| Example | Expected behavior |
|---|---|
| `Raju bhai ka balance batao` | Read-only due lookup; exact alias required. |
| `Raju bhai ka ₹50 udhaar likh do` | Preview the customer and ₹50 credit; confirmation required. |
| `Raju ne ₹50 jama kiye` | Preview repayment; backend rejects an amount above due. |
| `Add new customer Rajju Sharma` | Preview exact spelling; confirmation adds profile only. |
| `How many Maggi packs are left?` | Read-only latest recorded count; says it is not a sensor reading. |
| `Maggi khatam ho gaya` | Preview a stockout observation; count does not change. |
| `Set Maggi stock count to 10 packs` | Preview physical count; confirmation changes recorded on-hand quantity. |
| `Summarize payments` | Reports mock payment statuses separately from ledger repayments. |
| `What happened in the shop today?` | Reports the recent recorded synthetic timeline; clarifies that this is not a live daily feed. |
| `Aaj kaisa raha?` | Loads the facts-only business brief and proposed mock merchant action. |

If Sarvam misrecognizes a name or amount, correct the editable transcript before Send. Never confirm a preview whose spelling, amount, or product is wrong.

## 7. System design and technology

### Client

- **Path:** `mobile/`
- **Stack:** Expo / React Native / TypeScript, with Expo Web support.
- **Main surfaces:** Home/Copilot, Insights, Inventory, Payment Review, Timeline.
- `mobile/src/api/ledgerClient.ts` is the typed API client.
- `mobile/src/features/home/parseMerchantCommand.ts` handles bounded deterministic command parsing.
- Home owns interpretation, exact lookup, preview, and confirmation orchestration.

### Backend

- **Path:** `backend/`
- **Stack:** Python 3.11, FastAPI, SQLite for the local prototype.
- **Database:** Local synthetic demo data. Default is `backend/data/munim.sqlite3`; `MUNIM_DB_PATH` can point to a separate demo file.
- **Routes:** Health, speech, command interpretation, customers, ledger, inventory, payments, events/summaries, insights, and mock actions.
- **Services:** Deterministic ledger, inventory, event, insight, and summary logic; server-side Sarvam and Gemini adapters.

### External services and data boundaries

- **Sarvam:** Optional speech-to-text. Audio is forwarded for transcription and not stored by this backend.
- **Gemini:** Optional command interpretation and facts explanation. Current observed calls have returned HTTP 503 or timed out; deterministic fallback is expected when this happens.
- **MongoDB:** Not used by the implemented prototype. Local app persistence is SQLite.
- **Paytm:** No production API, merchant dashboard, account, payment feed, or live credentials are connected.
- **Data:** Synthetic transaction fixture and merchant-entered demo events only. Never commit API keys, customer exports, personal data, or actual payment data.

## 8. Current observed state and verification

### Local demo database snapshot

The active local backend was restarted with the existing synthetic/demo database preserved. Read-only endpoint checks on 2026-10-30 reported:

- `GET /health`: HTTP 200.
- `GET /events/summary`: HTTP 200; 17 recorded business events, 1 mock payment event, 2 posted repayments, and 0 open payment reviews.
- Exact customer lookup resolved `Raju bhai`; derived balance was **₹300** at the time of check.
- Exact product lookup resolved `Maggi`; on-hand quantity was **0 packs**, intentionally set by the user.
- No records were changed by these checks.

This is a mutable demo snapshot, not a hard-coded product promise. Starting with a fresh database or continuing the demo changes the counts and balances.

### Build checks recorded

- Mobile `npm run typecheck`: passed after current command/summarization work.
- Backend `python -m compileall -q backend/app`: passed after current service/model changes.
- `GET /events/summary` smoke check: returned HTTP 200 against both an isolated synthetic database and the preserved local demo database.
- **Not yet verified for this latest slice:** a fresh full browser/device acceptance run of every new command, real microphone-to-command round trip with a current Sarvam response, physical phone/LAN use, and live Gemini-generated interpretation/explanation.

See [`BUILD_LOG.md`](BUILD_LOG.md) for dated implementation/audit notes, [`HACKATHON_EXECUTION_PLAN.md`](HACKATHON_EXECUTION_PLAN.md) for phase status, and [`BROWSER_DEMO_WALKTHROUGH.md`](BROWSER_DEMO_WALKTHROUGH.md) for the clean-demo rehearsal.

## 9. Known limits and risks

1. **Synthetic prototype:** No Paytm production connection, real merchant feed, or live customer data.
2. **Gemini availability:** Current local requests return intermittent 503/timeouts. Deterministic fallback preserves bounded behavior; the AI-generated path is not currently a reliable demo dependency.
3. **Speech quality:** STT may mishear Hindi/Hinglish names, product names, and spoken amounts. Transcript review is required. A typed command is the fallback.
4. **No live sales or stock inference:** UPI collections are not total revenue or profit. Stock is only as current as the last count entered.
5. **Mock payment feed:** Payment status and ledger repayment are separate. Synthetic tokens are not customer identities.
6. **No causal proof:** The mock action comparison cannot establish that the action caused a sales change.
7. **No authentication/production security model:** The prototype has no merchant account system, roles, production deployment controls, or durable multi-tenant infrastructure.
8. **Research fraud model deferred:** The provided model bundle has not been independently integrated/validated in this codebase; it is outside the active demo path.
9. **Credentials:** Secret values are intentionally omitted from this document and must remain backend-only. Rotate any test credential that has been exposed in chat or a shared log before production use.

## 10. Work status and next steps

### Done or implemented

- Core problem framing and Track 1 product scope.
- Synthetic backend and merchant personas.
- Ledger, balance, repayment guardrails, idempotency, stock records, payment review, and timeline events.
- Facts-only merchant brief, deterministic fallback, editable merchant action, mock approval, and outcome window.
- Sarvam transcription endpoint and editable transcript flow.
- Bounded command assist and common voice-ready command intents.
- Payment/activity summary endpoint and Timeline/Home summaries.
- Handoff docs, build log, phase tracker, and browser runbook.

### Current phase: integrated demo readiness

1. Refresh the browser at `http://localhost:8081/` and confirm it still talks to the updated backend on port 8000.
2. Try the new read-only commands first: balance, stock check, payment summary, and timeline summary.
3. Try a customer creation command and confirm only if the exact name is right; verify the resulting customer without posting credit.
4. Try stockout observation and physical count separately; check the quantity before and after each action.
5. Test a voice recording with one short, clear command. Inspect/edit its transcript, then test a read-only query before testing a write.
6. Rehearse the full runbook from a fresh timestamped synthetic database without deleting the existing demo database.
7. Verify Expo Go on a physical phone over LAN if the presentation requires a phone demo.
8. Keep claims explicit: synthetic data, provider fallback, mock payment/action behavior, no Paytm integration, no causal claim.

### Deferred

- Fraud model integration.
- Real Paytm data/API integration, live payment automation, or real offer publishing.
- MongoDB migration, authentication/roles, multi-shop production architecture.
- TTS, offline sync, supplier/procurement workflows, delivery features.
- Business budgeting/forecasting. The implemented “balance” command means a customer's due/udhaar, not the shop's budget.

## 11. Repository map

```text
Munim-AI/
├── README.md
├── backend/
│   ├── app/api/                  # FastAPI routes
│   ├── app/domain/models.py      # Request/response contracts
│   ├── app/services/             # Ledger, inventory, AI, facts, events
│   └── seed_demo.py              # Optional synthetic Raju/Maggi seed
├── mobile/
│   └── src/features/             # Home, insights, inventory, payments, timeline
└── docs/
    ├── PROJECT_BRIEF_AND_CURRENT_STATE.md  # This handoff
    ├── BUILD_LOG.md                       # Dated implementation evidence
    ├── HACKATHON_EXECUTION_PLAN.md         # Phase tracker and exit gates
    ├── BROWSER_DEMO_WALKTHROUGH.md         # Clean synthetic demo steps
    └── contracts/backend-api-v0.md         # API/data contract
```

## 12. Git and handoff workflow

- Current implementation branch: `codex/sarvam-voice-input`.
- Latest recorded push for this snapshot: `f84584b`.
- Make one coherent change at a time; run the relevant type/compile checks; update this build log and the phase tracker when behavior or status changes; commit and push to the feature branch.
- Do not put secrets in commits, screenshots, build logs, or mobile `EXPO_PUBLIC_*` variables.
- Before saying a feature is “done,” distinguish code completion from browser/device acceptance and cite the observed check.

## Appendix A — Key local run commands

Backend (PowerShell, from repository root):

```powershell
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Mobile browser (second terminal, from repository root):

```powershell
cd mobile
npm ci
$env:EXPO_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000"
npm run web
```

Open `http://localhost:8081/`. For a physical phone, use the laptop's reachable LAN IP and run Uvicorn with `--host 0.0.0.0`; phone-to-laptop networking still requires its own check. Use a new timestamped `MUNIM_DB_PATH` for a clean rehearsal rather than deleting the current demo database.
