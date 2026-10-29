# Phase 1: Contracts and scaffold

**Phase window:** first 3 hours · **Status:** contracts and backend scaffold drafted; mobile scaffold and team review still pending.

## Decisions proposed for this build

- Product: Munim-AI is the merchant-facing copilot; KiranaOS is structured shop memory.
- Demo: one synthetic shop with synthetic customer/product/payment IDs. No real Paytm integration or personal data.
- Money: integer paise in APIs and database; format INR in the UI.
- Persistence: SQLite for the single-shop hackathon demo; keep tables and API DTOs portable enough to migrate later.
- Backend: FastAPI with typed request/response models. The LLM cannot call arbitrary database writes.
- Mobile: Expo + React Native + TypeScript as requested in the supplied brief; text path works if mic/network/provider is unavailable.
- Voice and LLM: provider-neutral adapters and mocks until credentials, model names, limits, and access are confirmed.
- Reconciliation: unique mock event ID and unique shop-scoped synthetic payer mapping required for automatic matching; ambiguous or excess payment value is held for review/unallocated.
- Ledger: posted credit/repayment is append-only; balance is derived from posted entries; corrections reference the entry they adjust/reverse.
- Stock: stockout is an observation; on-hand stock changes only after a confirmed count/movement.
- Privacy: only synthetic identifiers are used in demo prompts and fixtures.

## Contracts drafted by Codex

- [`contracts/command-proposal.schema.json`](contracts/command-proposal.schema.json): typed proposal and clarification state.
- [`contracts/facts.schema.json`](contracts/facts.schema.json): computed facts sent to the reader/explainer.
- [`contracts/payment-event.schema.json`](contracts/payment-event.schema.json): provider-neutral mocked payment event with idempotency key.
- [`contracts/scenario-manifest.json`](contracts/scenario-manifest.json): canonical demo seed and expected arithmetic.

These are draft v1 contracts for team review. If a field changes, update the schema, sample payload, API type, UI types, and demo fixture together in one coordinated PR.

## Scaffold status and remaining Antigravity task

Codex has added `.gitignore`, `.env.example`, `backend/requirements.txt`, `backend/README.md`, and a minimal `backend/app` health route. The health route reports local API liveness only; no domain behavior or database writes are implemented.

Antigravity should create only the minimum runnable mobile skeleton and keep business workflows for later phases:

```text
backend/
  app/
    api/
    domain/
    services/
  tests/
mobile/
  app/
  src/
    api/
    components/
    features/
    types/
data/
  synthetic/
docs/
  contracts/
```

Remaining artifacts: `mobile/` app shell and `mobile/README.md` start instructions. Do not install audio libraries or request microphone permission in Phase 1. Do not edit `backend/`, root `.gitignore`, `.env.example`, `docs/contracts/`, or this checklist; those belong to the Codex Phase 1 branch. No ledger/payment/AI behavior in the mobile scaffold PR.

## Phase 1 exit checklist

- [ ] Team agrees the v1 contracts and corrected Raju repayment seed arithmetic.
- [ ] All three teammates can clone, branch, push, and open PRs on the GitHub repo.
- [ ] FastAPI health route starts in the selected backend environment.
- [ ] Expo shell starts on the Android demo phone.
- [ ] `.env` and real data are ignored; `.env.example` contains no secrets.
- [ ] `main` contains the merged contracts and scaffold PRs before Phase 2 work branches.
- [ ] Team can identify owners for `backend/`, `mobile/`, `docs/contracts/`, and root integration files.
