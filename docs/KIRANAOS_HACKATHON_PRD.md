# KiranaOS / Munim-AI Hackathon PRD

**Version:** 1.0-hackathon · **Prepared:** 29 October 2026 · **Track:** Merchant Growth AI

**Status:** Current two-day product scope. The full KiranaOS PRD supplied by the team is a long-term vision; the 48-hour cut and gates are in [HACKATHON_EXECUTION_PLAN.md](HACKATHON_EXECUTION_PLAN.md).

## Product definition

**Munim-AI** is a voice/text copilot for the shopkeeper. **KiranaOS** is the structured, auditable business memory it uses: customer aliases, credit and repayment ledger entries, stock events, payment events, and a timeline. The LLM helps understand utterances and explain facts; deterministic application code and the database decide what is recorded and what balances mean.

### One-line pitch

> Record udhaar and stock events by voice, keep business balances traceable, and connect incoming payments to shop records only when the evidence supports the match.

## Problem statement

Small retailers track customer credit, repayments, stock observations, and promises across notebooks, memory, conversations, and payment apps. UPI history can show a payment event but cannot reveal the shop's complete credit or stock state, and a payment alone does not prove which debt it settles. Repeated manual entry makes it harder to keep those records connected and accurate.

**How might we help a shopkeeper capture everyday business events in their own language, maintain a reliable record, and take a useful next step without guessing when details are unclear?**

## Track fit and product distinction

This targets **Merchant Growth AI** by helping merchants manage day-to-day operations and act on more complete business context. Paytm already describes merchant analytics and voice-enabled products, so we do not claim “first AI merchant insight.” The prototype's proposed distinction is persistent shop memory for udhaar and stock, traceable payment reconciliation, and explainable actions the merchant approves. It is a hypothesis to demonstrate, not a proven advantage or sales lift.

## Hackathon user and core journey

Primary user: owner/operator of a small kirana, tea stall, or medical store who has limited time for typing and wants to speak or ask simple questions.

1. Merchant says/types “Raju bhai ka ₹50 udhaar likh do.” The app shows a typed proposal and asks for confirmation; backend posts a credit entry; customer balance is derived from ledger entries.
2. A mock payment event arrives. It auto-matches only when a unique stable synthetic payer token and an eligible outstanding balance support the match; otherwise it enters a review queue. Duplicate events do not produce duplicate credits.
3. Merchant says/types “Maggi khatam ho gaya.” The system records a stockout observation and asks for a physical count before changing on-hand stock.
4. Merchant asks “Aaj kaisa raha?” Deterministic calculations create a brief and evidence panel. Munim proposes a shop-side counter notice/offer; the merchant can edit, reject, or approve it. Publishing is mocked and marked as such.
5. A later view compares the selected periods as an observation, not proof that the offer caused a change.

Text is required for a reliable demo; speech is an adapter. Show the transcript before sensitive writes and clarify ambiguity rather than guessing.

## Core requirements

### Business memory

- Shop-scoped synthetic customer records with aliases; names are not unique identifiers.
- Append-only `CREDIT`, `REPAYMENT`, and linked `ADJUSTMENT/REVERSAL` ledger entries; derive balance by summing posted entries.
- Stock observations are separate from physical stock counts and stock movements.
- Payment events have unique source IDs and explicit status; payment allocations retain amount, evidence, and decision status.
- Activity timeline records source utterance/event, related entities, actor/source, and lifecycle status.

### AI and write safety

- LLM returns strict typed proposals only; it never writes to the database.
- Backend validates intent, entities, amount/quantity/unit, confidence, confirmation state, and idempotency before mutation.
- Ambiguous customer, low-confidence amount, unclear intent, or weak payment match causes a clarification/review item and no guessed write.
- Financial values and insights are computed in code. Every number in an LLM explanation must map to the facts JSON; otherwise use deterministic fallback wording.
- Pending or failed operations are never shown as completed.

### Insight and action

- Calculate daily/comparable-window collections from successful synthetic payment events, with explicit period, status mapping, and sample counts.
- Explain the observation using evidence IDs and relevant caveats; do not infer missing causes, footfall, stock, cash sales, customer intent, or total revenue.
- Merchant approval is required; action publishing is a labelled mock. Do not message named customers.
- Outcome views state the exact windows and counts; they do not claim causality.

## Data contracts

Money is integer paise. Example ledger record:

```json
{
  "entry_id": "entry_synth_001",
  "shop_id": "shop_synth_01",
  "customer_id": "customer_raju_01",
  "type": "CREDIT",
  "amount_paise": 5000,
  "source_event_id": "event_synth_001",
  "status": "POSTED",
  "created_at": "2026-10-30T10:15:00+05:30"
}
```

Example typed AI command proposal:

```json
{
  "schema_version": "1.0",
  "command_id": "cmd_synth_001",
  "intent": "create_credit",
  "customer_ref": {"query": "Raju bhai", "customer_id": "customer_raju_01"},
  "amount_paise": 5000,
  "confidence": 0.94,
  "needs_confirmation": true,
  "clarification": null
}
```

Example facts sent to the explainer:

```json
{
  "schema_version": "1.0",
  "shop_id": "shop_synth_01",
  "data_mode": "synthetic",
  "period": {"start": "...", "end": "...", "timezone": "Asia/Kolkata"},
  "facts": [
    {"id": "raju_balance", "value_paise": 25000, "status": "available", "source": "posted_ledger_entries"},
    {"id": "stock_maggi", "value": null, "status": "needs_count_confirmation"}
  ],
  "evidence_ids": ["raju_balance"],
  "caveats": ["Synthetic demo data; not Paytm data."],
  "allowed_actions": ["counter_notice"]
}
```

These are prototype contracts, not Paytm feed schemas. See the execution plan for required fields, payment matching rules, number validation, and idempotency behavior.

## Two-day scope

**P0:** synthetic single-shop workflow for credit, repayment/balance, stockout observation/count confirmation, daily summary, timeline, and approved mocked action. Mock UPI reconciliation uses stable synthetic IDs and a review queue. Text path always works.

**P1/stretch:** Sarvam STT/TTS after confirming current model names, credentials, quotas, and network; additional personas and polished charts.

**P2/last:** optional fraud research panel, only after independent local verification and the core demo. Model outputs are research signals trained on heterogeneous, partly synthetic public data; never Paytm-validated fraud decisions.

**Roadmap only:** supplier calling, automated procurement, deliveries, offline sync, multi-user roles, real payment gateway, real customer messaging, GST/billing, and demand forecasting. Do not present them as built.

## Correct canonical repayment arithmetic

The provided brief's example needs consistent seed values: if Raju starts with ₹500 due, a newly confirmed ₹50 credit brings the balance to ₹550; a unique mock ₹300 repayment then leaves ₹250 due. If the only debt is ₹50, a ₹300 payment must not be fully allocated; an amount beyond debt stays unallocated or in review. This example should be reflected in the seed scenario and demo narration.

## Success criteria for this prototype

- A reviewer can complete the four core journey steps on the demo phone from a clean start.
- Replaying one command/payment event creates only one financial effect.
- Balance is reproducibly derived from posted ledger entries.
- Ambiguous names and weak payment evidence trigger clarification/review.
- A stockout observation does not silently change verified on-hand stock.
- Unsupported facts or numbers from the LLM are rejected; deterministic fallback works.
- Synthetic, mock, pending, failed, and research-only states are visibly and accurately labelled.
- The pitch acknowledges existing Paytm analytics, no live integration, and no causal result claim.

## Known risks and assumptions

- Hackathon brief, judging rubric, data rules, and Sarvam access are team-supplied and need organizer confirmation.
- No real Paytm merchant data/API integration is available in this prototype unless the team independently confirms access.
- Pseudonymous payer IDs may not exist in a real merchant feed; disable person-based churn/reconciliation metrics without them.
- A two-day three-person build cannot credibly deliver the full long-term KiranaOS product. Protect ledger correctness and the core user journey; cut optional integrations first.
- The fraud model is separate from merchant-growth logic and must not be presented as Paytm-specific validation.
