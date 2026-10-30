# Munim-AI Delivery Phases

This is the current phase tracker for the hackathon prototype. Keep the Git workflow continuous: each coherent fix is committed and pushed to the active task branch, and this file plus [`BUILD_LOG.md`](BUILD_LOG.md) records the state for the next person. No real Paytm integration or production data is implied.

## Phase 1 — Merchant command and ledger

**Status: Implemented; voice end-to-end acceptance is still pending.**

- Text and Sarvam voice input enter the bounded deterministic command parser.
- Customer/product aliases are resolved exactly; ambiguity or missing details stops for clarification.
- Credit, repayment, and stockout writes show a preview, require merchant confirmation, and use idempotency keys.
- Balances are derived from append-only ledger entries; repayments cannot exceed outstanding balance.
- Recent voice recordings reached Sarvam successfully. A transcript punctuation bug was fixed, but the local database has no voice-tagged write yet.

**Exit gate:** Speak a read-only balance request, confirm the transcript and customer resolve correctly, then confirm one synthetic credit and verify its amount and source in the timeline/database.

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
- Gemini may explain only supplied facts; invalid or unavailable model output falls back to deterministic copy.
- Mock shop-side actions require approval and are never published. Outcome comparisons remain observational and do not claim causality.
- The current Gemini key returns HTTP 401, so the deterministic path is the active path. MongoDB connectivity is separate; the app uses SQLite.

**Exit gate:** The brief loads with facts and caveats when Gemini is unavailable, a mock action requires confirmation, and the outcome stays scheduled/insufficient when no post-action data exists.

## Phase 5 — Integrated demo readiness

**Status: In progress; this is the current phase.**

1. Complete the Phase 1 voice acceptance gate on the current browser or an Android phone.
2. Rehearse the text command path, stock observation/count, payment review, business brief, and mock action against a clean synthetic database.
3. Verify both services start from the documented setup and the phone can reach the backend over the demo network.
4. Freeze a known-good branch/commit and keep the demo script honest about synthetic data, deterministic fallback, mock publishing, and missing live Paytm integration.

**Completion gate:** The complete scripted journey works from a clean seed without manual database edits, every financial write has a confirmation step, and all claims match observed behavior.

## Deferred after the core demo

- Fraud research signal integration, unless the core demo is stable and its model artifacts are independently checked.
- Live Paytm data, real customer messaging, MongoDB migration, TTS, offline sync, supplier automation, and causal sales-lift claims.

Do not mark a phase complete from code presence alone; use the specific exit gate and record the evidence in [`BUILD_LOG.md`](BUILD_LOG.md).
