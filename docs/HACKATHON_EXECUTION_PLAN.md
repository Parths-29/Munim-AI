# Munim-AI / KiranaOS: 48-Hour Execution Plan

**Prepared:** 29 October 2026 · **Team:** Parth, Priyanshu, Rachit · **Track:** Merchant Growth AI

**Purpose:** Convert the KiranaOS product vision into a realistic, reviewable hackathon build. This is a planning document; application implementation starts only after the team agrees to the scope.

## 1. What we are building

**Munim-AI** is the voice/text business copilot. **KiranaOS** is its structured business memory: customer records and aliases, an append-only credit ledger, stock movements, payment records, and an activity timeline.

The product problem is that a small shop's business facts live across a paper bahi-khata, memory, conversations, stock checks, and payment history. A payment app can show a payment, but payment history alone does not tell us the shop's udhaar balance or stock on hand, nor does it prove which debt a payment repays. Munim captures the missing merchant-entered events and relates records only when there is enough evidence.

### Better one-line pitch

> Munim-AI helps a shopkeeper record udhaar and stock by voice, keep balances traceable, and connect incoming payments to shop records only when the evidence supports the match.

Avoid “Paytm knows money moved; we know why it moved.” It overstates what the product knows. A safer framing is: **payment history shows recorded money movement; Munim adds the shop's own credit and stock records, then explains what those records support.**

### Track fit and proposed USP

Track 1 asks for an AI business partner to help merchants grow and run operations. This project fits through reliable daily operations and actionable business context. Paytm already describes merchant analytics and voice products, so the claim is not “first AI insights.” The proposed difference to demonstrate is:

1. Persistent, structured shop memory for udhaar and stock events that payment history does not contain.
2. Traceable balances computed from an append-only ledger.
3. Payment-to-debt reconciliation that auto-matches only with evidence and otherwise asks the merchant.
4. A concise insight-to-action flow with an evidence explanation and explicit merchant approval.

These are prototype differentiators to demonstrate, not claims of exclusive market capability or proven business outcomes.

## 2. Hard scope for two days

### Must demo end to end (P0)

1. **Credit entry:** “Raju bhai ka ₹50 udhaar likh do.” Show a parsed proposal, let the merchant confirm, append a credit event, and show the derived balance.
2. **Repayment/balance:** record a repayment or a mocked incoming UPI event, show the allocation decision, and calculate the new balance from ledger entries.
3. **Stockout:** “Maggi khatam ho gaya.” Record it as an observation. Ask for a counted quantity before changing on-hand stock; do not treat “running low” as a verified count.
4. **Business brief:** “Aaj kaisa raha?” Compute a small, deterministic daily/comparable-period summary, show the underlying facts, then offer one editable mock counter notice/offer for merchant approval.
5. **Activity timeline:** show source utterance/event, actor/source, status (proposed, confirmed, posted, needs review, failed), and related record.

Text input is a release requirement. Sarvam speech-to-text/text-to-speech is an adapter and a stretch feature until actual credentials, model names, limits, and venue network are confirmed. Use one synthetic shop in the hackathon build; three synthetic merchant personas can be available as demo fixtures if they do not slow the core path.

### Cut or simplify first

- Fraud/anomaly panel: last optional feature; only after a clean local run of the ZIP and the whole P0 demo.
- Supplier calls, automatic purchasing, procurement, delivery tracking, offline sync, multi-user roles, GST/billing, demand forecasting, real payment gateways, real customer messaging: roadmap only.
- For 48 hours, choose a single database/runtime already familiar to the team. Do not build a general agent platform or production-grade authentication system.

The attached KiranaOS PRD is a long-term product vision, not a two-day backlog. Its first-release/production requirements (auth, tenant isolation, offline behavior, procurement, production security, broad integrations) cannot all be delivered credibly in this hackathon window.

## 3. Required data and command contracts

Agree these contracts in Phase 1 before parallel implementation. Keep them small and versioned.

### 3.1 Core records

| Record | Minimum fields | Integrity rule |
|---|---|---|
| Customer | `customer_id`, shop-scoped `display_name`, aliases, optional synthetic `payer_token` | Names/aliases are not unique IDs; ambiguous resolution asks. |
| Ledger entry | `entry_id`, `shop_id`, `customer_id`, `type`, `amount_paise`, `created_at`, `source_event_id`, `status`, optional `reverses_entry_id` | Posted credit/repayment entries are append-only; corrections are linked adjustment/reversal entries. Balance is derived, not stored as an LLM-generated number. |
| Product / stock movement | `product_id`, name/aliases, unit; movement `movement_id`, quantity delta, reason, event/source ID, status | A stockout observation is not an inventory count. Record count adjustments separately. |
| Payment event | `provider_event_id`, amount, timestamp, payer token/reference if available, status, source=`mock` | Unique provider/event ID makes webhook retries idempotent. Receipt is separate from settlement. |
| Payment allocation | `allocation_id`, payment event, ledger entry, amount, match evidence, decision status | A payment can only be allocated up to the outstanding debt; remainder goes to review/unallocated. |
| Business event | `event_id`, type, source utterance, actor/source, related IDs, lifecycle status, timestamps | Timeline is append-only enough to explain proposals, confirmations, postings, failures, and corrections. |

Use integer paise for money. Keep synthetic IDs and a visible synthetic-data banner. Do not place phone numbers, VPA, names, or raw transcripts in the LLM explanation context unless strictly required; in this demo use only synthetic values.

### 3.2 Typed command contract

The LLM returns a proposal, never a database write. A narrow command shape can be:

```json
{
  "schema_version": "1.0",
  "command_id": "cmd_synth_0001",
  "intent": "create_credit",
  "customer_ref": {"query": "Raju bhai", "customer_id": null},
  "amount_paise": 5000,
  "product_ref": null,
  "quantity": null,
  "unit": null,
  "confidence": 0.94,
  "needs_confirmation": true,
  "clarification": null
}
```

Supported intents for the demo: `create_credit`, `record_repayment`, `get_customer_balance`, `report_stockout`, `adjust_stock`, `get_daily_summary`. Validate each intent with a typed schema: required fields, positive amounts, supported units, known customer/product resolution, confidence policy, and confirmation requirements. For an unknown/ambiguous customer, low confidence, or unclear amount, return a clarification proposal and make no mutation.

Use an idempotency key for each accepted command. Replaying the same command or mock payment event must not create a second ledger entry or stock movement.

### 3.3 Facts JSON for the reader/explainer

Analytics and database queries produce facts first; the LLM only converts those facts into language. Suggested contract:

```json
{
  "schema_version": "1.0",
  "shop_id": "synthetic_shop_01",
  "data_mode": "synthetic",
  "period": {"start": "...", "end": "...", "timezone": "Asia/Kolkata"},
  "facts": [
    {"id": "collections_today", "value_paise": 842500, "unit": "INR_paise", "count": 42, "status": "available"},
    {"id": "customer_balance_raju", "value_paise": 25000, "unit": "INR_paise", "status": "available", "source": "posted_ledger_entries"},
    {"id": "maggi_stock", "value": null, "unit": "pack", "status": "needs_count_confirmation"}
  ],
  "evidence_ids": ["collections_today", "customer_balance_raju"],
  "caveats": ["Synthetic demo data; not Paytm data."],
  "allowed_actions": ["counter_notice"]
}
```

No LLM-calculated totals. The UI should render money from the numeric facts itself. Validator requirements: strict JSON schema; evidence IDs must exist; every numeric value must match a fact or a deterministic formatting of one; reject invented reasons/identities/causal claims; use deterministic fallback text when validation/provider fails.

### 3.4 Payment match policy and canonical-seed correction

**The brief's canonical numbers need fixing:** a new ₹50 credit followed by a ₹300 payment cannot be auto-matched as if the ₹300 fully settles that ₹50 debt. Seed Raju with an existing ₹500 balance, then add ₹50 credit (balance ₹550), then mock a ₹300 payment linked to Raju, leaving ₹250 due. Or seed only ₹50 debt and send a ₹30 repayment. Never allocate above the outstanding amount; any excess remains unallocated for review.

For a high-confidence demo auto-match, require a stable synthetic payer token mapped to exactly one customer, a unique payment event ID, successful/settled mock status as defined, and a positive outstanding balance. If identity is ambiguous, payment is duplicated, or match amount exceeds the eligible outstanding amount, enqueue for review (or allocate only a clearly supported partial amount and leave excess unallocated). A UPI payment proves money moved; it does not alone prove which debt it repays.

## 4. Five phases over 48 hours

Treat hours as relative to team kickoff; shift the blocks to the event schedule. Deliver a working vertical slice by the end of the first build day. Keep 2–3 hours at the end for rehearsal and recovery.

| Phase | Timebox | Goal / exit gate | Parallel owners | Git checkpoint |
|---|---:|---|---|---|
| 1. Align contracts and scaffold | H0–H3 | Scope frozen; repo folders, run instructions, schemas, example events/facts, and demo scenario agreed. | Parth: command/facts schemas and provider adapter contract. Priyanshu: DB/domain schema and seed format. Rachit: mobile screen map and API mock contract. All review one another. | Merge one small `docs/contracts` PR first. Then each owner opens a scaffold/contract PR only for their owned paths. |
| 2. Build trustworthy memory | H3–H10 | Credit, repayment, derived balance, stockout observation/count, event timeline, and idempotent writes work with text/mock commands. | Priyanshu owns DB + typed FastAPI service. Parth builds parser stub returning typed proposals/clarifications. Rachit builds Expo UI against mock API. | Separate `feat/ledger-api`, `feat/command-proposals`, `feat/mobile-memory-ui` PRs. Backend contract PR merges before integration. |
| 3. Complete the Day-1 vertical slice | H10–H20 | On one phone, record credit → confirm → see balance; query balance; report stockout → confirm count; see timeline. Text path works if voice is down. | Parth adds structured extraction, confidence/clarification, Sarvam adapter if available. Priyanshu adds validation, ledger rules, idempotency. Rachit connects UI and visible statuses. | Small PRs: `feat/command-confirmation`, `feat/ledger-timeline`, `feat/mobile-core-flow`; merge after a paired end-to-end review. **Day-1 gate:** record a 60–90 second demo without manual DB edits. |
| 4. Add payment reconciliation and growth insight | H20–H34 | Mock payment can auto-match only under policy or enter review; “how was business?” uses computed facts, evidence panel, approved mock action, neutral outcome comparison. | Priyanshu: payment event, allocation/review queue, deterministic analytics. Parth: reader/explanation validator and voice response. Rachit: reconciliation, evidence, action/outcome screens. | PRs `feat/mock-payment-reconciliation`, `feat/grounded-business-brief`, `feat/approved-mock-action`; integration PR links the canonical demo. |
| 5. Stabilize, rehearse, present | H34–H48 | Clean install/start, canonical flows work on presentation phone, failures have fallbacks, deck and honest limitations ready. | All: fix only demo-blocking defects. Rachit owns rehearsal/deck; Priyanshu validates seeded numbers and replay/idempotency; Parth checks language, output validation, and offline/text fallback. | `fix/demo-blockers` PRs only; final `docs/demo-script` PR. Freeze features before presentation; cut fraud signal first. |

### Day-1 vertical slice definition

At the end of Phase 3, the user can type a credit command, see a structured interpretation, confirm it, and see the derived balance and timeline update. The shopout utterance is recorded as an observation and does not falsely change inventory before a count is confirmed. This is more valuable than half-built speech, procurement, or fraud features.

### Feasibility call

The full KiranaOS PRD cannot be delivered in two days. Even the narrower A–G scope in the lead brief is aggressive for three students starting from an empty app repository. The phase plan makes the smallest credible operational-memory journey P0 and the insight/action loop P0 for Track 1; it keeps supplier, delivery, offline sync, multi-user, procurement, production auth, and fraud scoring out. If schedule slips, cut order is: fraud, advanced voice polish, extra personas, failure-rate metric, outcome visualization complexity. Do not cut ledger correctness, confirmation, idempotency, or honest labels.

## 5. Team Git and pull-request workflow

The GitHub repository currently contains planning documentation and no application scaffold. It is public, but public visibility does not grant teammates permission to push. The repository owner must add all three teammates as collaborators with write access before parallel work begins.

### Branch model

- `main` is the shared, demoable branch. No direct pushes; every change arrives through a PR.
- Do not create a long-lived `develop` branch for this 48-hour build. Merge small, working feature branches into `main` frequently.
- Branch from the latest `main`; keep each branch to one task and owned paths. Example names: `feat/ledger-api`, `feat/mobile-core-flow`, `feat/command-confirmation`, `feat/mock-payment-reconciliation`, `docs/demo-script`.
- Use conventional commit subjects such as `feat(ledger): derive customer balance from entries`, `fix(recon): leave excess payment unallocated`, `docs(plan): clarify canonical repayment scenario`.
- Never commit `.env`, API keys, customer data, raw audio, or real transaction exports. Put secrets in local environment variables and commit only `.env.example` with placeholder names.

### How parallel work avoids collisions

1. Phase 1 merges the API/data contracts first. Contract changes after that require a small coordinated PR.
2. Agree folder ownership: Priyanshu owns `backend/` and seed-data generation; Parth owns `backend/app/ai/` or a separate voice/extraction module and the validator; Rachit owns `mobile/` and demo assets. Keep shared files (API schemas, root config, README) behind explicit coordination.
3. UI can start against a checked-in mock response while backend work proceeds. Replace the mock only after the endpoint contract is merged.
4. Keep PRs narrow (one feature, typically reviewable in minutes). Do not let multiple branches rewrite the same large file.
5. Rebase/merge latest `main` into the branch before opening the PR; resolve conflicts with the file owner, not by force-pushing over another person's work.

### PR required for every phase task

Every contributor uses this loop:

1. Pick or create a GitHub Issue with a user-visible outcome and acceptance criteria.
2. Create a feature branch from current `main` and assign one owner.
3. Commit in small steps; push the branch.
4. Open a PR to `main`, link the Issue, list changed behavior, show a screenshot/short recording for UI, provide verification evidence, and list known limits.
5. Request one teammate review. Data/ledger/payment changes require review by someone other than the author who checks invariants and duplicate-retry behavior.
6. Fix comments, get approval, and merge with squash merge. Delete the branch after merge.
7. Pull latest `main` before the next task and run the short end-to-end smoke path on the integrated app.

PR body template is in [`.github/pull_request_template.md`](../.github/pull_request_template.md). Every phase row above is a checkpoint; do not wait until Phase 5 to integrate. If GitHub Actions are configured, require formatting/type checks and focused tests before merge. For the hackathon itself, attach manual verification notes and keep the critical flows testable on the demo phone.

### PR review checklist

- Does the backend, not the LLM, enforce the command schema and permissions?
- Are money/quantity units explicit and validated?
- Can retries create duplicate entries or movements?
- Are posted ledger facts immutable, with corrections linked?
- Is a stockout observation distinct from verified stock count?
- Is payment match evidence visible, and does ambiguous/excess amount go to review?
- Do facts and numbers shown in the explanation come from code/data?
- Are pending/failed/mock/synthetic states labelled accurately?
- Does the UI have a text path if voice/network fails?
- Does the PR include reproducible steps and note any scope it deliberately leaves out?

## 6. Demo flow and expected arithmetic

Seed a synthetic customer Raju with ₹500 opening credit (posted ledger entry). Then:

1. Say/type “Raju bhai ka ₹50 udhaar likh do.” System proposes `create_credit`; merchant confirms; balance becomes ₹550.
2. Emit a unique mock successful payment of ₹300 with Raju's synthetic payer token. If the token resolves uniquely and no duplicate event exists, allocate ₹300 to the eligible balance; balance becomes ₹250. Replay the same event ID and confirm no second allocation. If evidence is ambiguous, show review queue instead.
3. Say/type “Maggi khatam ho gaya.” Record `stockout_observed`; ask for counted remaining stock. Only a confirmed count changes on-hand inventory.
4. Say/type “Aaj kaisa raha?” Show synthetic collections/payment facts, comparison window, counts, and caveat; propose a counter notice; merchant edits/approves; state “Mock only — not published.” Show the later window comparison as an observation.

If using a different seed, put the exact expected balances in `scenario_manifest.json` and rehearse against those values. Do not hide arithmetic inconsistencies behind LLM narration.

## 7. Verification plan (for implementation)

These are planned checks, not tests run in this documentation-only update:

- **Ledger arithmetic:** credit increases amount due; repayment reduces it; correction is a linked adjustment; balance equals sum of posted signed entries.
- **Idempotency:** same `command_id` or payment event ID replayed twice produces one effect; distinct IDs are not accidentally collapsed.
- **Overpayment:** payment > eligible outstanding does not create negative debt or over-allocate; excess remains review/unallocated.
- **Entity ambiguity:** two “Raju” matches trigger clarification and produce no write.
- **Stock semantics:** stockout observation alone does not mutate physical count; confirmed count/adjustment records a movement.
- **Number validator:** valid facts render; fabricated number, unsupported evidence ID, wrong currency/period, or causal assertion is rejected and falls back.
- **Lifecycle:** pending or failed command/payment/action is never rendered as completed.
- **Canonical demo:** run all four steps using the presentation phone and synthetic data from a clean startup.

## 8. Risks and open questions

| Item | Why it matters | Plan |
|---|---|---|
| No Paytm integration/data access is confirmed. | Avoid implying this is connected to production payment records. | Synthetic transactions and provider-neutral mocked events, with visible labels. |
| Paytm already offers voice and merchant analytics. | Generic voice insights are not a credible unique claim. | Lead with memory/ledger/reconciliation and explain evidence/approval; verify any competitive claims. |
| Payment identity may not map to a named customer. | False debt settlement is harmful. | Synthetic mapping for demo; stable, permitted token + unique match only; otherwise review. |
| ₹300 payment vs ₹50 new credit inconsistency. | Demo would over-settle the debt. | Use ₹500 opening + ₹50 credit + ₹300 payment = ₹250 balance, or change repayment to ₹30. |
| KiranaOS vision far exceeds event time. | Builds fragmented screens without trustworthy core. | Use P0/P1/P2 cut list and feature freeze. |
| Sarvam credentials/model/quotas/latency unknown. | Voice dependency can fail. | Verify from official docs/team access; provider adapter plus text/prerecorded fallback. |
| SQLite concurrency or event retries can corrupt balances. | Financial state must remain correct. | Atomic DB writes, unique IDs, append-only entries, derive balances; avoid concurrent multi-writer complexity in demo. |
| Fraud inference bundle unverified and domain-shifted. | Its risk outputs may be misleading. | Optional last; run separately on synthetic data; disclose mixed public/synthetic training. |
| Demo comparison can imply causation. | Sales can change for many reasons. | Label as before/after observation, not lift caused by offer. |

### Questions the team must settle in Phase 1

1. Who has owner/admin rights on the GitHub repo, and are Parth, Priyanshu, and Rachit all write collaborators?
2. Which local environment can build and run Expo on the actual Android demo phone? Who owns the phone and hotspot?
3. Are Sarvam credentials and allowed model endpoints available now? What is the fallback if not?
4. Which LLM provider/credits are actually available, or should canonical utterances use a deterministic parser for the demo?
5. Does the team accept the corrected Raju seed arithmetic and a review queue for ambiguous payments?
6. What official hackathon rules/data-use requirements and judging rubric were supplied by organizers?

## 9. What to say to judges

- “This demo uses synthetic data; it is not connected to Paytm.”
- “Paytm already provides merchant analytics and voice-enabled products. We are demonstrating how a merchant-owned memory layer can record udhaar and stock events and relate them to payment events cautiously.”
- “The balance is derived from posted ledger entries. The LLM proposes typed commands and explains computed facts; backend validation and the merchant confirmation control writes.”
- “A payment is not automatically assumed to repay a debt. Strong synthetic match evidence can be auto-allocated; ambiguous cases go to review.”
- “The offer is mocked, and our before/after view is a comparison, not proof of causation.”
