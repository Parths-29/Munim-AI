# Munim-AI Product Requirements Document (Hackathon Prototype)

**Version:** 0.1 · **Prepared:** 29 October 2026 · **Team:** Code Apex · **Target track:** Merchant Growth AI  
**Status:** Scope baseline for a two-day build. This PRD records a proposed prototype; it does not assert that code, live integrations, or production validation already exist.

## 1. Executive summary

Munim-AI is a voice-first business copilot that helps a small merchant interpret payment activity and choose a practical, low-risk shop-side action. It turns an authorized transaction history into deterministic, time-bounded facts, explains those facts in simple language, and asks the merchant before presenting an action as approved. The hackathon demo uses synthetic data and a mocked publishing step.

The product is intended to address the gap between **having payment records** and **knowing what to do next**. It must not imply that payment history reveals cash sales, inventory, customer intent, or why a customer did not buy. It must clearly separate observed facts, calculated comparisons, model-generated wording, and merchant-entered information.

## 2. Hackathon context and track fit

The team-provided hackathon description frames the event around AI for real fintech problems and gives three tracks:

| Track | Brief's intent | Munim-AI relationship |
|---|---|---|
| Merchant Growth AI | Help Paytm merchants grow, manage operations, and serve customers. | **Primary fit.** Turns payment records into understandable business signals and a merchant-approved shop-side experiment. |
| AI-Powered Financial Journeys | Simplify customer-facing insurance, lending, and fintech journeys. | Not the selected problem. Munim-AI does not recommend or originate loans/insurance in this prototype. |
| Autonomous AI Teammates | AI teammates that understand context, decide, act, and support human teams in sales/service. | Adjacent only. A future merchant assistant could take bounded actions, but this prototype keeps approval with the merchant and does not claim autonomous execution. |

The track wording here comes from the brief supplied by the team. Official judging weights, eligibility, data rules, and the Sarvam API offer should be confirmed from organizer materials. The build should follow the confirmed rules if they differ.

## 3. Problem statement

### 3.1 User and context

A small offline merchant—such as a kirana, tea stall, or pharmacy—may accept UPI through a QR code and have limited time to study dashboards. Payment records can show completed transactions, but a merchant still needs to interpret changes and decide whether any action is worth trying. A payment-only view is inherently partial: cash, udhaar, stock-outs, footfall, refunds outside the available feed, and customer reasons may be missing.

### 3.2 Problem statement

**How might we help a time-constrained small merchant understand a meaningful change in the payments they can see, verify the evidence in seconds, and choose a safe next action in their language—without inventing causes or overstating what payment data proves?**

### 3.3 Why it matters to business

A useful merchant copilot can reduce the effort needed to turn records into a decision, make existing payment data more actionable, and give a merchant a simple way to try and review a shop-side change. The prototype can demonstrate usability and an honest decision loop. It cannot establish actual incremental sales or Paytm business impact without a real deployment and controlled evaluation.

## 4. Existing product landscape and competitive honesty

Public Paytm materials already describe merchant analytics and business-management tools. The Analytical tab support page references new/repeat/churn trends, retention cohorts, RFM, payment failure reasons, and recommendations. Paytm's merchant dashboard support page lists transaction monitoring, settlements/refunds, analytics, and reporting. Paytm Payment Analytics describes success-rate analysis, customer analytics, churn, retention, and failure analysis for online merchants. The Paytm for Business site also advertises payments, Soundbox, invoicing, business insights, loans/insurance, and growth products.

Therefore:

- **Do not claim** Paytm has no analytics, no churn insights, or no recommendations.
- **Do not claim** a unique or validated product advantage over Paytm or other UPI apps without direct product research and evidence.
- **Prototype hypothesis:** a compact, voice-first flow for a small offline merchant that combines a computed observation, an understandable “why,” a merchant-controlled next step, and a transparent result comparison may reduce the effort between data and action.
- **Potential distinction to test:** the experience and trust contract (local-language question/brief, evidence panel, explicit uncertainty, approval before action) rather than an unverified claim that underlying analytics are absent elsewhere.

Sources are listed in the README. Public feature pages do not establish which features are available to every merchant, on every plan, in every geography, or on every device. Validate with a real merchant or organizer before describing a feature as universally available.

## 5. Product goals and non-goals

### Goals for the hackathon prototype

1. Demonstrate one complete merchant task from question to evidence to approved mock action to outcome comparison.
2. Keep every statistic reproducible by deterministic code.
3. Give the merchant a visible explanation of the time window, comparison, evidence, and missing data.
4. Support a simple Hindi/Hinglish/English interaction, with text input as a reliable fallback.
5. Show an explicit boundary between synthetic demo data and real Paytm data.
6. Make the user the decision-maker; the AI may draft an action but cannot publish it without confirmation.

### Non-goals

- Paytm or another UPI app integration, production API credentials, bank access, or live merchant data.
- Payment authorization, fraud blocking, credit scoring, lending/insurance eligibility, or financial advice.
- Automatic customer messaging or use of customer contact data.
- Inventory prediction, stock-out detection, weather forecasting, ONDC, GST filing, or cash/udhaar accounting in the two-day scope.
- Claiming causal impact from a before/after comparison.
- Using an LLM to calculate totals, infer a customer's identity, or invent the reason for a change.

## 6. Primary user and user stories

**Primary persona:** A busy owner/operator of a small neighborhood shop who accepts digital payments, is more comfortable speaking than navigating reports, and wants one useful answer without reading a long analytics dashboard.

- As a merchant, I can ask “How was business?” and get a short summary for a stated period.
- As a merchant, I can see the facts and comparison behind every observation.
- As a merchant, I can reject or edit a suggested action before it is shown as approved.
- As a merchant, I can view what happened during a later time window without being told that the action caused it.
- As a merchant, I can see when the system lacks enough data and get a clarification instead of a confident guess.

## 7. Core experience and scope

### 7.1 Core loop (must work)

1. **Trigger:** Merchant opens a morning brief or types/speaks “How was business?”
2. **Select scope:** Display the merchant persona and date range; default to a 7-day period compared with the preceding comparable 7 days. Use a clear timezone and define whether the current incomplete day is excluded.
3. **Compute:** Python/pandas (or DuckDB if useful) computes the chosen facts from a normalized transaction table. Do not use LLM arithmetic.
4. **Explain:** The LLM receives only the computed facts JSON, allowed action templates, and language preference. It returns a strict structured response. A validator rejects unsupported values and claims.
5. **Show evidence:** A “Why am I seeing this?” panel lists the exact comparison, sample counts, and caveats.
6. **Offer action:** The merchant can accept, edit, or reject a shop-side offer/counter notice. The prototype marks publication as **Mocked — not sent or published**.
7. **Review outcome:** Compare sales in the selected action window with a prior comparable period. Show raw counts/amounts, windows, and missing context. Say “sales were higher/lower during this window,” never “the offer caused an increase.”

### 7.2 Initial analytics signals

| Signal | Proposed calculation | Required data | Caveat shown |
|---|---|---|---|
| Revenue/collections change | Sum successful transaction amounts for current and comparable periods; report absolute and percentage difference. | Timestamp, amount, status, merchant identifier. | Payment collections are not total business revenue; cash and other apps may be absent. |
| Hourly pattern / peak gap | Aggregate successful amount and count by local hour and compare with historical same weekday/hour bins. | Timestamp, amount, status. | A quiet hour does not prove lost demand; use enough historical days and show sample size. |
| Average ticket drift | Mean or median successful amount per transaction for current vs reference period. | Amount, timestamp, status. | Ticket size may shift with product mix; it is not a price or margin measure. Prefer median alongside mean. |
| Payment failure rate | Failed attempts divided by all attempts for the same window, with reason breakdown only if reason exists. | Attempt status and ideally failure reason. | A QR transaction export may not contain failed attempts or diagnostic reason codes. If absent, mark unavailable; do not infer. |
| Lapsed repeat-payer count | Distinct stable pseudonymous payer tokens with at least 3 successful payments in prior 28 days and none in the most recent 7 days. | Stable, merchant-scoped pseudonymous payer token and timestamp. | Only calculate if the feed provides stable tokens and this use is authorized. Do not resolve identities or message people. |

**Minimum data sufficiency:** expose the sample size and selected windows. Suppress percentages for zero baselines. For small samples, label the observation low confidence or say there is not enough data. Define timezone handling and exclude pending/reversed transactions according to an explicit status mapping.

## 8. Data plan and schema

### 8.1 Hackathon data

Generate synthetic, clearly labelled transactions for three personas: kirana, tea stall, medical store. Use 90 days to support weekday/hour comparisons. Plant a small number of explainable scenarios (e.g., a decline in morning collections, a shift in median ticket, repeated returning payers who are absent recently) and keep a written scenario manifest so the team knows what the data is demonstrating.

Synthetic data must not be described as observed Paytm behavior. Do not include real names, phone numbers, UPI IDs, bank details, or copied live transactions.

### 8.2 Minimal normalized row

```json
{
  "transaction_id": "synthetic_tx_0001",
  "merchant_id": "synthetic_merchant_kirana_01",
  "timestamp": "2026-10-01T10:24:00+05:30",
  "amount_paise": 12500,
  "status": "SUCCESS",
  "payment_method": "UPI",
  "payer_token": "synthetic_payer_0042",
  "failure_reason": null,
  "source": "synthetic"
}
```

Schema rules:

- Store currency as integer paise where practical; format rupees only at the UI boundary.
- `status` uses an explicit enum such as `SUCCESS`, `FAILED`, `PENDING`, `REVERSED`, `REFUNDED`; define inclusion per metric.
- `payer_token` is optional. Never substitute raw phone number, VPA, or name into the LLM context.
- `failure_reason` is optional and source-dependent. Null means unavailable, not “no failure reason.”
- Keep provenance (`source`) and the synthetic-data banner visible in demo mode.
- A real feed may omit payer token, failed attempts, failure reasons, customer contacts, or even certain transaction statuses. The analytics engine must disable metrics whose inputs are missing.

### 8.3 Facts JSON passed to LLM

The analytics service should produce a small schema-versioned object, e.g.:

```json
{
  "schema_version": "1.0",
  "merchant": {"persona": "kirana", "data_mode": "synthetic"},
  "window": {"current_start": "...", "current_end": "...", "baseline_start": "...", "baseline_end": "...", "timezone": "Asia/Kolkata"},
  "metrics": {
    "successful_amount_paise": {"current": 842500, "baseline": 1032000, "delta_paise": -189500, "delta_percent": -18.36, "n_current": 42, "n_baseline": 51, "status": "available"},
    "median_ticket_paise": {"current": 15000, "baseline": 18000, "status": "available"},
    "failure_rate": {"status": "unavailable", "reason": "failed_attempts_not_in_source"},
    "lapsed_repeat_payers": {"count": 4, "status": "available", "definition": "3+ successful payments in prior 28d; none in latest 7d", "identity_scope": "merchant_scoped_pseudonymous_tokens"}
  },
  "evidence_ids": ["revenue_change", "median_ticket_change"],
  "allowed_actions": ["counter_offer", "shop_notice"],
  "data_quality": {"missing_status_rows": 0, "synthetic": true}
}
```

This is an example contract, not a discovered Paytm feed schema. The implementation should keep raw payer identifiers outside the LLM and avoid generating individual-level descriptions.

## 9. LLM, voice, and safety contract

### LLM role

- Turn facts into a concise explanation and propose one template-based action relevant to the data.
- Return JSON with `summary`, `evidence_ids`, `caveats`, `suggested_action`, `confidence`, and `clarification_needed`.
- Use only facts and IDs from the provided payload. Do not create amounts, percentages, dates, customer identities, reasons, causal statements, or external factual claims.
- Do not send a customer offer or contact anyone. The merchant reviews and confirms the mock action.

### Validation

1. Parse against a strict schema; reject malformed output.
2. Verify evidence IDs exist in the facts.
3. Verify each numerical claim is in facts or deterministically rendered from a fact. Prefer templated rendering for the UI's numeric values.
4. Reject disallowed causal/identity claims and unsupported reasons.
5. If rejected or the LLM is unavailable, show a deterministic fallback explanation.
6. Log the facts snapshot and model output in synthetic demo mode for reproducibility; do not log secrets or personal data.

### Voice

The brief says a Sarvam AI API is available to participants; exact credentials, models, quotas, terms, and whether both speech-to-text and text-to-speech are provided must be confirmed. Design voice as an adapter, not a hard dependency. Text input/output and a prerecorded audio fallback keep the core demo working. Display the recognized text and ask for confirmation when confidence is low or the parsed intent would create a record/action.

## 10. Optional fraud research signal

The separately provided `munim_inference_bundle.zip` packages a FastAPI `/predict` endpoint and saved XGBoost/Isolation Forest artifacts. It takes a single transaction payload and returns a supervised fraud probability, anomaly score/percentile, a fusion resolution, diagnostics, and an explanatory research report. The existing project description labels the system offline and post-transaction research only.

### Intended integration if time permits

- Treat it as a separate **“Research risk signal”** demo card, not part of growth recommendation math.
- Run only with synthetic transactions, stable synthetic IDs, and clear provenance.
- Show the relevant model outputs and say “unusual compared with this model's training reference; review manually.”
- Do not say the transaction is definitively fraudulent, block it, or infer a fraud burst from a single-event endpoint.
- Do not send identifiers or raw features to the LLM; use a minimal sanitized fact summary if human-readable explanation is needed.

### Limitations to disclose

- The source project combines multiple public datasets and includes PaySim synthetic mobile-money data. It is not a representative, validated Paytm merchant dataset.
- Its reported benchmark metrics are model/dataset-specific and are not expected Paytm accuracy, production performance, or hackathon proof of fraud detection.
- The bundle has not been independently run from this repository at PRD time. Its package/version compatibility and endpoint behavior need local verification before demo use.
- A single-transaction API does not itself establish temporal burst/failure/refund-scam patterns. Such rules need event history and separately defined validation.

If integration risks the core demo, cut this beat first.

## 11. System architecture (target)

```text
Synthetic CSV / generated transactions
                 │
                 ▼
      Schema + status normalization
                 │
                 ▼
   Deterministic analytics service ─────────► Evidence panel / charts
                 │                                   │
                 ▼                                   │
       Versioned facts JSON                          │
                 │                                   │
       LLM explanation adapter                       │
                 │                                   │
       Strict output validator ◄── fallback templates│
                 │                                   │
                 ▼                                   ▼
      Merchant review / edit / approve ──► mocked offer record
                                                  │
                                                  ▼
                              comparable-window outcome comparison
```

Potential prototype stack: Python + pandas/DuckDB and FastAPI for data/API; React/Vite or the team's existing frontend for UI; Sarvam adapter if access is ready; JSON/SQLite for local demo state. Choose the stack already working in the repository once application code is added. Avoid spending the deadline replacing frameworks.

## 12. Functional requirements

| ID | Requirement | Priority / acceptance condition |
|---|---|---|
| F1 | Load the selected synthetic merchant and date window. | P0: persona and data-mode banner visible; same input produces same facts. |
| F2 | Compute revenue, ticket, hourly, and optional churn/failure metrics. | P0: each metric shows definition, windows, and sample counts; unavailable inputs disable metric. |
| F3 | Ask a question by text; voice is an optional input/output adapter. | P0 text works; P1 voice demo works or a clear fallback is available. |
| F4 | Produce evidence-grounded explanation. | P0: strict JSON validation; unsupported number/evidence causes deterministic fallback. |
| F5 | Show “Why am I seeing this?” explanation. | P0: exposes metric, comparison dates, counts, and caveats. |
| F6 | Suggest a shop-side action. | P0: action is editable/rejectable and not published automatically. |
| F7 | Record mock action and display status. | P0: visible “mock only; not published/sent” label. |
| F8 | Compare an outcome period with a prior comparable period. | P0: both periods and counts shown; no causal wording. |
| F9 | Show optional fraud research signal. | P2: only after the full P0 loop is stable and artifacts run locally. |

## 13. Non-functional and trust requirements

- **Explainability:** every recommendation has traceable evidence and metric definitions.
- **Determinism:** analytics facts do not change when the LLM wording changes.
- **Privacy:** synthetic-only hackathon demo; least-data principle; no contacts or raw personal identifiers in prompts or logs.
- **Graceful degradation:** model/API/voice failures fall back to text and deterministic output.
- **Honest labels:** synthetic, mocked, unavailable, and research-only states are visually explicit.
- **Language accessibility:** concise, familiar language; avoid jargon; preserve numeric accuracy when translating.
- **Human control:** merchant confirms action; no autonomous publication, payment, lending, or customer messaging.

## 14. Measurement plan

### Hackathon demo measures (can be measured locally)

- Core-loop completion: question → evidence → approved mock action → outcome view.
- Time to understand: can a reviewer explain why the insight appeared after reading the evidence panel?
- Grounding checks: unsupported numeric claims rejected; deterministic fallback works.
- Data-quality behavior: missing payer token/failure records cause “unavailable,” not fabricated metrics.
- Action control: reject/edit/approve states are visible and correct.

### Real-world outcomes (not claimable from the synthetic demo)

- Merchant comprehension and trust from usability interviews.
- Repeat use and time saved compared with manually opening reports.
- Action acceptance/rejection and the reasons merchants give.
- Sales outcomes using randomized or otherwise carefully controlled experiments, with seasonality, footfall, stock, and other channels accounted for.
- Data availability, consent, privacy, and metric error rates on a real authorized feed.

## 15. Demo story

Use one planted synthetic scenario. Example: a tea stall has lower UPI collections in the morning window than the previous comparable week, while afternoon collections are stable. Munim states only the measured change and shows timestamps/counts. It explicitly says the payment records cannot tell whether this came from footfall, cash, stock, or customer choice. The merchant can approve a mock “morning chai + snack” counter notice. Later, Munim shows the compared window totals and reminds the reviewer this is correlation/observation, not proven causality.

The scenario manifest should list the planted pattern and expected computed outputs so the team can rehearse and verify the demo. Do not design the story to imply the system knows a stock-out or customer motive from UPI data.

## 16. Risks, open questions, and mitigations

| Risk / open question | Why it matters | Mitigation / owner action |
|---|---|---|
| No confirmed Paytm transaction-data API/access. | The prototype could be mistaken for a live integration. | Use synthetic data, mark it visibly, and ask organizers what data/API access is allowed. |
| Merchant analytics overlap with existing Paytm features. | Generic charts or churn recommendations may not be differentiated. | Position on interaction/trust loop, verify product availability, and avoid “first/only” claims. |
| Stable payer tokens unavailable. | Lapsed-repeat metric becomes impossible or privacy-sensitive. | Disable that metric if absent; never derive identity from contact data. |
| Failed attempts/reasons absent from exported data. | Failure rate can be misleading if denominator excludes failed attempts. | Show “unavailable” unless all attempts are represented. |
| Synthetic records look like actual Paytm behavior. | Judges may over-read results. | Persistent synthetic banner and explicit dataset description. |
| LLM fabricates causes or values. | Financial trust risk. | Facts-only prompt, strict schema, evidence IDs, validator, fallback. |
| Voice API unavailable/slow/network trouble. | Demo can fail under venue conditions. | Text-first fallback and prerecorded voice path; cache demo output. |
| Fraud model domain shift and artifact/runtime issues. | False confidence and integration delay. | Optional P2 beat; synthetic-only; verify locally; disclose mixed datasets and offline scope. |
| Outcome comparison implies causal lift. | Before/after confounding. | Use neutral comparison language; explain missing context and no control group. |
| Hackathon rules, judging rubric, Sarvam terms not confirmed. | Product/technical mismatch. | Confirm official rules and access with organizers/team packet; treat supplied event brief as current working context only. |

## 17. Two-day execution plan

### Tonight: establish a reliable vertical slice

1. Confirm the exact demo environment and data format; freeze the P0 scope.
2. Add synthetic transaction schema, deterministic generator, three personas, and scenario manifest.
3. Implement analytics functions with unit-level manual examples: windows, statuses, currency, timezone, zero-baseline, missing tokens.
4. Commit sample facts JSON and expected values for repeatable demo.

### Tomorrow: user flow and grounded explanation

1. Build dashboard with merchant selector, date range, summary, evidence panel.
2. Add question input and deterministic explanation fallback.
3. Add LLM adapter only after facts JSON is stable; validate all output.
4. Add action preview, edit/reject/approve, mock publication label.
5. Add outcome comparison and caveat text.
6. Integrate Sarvam voice if credentials/model work; otherwise use text and prerecorded fallback.

### Final hours: polish, verify, rehearse

1. Run the full demo path on the actual presentation laptop and offline/poor-network conditions.
2. Confirm every visible number matches the generated facts; check missing-data cases.
3. Cut fraud integration if it makes the core loop less reliable.
4. Prepare a short pitch, architecture, data provenance, guardrails, limitations, and Q&A slide.
5. Keep one clean demo persona/scenario and one backup screenshot/video if allowed by event rules.

The exact event date/time should be taken from the official organizer message; the team has stated the event is in approximately two days.

## 18. Roles (working assignment)

- **Parth:** LLM adapter, voice integration, structured output, numeric/evidence guardrails.
- **Priyanshu:** synthetic data generator, normalized schema, deterministic analytics; fraud bundle only as optional integration.
- **Rachit:** merchant UI, evidence/action flow, deck and demo rehearsal.

All three should review metric definitions and demo claims. Scope changes require agreement; the core loop takes priority over optional features.

## 19. Judge questions and honest answers

1. **Is this integrated with Paytm?** No. The hackathon prototype uses synthetic data and a mocked action; no Paytm integration is claimed.
2. **Does Paytm already have analytics?** Yes. Public Paytm materials describe merchant/payment analytics. Our prototype explores a voice-first, evidence-linked path from a payment observation to a human-approved next step.
3. **Can UPI history tell you why sales fell?** No. It shows only recorded payment behavior in the available feed. Cash, footfall, stock-outs, and customer intent may be missing.
4. **How do you prevent hallucinated numbers?** The analytics engine computes them; the LLM gets a constrained facts object; output is schema/evidence validated; deterministic wording is the fallback.
5. **Do you identify or message lapsed customers?** No. We count only stable merchant-scoped pseudonymous tokens if a permitted feed provides them; no contact data or messaging is used.
6. **Does the offer increase sales?** We can compare windows in the demo, but cannot claim causation without a controlled real-world experiment.
7. **Why not use the fraud model as the main feature?** It is a separate offline research model over mixed public data and scores a transaction; it does not solve the chosen merchant-growth problem or establish Paytm fraud performance.
8. **What happens when data is missing?** The affected metric is marked unavailable with a reason; we don't impute a confident business claim.
9. **Why voice?** It is a usability hypothesis for a time-constrained merchant; it is an optional interface with a text fallback, not proof of lower friction until tested.
10. **What would be needed for a real pilot?** Merchant research, authorized privacy-preserving data access, feed-specific metric validation, security/compliance review, reliability work, and a controlled pilot measuring comprehension and outcomes.

## 20. Decision log

- **Locked:** Munim-AI, Track 1 Merchant Growth AI.
- **Locked core:** explain payment-history facts → show evidence → merchant approves a shop-side action → compare an outcome window honestly.
- **Synthetic-only demo:** no claim of Paytm integration.
- **Fraud model:** optional second beat, cut first if it threatens the core loop.
- **Out of scope:** lending, ONDC, bill scanning, weather, inventory, real WhatsApp sending, automatic customer contact, payment blocking.
- **Open:** exact facts JSON / source schema, voice service availability, official judging criteria, collaborators and code scaffold, and whether stable pseudonymous customer tokens can legally/technically be used in a real feed.

## References

- Event tracks: team-provided Paytm Build for India AI Hackathon brief (not yet independently verified against official event rules).
- [Paytm for Business: Analytical tab](https://business.paytm.com/support/what-is-the-use-of-analytical-tab)
- [Paytm merchant dashboard support](https://business.paytm.com/support/what-is-the-use-of-merchant-dashboard-)
- [Paytm Payment Analytics](https://business.paytm.com/payment-analytics)
- [Paytm for Business](https://business.paytm.com/)
- Fraud-model source project description and packaged inference bundle were supplied by the team; those are research artifacts, not evidence of Paytm deployment or performance.

