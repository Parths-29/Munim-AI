# Munim-AI

**An explainable, voice-first business copilot for small Paytm merchants.**

Munim-AI turns a merchant's payment history into a small number of understandable business signals and a merchant-approved next step. The prototype is designed for the **Merchant Growth AI** track of the Paytm Build for India AI Hackathon, Mumbai Edition.

> **Current status:** Product definition and hackathon prototype plan. This repository was empty when documentation work began. The PRD is the source of truth for scope; code, integration, and live Paytm data access are not yet established by these documents.

## The problem we are solving

Small shop owners receive digital payments and can inspect transaction history, but a list of payments still leaves practical questions unanswered: Was today unusually slow? Which time window changed? Is the average sale shrinking? What is one low-risk thing I can try tomorrow? A chart may show a change without helping a busy merchant understand the evidence or choose an action.

**Problem statement:** Given an authorized merchant's payment history, how might we help a small merchant notice a meaningful change, understand why the system noticed it, and choose a practical next step in their own language—without pretending to know facts the payment data cannot show?

Munim-AI is not a payment processor, credit decision system, or fraud-blocking product. It is a prototype business copilot. It does not claim access to Paytm systems or real merchant data.

## What the hackathon asks builders to explore

The event brief supplied by our team describes three tracks:

1. **Merchant Growth AI:** AI business partners that help Paytm merchants grow, manage operations, and serve customers.
2. **AI-Powered Financial Journeys:** simpler and more human customer journeys in insurance, lending, and fintech.
3. **Autonomous AI Teammates:** agents that understand context, decide, take actions, and work with human teams in sales or customer service.

Munim-AI is scoped to **Track 1**. It may demonstrate a human-approved action, but we are not changing tracks or claiming autonomous financial actions. See [the PRD](docs/PRD.md) for track fit, scope, evidence, architecture, safety limits, and the build plan.

## The core demo loop

1. The merchant asks “How was business?” or opens a morning brief.
2. Deterministic Python analytics compare a chosen period with a comparable prior period.
3. The assistant explains only computed facts and shows a “Why am I seeing this?” panel.
4. The merchant reviews and approves a shop-side action, such as a counter notice or QR-linked offer. Publishing is labelled as a mock in the hackathon prototype.
5. The dashboard compares sales during the offer window with a prior comparable window. It describes an observed comparison, not proof that the offer caused a change.

The LLM is an explanation and language layer; it is not the source of transaction metrics. A validator checks every displayed numerical claim against the analytics facts. Low-confidence voice input must be confirmed rather than silently saved.

## What we have

- A locked product concept and a three-person team: Parth (LLM, voice, guardrails), Priyanshu (data generation, analytics, optional anomaly-model integration), and Rachit (UI, deck, demo).
- A ZIP called `munim_inference_bundle.zip` supplied separately from this repository. It contains a FastAPI inference service and model artifacts for a single-transaction hybrid fraud/anomaly research score. It has not yet been independently run from this repository.
- A README for the original UPI fraud project describing a multi-source dataset and offline research pipeline. The dataset is heterogeneous and includes synthetic mobile-money data; its metrics are not Paytm-specific validation.
- A hackathon event brief supplied in the conversation. Exact API access, judging rubric, Sarvam API credentials/model, and official event rules still need confirmation from organizer materials.

The model ZIP is not committed here. Do not put credentials, real payment exports, or personally identifying data into the repository. See the PRD for how the research model may be presented honestly.

## Planned prototype

- A clearly labelled synthetic dataset for three merchant personas: kirana, tea stall, and medical store.
- A deterministic analytics engine for revenue change, hourly patterns, average-ticket drift, recorded payment failures, and lapsed repeat-payer counts only when stable pseudonymous payer IDs exist.
- A voice/text question flow, with a text fallback if speech services are unavailable.
- Structured LLM output grounded in analytics facts, with validation and source evidence.
- A human-approved, mocked shop-side offer and a careful before/after comparison.
- Optional research-risk panel based on the existing fraud model, only if it can be integrated and demonstrated reliably. It is not part of the core acceptance criteria.

## Build status and next steps

1. Confirm the repository collaborators can access the project and agree to the PRD scope.
2. Implement a reproducible synthetic data generator and define the transaction schema.
3. Implement and validate deterministic analytics before adding an LLM.
4. Build the merchant-facing dashboard and evidence panel.
5. Add the grounded explanation and voice path, keeping text input as a fallback.
6. Add the mocked approval/action and outcome-comparison flow.
7. Integrate the fraud model only after a clean run and a clear explanation of its research limitations.
8. Rehearse a short end-to-end demo with one planted scenario and an honest limitations slide.

For detail, open [docs/PRD.md](docs/PRD.md) and [docs/BUILD_PLAN.md](docs/BUILD_PLAN.md).

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
