# Munim-AI

**A voice-first shop copilot with a reliable business memory for small Indian retailers.**

**Munim-AI** is the merchant-facing copilot; **KiranaOS** is the structured memory layer behind it. The hackathon prototype focuses on recording customer credit (udhaar), stock events, and payment events safely, then answering questions and suggesting actions the shopkeeper approves. It targets the **Merchant Growth AI** track of the Paytm Build for India AI Hackathon, Mumbai Edition.

> **Current status:** A working synthetic-data prototype with ledger, inventory, payment review, business insights, mock merchant-approved actions, and browser command flow. Phase 5 browser/demo acceptance is in progress. Gemini currently falls back after provider errors/timeouts; no live Paytm integration is claimed.

## The problem we are solving

Shop information is split across notebooks, memory, conversations, inventory checks, and payment apps. UPI history can show that money arrived; it cannot by itself tell the shop's credit balance, stock on hand, or which debt a payment should settle. Manually keeping those records connected takes effort and mistakes can affect real balances.

**Problem statement:** How might we help a small shopkeeper speak everyday business events into a reliable, searchable record, safely connect payments to shop records when evidence is strong, and understand what needs attention—without guessing when the information is ambiguous?

Munim-AI is not a payment processor, credit decision system, or fraud-blocking product. The hackathon demo uses synthetic data and mocked payment events; it does not claim access to Paytm systems or real merchant data.

## What the hackathon asks builders to explore

The event brief supplied by our team describes three tracks:

1. **Merchant Growth AI:** AI business partners that help Paytm merchants grow, manage operations, and serve customers.
2. **AI-Powered Financial Journeys:** simpler and more human customer journeys in insurance, lending, and fintech.
3. **Autonomous AI Teammates:** agents that understand context, decide, take actions, and work with human teams in sales or customer service.

Munim-AI is scoped to **Track 1**. Its proposed distinction is structured shop memory for udhaar and stock, cautious payment-to-ledger reconciliation, and evidence-linked actions approved by the merchant. Paytm already offers merchant analytics and voice-enabled products; we do not claim to be first. See the current [hackathon PRD](docs/KIRANAOS_HACKATHON_PRD.md) and [continuous team workflow](docs/CONTINUOUS_COLLABORATION.md).

## The core demo loop

1. The merchant asks a question or speaks a business event, such as “Raju bhai ka ₹50 udhaar likh do.”
2. AI returns a typed proposal; the backend checks it and asks for confirmation when needed.
3. Validated events are appended to the ledger or stock history. Balances are computed from entries, not invented by the LLM.
4. A mocked UPI event is linked to a debt only when evidence is strong; otherwise it goes to a review queue.
5. For “How was business?”, deterministic analytics create facts; the assistant explains them with evidence and proposes an editable, merchant-approved shop-side action.
6. A later comparison shows what happened during the action window, without claiming the action caused the result.

The LLM does not write to the database directly or calculate financial values. Ledger entries are append-only; corrections are linked adjustments. Ambiguous names, amounts, or payment matches trigger clarification or human review. Pending and failed actions remain visibly pending or failed.

## What we have

- A product concept and a three-person team: Parth (LLM, voice, guardrails), Priyanshu (data generation, analytics, optional anomaly-model integration), and Rachit (mobile UI, deck, demo).
- A ZIP called `munim_inference_bundle.zip` supplied separately from this repository. It contains a FastAPI inference service and model artifacts for a single-transaction hybrid fraud/anomaly research score. It has not yet been independently run from this repository.
- A README for the original UPI fraud project describing a multi-source dataset and offline research pipeline. The dataset is heterogeneous and includes synthetic mobile-money data; its metrics are not Paytm-specific validation.
- A hackathon event brief supplied in the conversation. Exact API access, judging rubric, Sarvam API credentials/model, and official event rules still need confirmation from organizer materials.

The model ZIP is not committed here. Do not put credentials, real payment exports, or personally identifying data into the repository. See the PRD for how the research model may be presented honestly.

## Hackathon prototype scope

- Voice/text commands for credit, repayment, customer balance, stockout observation, stock adjustment, and daily summary.
- A structured, append-only business event history with source utterance and action status.
- Synthetic data for kirana, tea stall, and medical store personas.
- A mocked UPI event with safe reconciliation and an unmatched-payment review path.
- A grounded business insight, evidence panel, and merchant-approved mocked shop-side action.
- Optional research-risk panel from the existing fraud model only after the core flow works and the bundle is verified.

The larger KiranaOS product vision includes delivery, supplier workflows, offline sync, roles, and procurement. Those are roadmap items, not two-day build commitments. The current ownership and continuous build workflow are in [docs/CONTINUOUS_COLLABORATION.md](docs/CONTINUOUS_COLLABORATION.md).

## Build status and next steps

The current phase is integrated demo readiness. The browser payment-review journey is verified: a successful synthetic ₹300 payment was manually allocated after merchant confirmation, the review queue cleared, and Raju's derived due ended at ₹250. The user intentionally counted Maggi at zero; a separate stockout observation has not been recorded in this run. The synthetic facts brief loads with deterministic fallback, and the mock action text is editable, but merchant approval remains pending. Phone-to-laptop networking and the complete clean-seed rehearsal remain.

Gemini is configured in the local ignored `.env`, but recent upstream requests returned HTTP 503 or timed out; deterministic explanations and command clarification remain available. Continue voice recognition work only after the core browser path is stable. Integrate the fraud model only after a clean run and a clear explanation of its research limitations.

For current product requirements, open [docs/KIRANAOS_HACKATHON_PRD.md](docs/KIRANAOS_HACKATHON_PRD.md). For continuously coordinated work, branch ownership, and the Git/PR loop, open [docs/CONTINUOUS_COLLABORATION.md](docs/CONTINUOUS_COLLABORATION.md). [docs/PRD.md](docs/PRD.md), [docs/BUILD_PLAN.md](docs/BUILD_PLAN.md), and [docs/HACKATHON_EXECUTION_PLAN.md](docs/HACKATHON_EXECUTION_PLAN.md) preserve earlier iterations and are not the current workflow.

## Evidence and references

- The track descriptions above are paraphrased from the event brief supplied by the team; they are not independently verified event rules.
- Paytm's merchant analytics support page says its analytics include new/repeat/churn trends, retention cohorts, RFM, payment failure reasons, and recommendations: [Paytm for Business: Analytical tab](https://business.paytm.com/support/what-is-the-use-of-analytical-tab).
- Paytm describes business dashboards with transaction monitoring, settlements/refunds, analytics, and report management: [Paytm merchant dashboard support](https://business.paytm.com/support/what-is-the-use-of-merchant-dashboard-).
- Paytm describes payment analytics for online merchants, including payment-flow success rates, customer retention, churn, RFM, and failure reasons: [Paytm Payment Analytics](https://business.paytm.com/payment-analytics).
- Paytm's business site describes QR, Soundbox, payments, invoices, insights, loans, insurance, and growth products: [Paytm for Business](https://business.paytm.com/).

These sources mean we must not claim “Paytm has no merchant analytics.” Munim-AI's prototype distinction is a voice-first, evidence-linked explanation and human-controlled next step for a small shop, with transparent limits—not exclusive access to insights or a proven lift in sales.

## Team

Team Code Apex: Parth, Priyanshu, and Rachit.

## License

No license has been selected for this repository yet. Do not assume this prototype or model bundle may be reused commercially until the team chooses a license and verifies the source datasets and model-artifact terms.
