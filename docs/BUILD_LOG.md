# Munim-AI Build Log and Handoff

**Purpose:** a durable, chronological handoff for the team and anyone resuming from another machine. Keep the current snapshot near the top and append a milestone after each major change.

## Current status snapshot

**Last checked:** 30 October 2026  
**Active work branch:** `codex/explainer-hardening` (latest code change: `85526fb`; subsequent commits update this log)
**Base:** `origin/main` at `ea21a1f`
**Working tree:** clean at the last local check.
**Merge status:** Antigravity’s explainer work is merged into `main` in PR #6. The hardening changes (`85526fb`) and handoff docs (`6ce832d`) are pushed to this branch and are not in `main`; a PR has not yet been opened for them. A separate remote branch, `antigravity/handoff-audit` at `b813ac6`, adds a longer audit version of this log only.

### Product and scope

- **Product:** Munim-AI is the merchant-facing copilot; KiranaOS is its structured shop memory.
- **Track:** Paytm Build for India Hackathon, Track 1 — Merchant Growth AI.
- **Core Experience:** Merchant asks "Aaj kaisa raha?" and receives an understandable business brief grounded strictly in transaction facts, plus a bounded action the merchant controls.
- **Data Integrity:** All current demo data is synthetic (`shop_synth_01`). There is no live Paytm integration, production merchant authentication, or real customer data.
- **Paytm Order Status API:** The Paytm Transaction Status API snippet is outside the current synthetic demo scope and is only relevant if the product later adds verification for real Paytm PG merchant orders.
- **Key Documents:** Read the [hackathon PRD](KIRANAOS_HACKATHON_PRD.md), [execution plan](HACKATHON_EXECUTION_PLAN.md), and [backend API contract](contracts/backend-api-v0.md).

### Implemented state by area

- **Backend (`backend/`):**
  - FastAPI and SQLite services under `backend/app/`.
  - Financial amounts are strictly integer paise.
  - Endpoints:
    - `GET /health` — health check and data mode.
    - `GET /customers/resolve`, `POST /customers` — customer alias resolution and registration.
    - `GET /ledger/customers/{id}/balance`, `POST /ledger/credits`, `POST /ledger/repayments` — ledger entries and derived balance.
    - `GET /products/resolve`, `POST /products`, `GET /inventory/products/{id}/stock`, `POST /inventory/stockout-observations`, `POST /inventory/counts` — stock balance, stockout observations, and physical counts.
    - `GET /events` — activity timeline of recent business events.
    - `GET /insights/facts` — deterministic, evidence-backed synthetic UPI facts (payment collections, collection change %, median ticket, failure rate, lapsed repeat payers).
    - `POST /insights/explain` — server-side facts-only AI explanation with strict number validation and deterministic fallback (on `codex/explainer-hardening` and `antigravity/handoff-audit`).
    - `POST /payments/intake`, `GET /payments/review`, `POST /payments/{id}/allocate`, `POST /payments/mappings` — synthetic payment intake, review queue for unmatched payments, manual allocation with merchant confirmation, and payer token mappings.
- **Mobile (`mobile/`):**
  - Expo (SDK 52), React Native, TypeScript app under `mobile/`.
  - Tabbed interface: Copilot, Pay Review, Inventory, Timeline, Insights.
  - "Aaj kaisa raha?" brief: queries `GET /insights/facts` and `POST /insights/explain`, displaying evidence chips, caveats, comparison periods, and merchant-controlled mock action approval.
  - Payer review flow: displays unmatched synthetic payments and allows merchant-confirmed allocation to known customers.
  - Inventory flow: stock lookup, stockout observation recording, physical inventory count reconciliation.
- **Required Environment Variables (redacted):**
  - Backend (`.env` in repository root or backend working directory, gitignored):
    - `GEMINI_API_KEY`: Google Gemini API key (tested model: `gemini-3.8-flash`).
    - `SARVAM_API_KEY`: Reserved for future speech-to-text / Indic voice models.
    - `MONGODB_URI`: Reserved for future MongoDB storage; demo runs on SQLite.
    - `VITE_API_BASE_URL`: Web / test client base URL setting.
  - Mobile (`mobile/.env` or Expo public config):
    - `EXPO_PUBLIC_API_BASE_URL`: URL of running FastAPI backend (e.g. `http://127.0.0.1:8000` for simulator, LAN IP for phone demo).

### Verification ledger

- **Verified from Git at this snapshot:** remote refs fetched; `main` is `12f8491`; `codex/explainer-hardening` is `6ce832d`; the branch is pushed and the local working tree was clean.
- **Verified by Codex:** `git diff --check` passed before the hardening commit; see the latest verification milestone below for runtime/mobile checks on the current branch.
- **Reported by Antigravity, not rerun on the hardening branch:** TypeScript typecheck and Android Expo export passed for the explainer implementation; fallback endpoint returned valid JSON; Gemini requests reportedly timed out or returned 503.
- **Reported in the later Antigravity audit:** mobile typecheck and Android Expo export passed; direct Gemini call timed out after about 15 seconds. The audit described backend facts/explainer as passing, but its supplied command history showed earlier pytest, TestClient, and direct Python smoke attempts exiting with code 1 without the later successful command/output. Codex subsequently reproduced the backend fallback path through local HTTP; details are below.
- **Verified by Codex on the current hardening branch:** backend facts/explainer HTTP smoke with a temporary SQLite database and Gemini disabled; mobile typecheck; Android export. See the latest milestone for exact outcomes.
- **Still not verified:** live Gemini response and full physical-phone-to-laptop demo.

## How to resume on another laptop

1. Clone or fetch the repository:
   ```bash
   git fetch origin --prune
   ```
2. Check out the current audit / hardening branch:
   ```bash
   git checkout antigravity/handoff-audit
   # or git checkout codex/explainer-hardening
   ```
3. Read this file, the [PRD](KIRANAOS_HACKATHON_PRD.md), the [execution plan](HACKATHON_EXECUTION_PLAN.md), and the [API contract](contracts/backend-api-v0.md).
4. Run `git status` before making edits; never force-push to shared branches.
5. Setup backend:
   ```bash
   cd backend
   python -m venv .venv
   .venv\Scripts\activate  # Windows or source .venv/bin/activate on Unix
   pip install -r requirements.txt
   # Ensure .env exists in repo root with GEMINI_API_KEY
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
6. Setup mobile:
   ```bash
   cd mobile
   npm ci
   npm run typecheck
   npx expo start
   ```
7. After each major change, update this log with exact command outputs, commit, and push to your team branch.

## Milestones

### 2026-10-30 — Product scope and implementation plan recorded
- **Goal:** Define hackathon use case, safety boundaries, and demo scope.
- **Artifacts:** `docs/KIRANAOS_HACKATHON_PRD.md`, `docs/HACKATHON_EXECUTION_PLAN.md`, and contracts under `docs/contracts/`.
- **Branch/commit:** Historical commits merged into `origin/main`.
- **Checks:** Documents and schema files present in repository.
- **Limitations:** Scope intentionally restricted to synthetic single-merchant kirana shop.
- **Next:** Backend ledger, inventory, and deterministic facts scaffolding.

### 2026-10-30 — Backend ledger, inventory, facts, and mocked payment review integrated
- **Goal:** Provide structured synthetic merchant records, safe payment review, inventory events, and reproducible insight facts.
- **Changes:** FastAPI/SQLite services and APIs; integer-paise financial math; idempotency keys and merchant confirmation; exact-match synthetic payer mapping; deterministic facts calculation.
- **Branch/commit:** Merged through `origin/main` history before `12f8491`.
- **Checks:** Seeded synthetic transactions, verified endpoints for customers, ledger, stock counts, and facts.
- **Limitations:** Synthetic single-shop behavior; no live Paytm feed, production authentication, or verified real-world impact.
- **Next:** Build mobile frontend to consume these endpoints.

### 2026-10-30 — Mobile shell and "Aaj kaisa raha?" brief integrated
- **Goal:** Demonstrate merchant-facing mobile flow against backend contracts.
- **Changes:** Expo/TypeScript screens, typed API client (`mobile/src/api/ledgerClient.ts`), facts display, synthetic-data caveats, mocked action approval.
- **Branch/commit:** Mobile work merged via PR #5 (`7dacba0`).
- **Checks:** Typecheck and Android export verified by Antigravity; contract mismatches corrected.
- **Limitations:** Physical-device/LAN demo setup depends on local network configuration.
- **Next:** Server-side facts-only AI explanation.

### 2026-10-30 — Facts-only Gemini explanation merged into main
- **Goal:** Explain deterministic merchant facts in simple Hindi/English terms with guaranteed deterministic fallback.
- **Changes:** Server-side Gemini explainer (`backend/app/services/explainer.py`), number/evidence validators, fallback copy, and mobile explanation card in HomeScreen.
- **Branch/commit:** `antigravity/facts-ai-explanation`; commits `898647e` and `01a7651`; merged by PR #6 at `12f8491`.
- **Checks:** API response validated; deterministic fallback verified when upstream model times out or returns 503.
- **Limitations:** Upstream model availability; explanation must remain optional and fallback behavior must be demonstrated.
- **Next:** Explainer hardening (POST semantics, fixed copy, header authentication).

### 2026-10-30 — Explainer hardening and safety boundaries
- **Goal:** Switch to POST semantics, tighten number validation, protect API keys in request headers, sanitize error outputs, and enforce server-owned action templates.
- **Changes:**
  - `backend/app/api/insights.py`: `POST /insights/explain` with `BriefExplanationRequest` body.
  - `backend/app/services/explainer.py`: Model selects `action_type` only; server templates supply `proposed_action`; negative-number validation tightened (no absolute-value substitutions); API key sent via `x-goog-api-key` header; exception details sanitized.
  - `mobile/src/api/ledgerClient.ts`: `fetchBriefExplanation` updated to `POST /insights/explain` with JSON body.
  - `docs/contracts/backend-api-v0.md`: Updated to document `POST /insights/explain`.
  - `docs/BUILD_LOG.md`: Initialized by Codex in `6ce832d`.
- **Branch/commit:** `codex/explainer-hardening` at `85526fb` and `6ce832d`.
- **Checks:** `git diff --check` passed.
- **Limitations:** Live Gemini request timed out in local environment; fallback engaged as expected.
- **Next:** Comprehensive verification of backend and mobile builds, updating cumulative log.

- **Goal:** use POST semantics and constrain model output to safer bounds.
- **Changes:** `POST /insights/explain` accepts `BriefExplanationRequest`; mobile sends JSON; the model selects a permitted action type while the backend supplies fixed action copy; negative-number validation no longer accepts absolute-value substitutions; Gemini API key is sent in `x-goog-api-key`; upstream exception details are sanitized.
- **Branch/commit:** `codex/explainer-hardening` at `85526fb`, based on `origin/main` `12f8491`; pushed, no PR opened yet.
- **Checks:** `git diff --check` passed before commit. Runtime and mobile build checks have not been rerun after these changes.
- **Limitations:** number validation checks whether values occur somewhere in the facts collection, not whether each sentence ties each value to the correct fact ID. Treat it as a guardrail, not proof of semantic correctness.
- **Next:** run backend smoke checks, mobile typecheck/export, then open a PR if checks pass.

### 2026-10-30 — Follow-up audit report received

- **Goal:** preserve the remote audit findings without confusing reported results with independently verified results.
- **Changes:** Antigravity pushed `antigravity/handoff-audit` at `b813ac6`, based on `codex/explainer-hardening` at `6ce832d`. The remote commit changes only `docs/BUILD_LOG.md`; it does not add application code.
- **Checks reported:** mobile TypeScript check and Android export passed; Gemini direct call timed out; the report claims backend fact/explainer/fallback behavior passed.
- **Evidence gap:** the command history supplied with that report also lists backend pytest, TestClient smoke, and direct Python smoke attempts exiting with code 1. The report gives no exact successful backend command or output to reconcile those failures. Codex therefore records backend verification as unverified.
- **Outcome:** Codex later ran a reproducible local HTTP smoke check successfully; see the following milestone. Keep using `codex/explainer-hardening` as the working branch; do not merge the audit-only branch as the code PR by default.

### 2026-10-30 — Codex backend and mobile verification

- **Goal:** independently verify the hardening branch after receiving the audit report.
- **Backend:** an isolated temporary SQLite database was seeded and exercised through local Uvicorn plus Python's standard-library HTTP client. `GET /insights/facts?persona=kirana` returned HTTP 200 with 5 facts; `POST /insights/explain` returned HTTP 200, used deterministic fallback without reading or using a Gemini key, and returned the fixed `counter_notice` action. OpenAPI exposed the POST route. **Passed.**
- **TestClient note:** the installed Starlette TestClient could not import because its optional `httpx2` dependency is absent. This is a test-client environment dependency, not an application runtime failure; the HTTP smoke check above exercised the real ASGI server instead. No test dependency was added.
- **Mobile dependencies:** `npm run typecheck` initially could not start because the existing `node_modules` lacked `tsc`. `npm ci` restored the lockfile dependencies without tracked file changes.
- **Mobile checks:** `npm run typecheck` exited 0. `npx expo export --platform android` exited 0 and bundled 706 modules into Hermes bytecode. **Passed.**
- **Dependency note:** `npm ci` reported 8 dependency advisories (5 low, 3 high). `npm audit --omit=dev` also exited 1 and identified high-severity transitive advisories in `deepmerge` and `zod` through Expo tooling. The suggested `npm audit fix --force` would downgrade Expo to 51, so no dependency changes were made. The branch does not change `package.json` or the lockfile; assess these existing advisories separately before release.
- **Limitations:** Gemini live connectivity was deliberately not tested; the fallback was forced so no local key or billable API request was used. Physical-device/LAN demo remains unverified.
- **Next:** review the branch diff and open a PR for `codex/explainer-hardening`; the dependency advisories are inherited from the current Expo dependency tree and were not introduced by this branch.
