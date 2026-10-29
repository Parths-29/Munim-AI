# Build Plan

This is the execution checklist derived from [the PRD](PRD.md). The core business-insight loop is the release gate; optional voice polish and the fraud signal come later.

## Work sequence

### P0 — synthetic data and metrics

- [ ] Define normalized transaction schema and explicit status mapping.
- [ ] Generate 90 days of deterministic synthetic data for kirana, tea stall, and medical store personas.
- [ ] Write a scenario manifest with planted changes and expected answers.
- [ ] Compute comparable-window collections, transaction counts, mean/median ticket, and hourly pattern.
- [ ] Compute failure rate only if attempts and statuses include all attempts.
- [ ] Compute lapsed repeat-payer count only if stable pseudonymous payer tokens exist.
- [ ] Add timezone, missing-data, zero-baseline, and minimum-sample handling.
- [ ] Produce a versioned facts JSON with sample sizes, windows, and provenance.

### P0 — merchant experience and trust

- [ ] Merchant persona/date-window selection and persistent synthetic-data badge.
- [ ] “How was business?” text flow.
- [ ] Insight card plus “Why am I seeing this?” evidence panel.
- [ ] Deterministic explanation fallback.
- [ ] LLM structured response and strict schema/evidence/number validator.
- [ ] Clarification path when speech or intent is uncertain.

### P0 — bounded action and outcome

- [ ] Offer/counter-notice preview with edit, reject, and approve controls.
- [ ] Explicit “mock only — not published or sent” state.
- [ ] Record action start/end window for reproducible comparison.
- [ ] Show comparison totals, counts, date windows, and caveats.
- [ ] Use neutral wording; no causal claim.

### P1 — voice

- [ ] Confirm Sarvam API access, supported models, credentials, limits, and terms from the event/team packet.
- [ ] Add STT/TTS adapter behind feature flag.
- [ ] Show recognized transcript before any data-changing action.
- [ ] Test Hindi/Hinglish and Devanagari normalization for the narrow supported prompts.
- [ ] Keep text and prerecorded fallbacks available.

### P2 — fraud research signal

- [ ] Copy the inference bundle into a local integration area without committing secrets or raw datasets.
- [ ] Verify model artifacts load and synthetic `/predict` works on the demo runtime.
- [ ] Confirm its reference-score CSV dependency and packaging assumptions.
- [ ] Display as “Research risk signal”; do not use for growth scoring or payment decisions.
- [ ] Disclose mixed-source training data and offline post-transaction scope.
- [ ] Drop this feature if it jeopardizes the P0 demo.

## Team split

| Owner | Main work | Deliverable |
|---|---|---|
| Parth | LLM/voice/guardrails | Facts-only prompt, validator, voice adapter/fallback |
| Priyanshu | Data/analytics/fraud option | Synthetic data, scenario manifest, deterministic metrics, optional model adapter |
| Rachit | UI/deck/demo | Merchant journey, evidence/action screens, pitch and rehearsal |

## Definition of demo-ready

- One synthetic persona completes the end-to-end loop reliably on the presentation laptop.
- All displayed values are reproducible from the facts JSON.
- “Why am I seeing this?” shows the metric definition, periods, counts, and relevant caveat.
- Missing fields suppress dependent metrics.
- LLM failure and voice failure do not break the experience.
- Action approval is explicit and mock publishing is visibly labelled.
- The outcome comparison does not imply causal lift.
- The pitch states no real Paytm integration and no claim of Paytm fraud accuracy.
