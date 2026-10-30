# Munim-AI Delivery Phases

This is the current phase tracker for the hackathon prototype. Keep the Git workflow continuous: each coherent fix is committed and pushed to the active task branch, and this file plus [`BUILD_LOG.md`](BUILD_LOG.md) records the state for the next person. No real Paytm integration or production data is implied.

## Phase 1 — Merchant command and ledger

**Status: Core text flow implemented; browser command NLP assist added with deterministic fallback. Voice capture/transcription tuning remains deferred.**

- Text and Sarvam voice input enter the bounded deterministic command parser.
- If the parser cannot classify a command, the browser may ask Gemini to return exact quoted entity/amount spans using synthetic English/Hinglish examples; the app validates those spans and re-runs its deterministic parser before preview. This is prompt guidance, not model training. The updated local key is present, but the latest Gemini request returned HTTP 503 and the deterministic fallback remains active.
- Customer/product aliases are resolved exactly; ambiguity or missing details stops for clarification.
- Credit, repayment, and stockout writes show a preview, require merchant confirmation, and use idempotency keys.
- Balances are derived from append-only ledger entries; repayments cannot exceed outstanding balance.
- A read-only voice request transcribed, resolved the exact `Raju bhai` alias, and fetched the balance. A later voice-originated ₹10 credit was also recorded. Because spoken number recognition is inconsistent, treat voice as optional and use typed commands for reliable financial entry; do not keep expanding voice capture/transcription now. A transcript may use the same command NLP assist as typed browser input.

**Exit gate:** Typed commands support the reliable financial path with preview and confirmation. Basic voice plumbing and one voice write were observed, but recognition fidelity is not a Phase 5 blocker; typed input remains the fallback.

## Phase 2 — Shop memory: inventory and timeline

**Status: Implemented.**

- Stockout observations remain separate from physical counts.
- On-hand stock changes only after a confirmed physical count.
- The append-only timeline captures customer, ledger, stock, payment, and action events with source metadata.

**Exit gate:** A stockout report leaves quantity unchanged; a confirmed count changes it by the calculated delta and appears in the timeline.

## Phase 3 — Mock payment reconciliation

**Status: Implemented for synthetic events.**

- Mock payment intake is idempotent by event ID and idempotency key.
- Automatic allocation requires a successful payment, an exact merchant-confirmed synthetic payer-token mapping, positive debt, and an amount no greater than that debt.
- Unmatched, ambiguous, excess, or non-successful payments stay in review or ignored states; a merchant must confirm manual allocation.

**Exit gate:** Replaying an event creates one effect; an unmatched event remains in review; a confirmed eligible allocation posts one repayment and updates the derived balance.

## Phase 4 — Merchant growth brief and approved action

**Status: Implemented with deterministic fallback.**

- Business facts are computed from the synthetic payment fixture and include evidence, windows, and caveats.
- Gemini may explain only supplied facts; invalid or unavailable model output falls back to deterministic copy. The proposed merchant-side counter notice is editable before approval, and the saved text is displayed with an explicit mock/not-published label.
- Mock shop-side actions require approval and are never published. Outcome comparisons remain observational and do not claim causality.
- The current Gemini request returned HTTP 503, so the deterministic path is the active path until provider access succeeds. MongoDB connectivity is separate; the app uses SQLite.

**Exit gate:** The brief loads with facts and caveats when Gemini is unavailable, a mock action requires confirmation, and the outcome stays scheduled/insufficient when no post-action data exists.

## Phase 5 — Integrated demo readiness

**Status: In progress; this is the current phase.**

1. **Passed (service-level):** Created a clean Phase 5 synthetic database with Raju opening due ₹500 and Maggi stock 12; preserved the previous preview database separately.
2. **Passed (isolated logic rehearsal):** Confirmed ₹50 credit, ₹300 unmatched payment review and merchant-confirmed allocation, ending balance ₹250; stockout did not change stock before count; confirmed count set stock to 10; five facts, deterministic explanation, and scheduled mock action all worked.
3. **Passed (browser-backed payment review):** A successful synthetic ₹300 event was merchant-confirmed and allocated; the review queue is empty, the derived Raju due is ₹250, and the timeline records the repayment. An earlier over-balance attempt was rejected without a ledger write.
4. **Browser inventory count passed; stockout observation not separately exercised:** The user confirmed Maggi's physical count of 0 is intentional; current on-hand is 0. No stockout-observation event is present, so that separate action has not been verified in the browser.
5. **Passed (browser growth brief and mock action):** Five synthetic facts and a four-evidence deterministic explanation load in about 8 seconds. The merchant-approved action text is `Ask us about this week's in-store offers. UPI accepted.` Backend status is `APPROVED_MOCK`, `mock_only=true`, outcome `scheduled`, with a seven-day measurement window. Nothing was published.
6. **Remaining (environment/demo):** Verify both services start from documented setup, check phone-to-laptop network access, and rehearse the complete scripted journey from a clean synthetic seed. The repeatable walkthrough is in [`BROWSER_DEMO_WALKTHROUGH.md`](BROWSER_DEMO_WALKTHROUGH.md).
7. Freeze a known-good branch/commit and keep the demo script honest about synthetic data, deterministic fallback, mock publishing, and missing live Paytm integration.

**Completion gate:** The complete scripted journey works from a clean seed without manual database edits, every financial write has a confirmation step, and all claims match observed behavior.

## Deferred after the core demo

- Fraud research signal integration, unless the core demo is stable and its model artifacts are independently checked.
- Live Paytm data, real customer messaging, MongoDB migration, TTS, offline sync, supplier automation, and causal sales-lift claims.

Do not mark a phase complete from code presence alone; use the specific exit gate and record the evidence in [`BUILD_LOG.md`](BUILD_LOG.md).
