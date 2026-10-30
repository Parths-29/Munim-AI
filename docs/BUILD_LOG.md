# Munim-AI Build Log and Handoff

**Purpose:** a durable, chronological handoff for the team and anyone resuming from another machine. Keep the current snapshot near the top and append a milestone after each major change.

## Current status snapshot

**Last checked:** 30 October 2026  
**Active work branch:** `codex/sarvam-voice-input`, based on `codex/mock-action-outcomes` at `5a990b5`
**Base lineage:** `origin/main` at `318863e` (includes merged PR #10), plus pushed mock-action tracking milestone.
**Latest pushed commit:** `91f62cc` — `feat: add Sarvam voice input with merchant confirmation`
**Working tree:** local browser-preview support is being recorded on this branch.
**Merge status:** PRs #7–#10 are in `main`; mock-action tracking and voice input are pushed feature branches, with no PR opened by Codex.

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
    - `POST /insights/explain` — server-side facts-only AI explanation with strict number validation and deterministic fallback.
    - `POST /actions/mock`, `GET /actions/latest` — append-only merchant-approved mock action, baseline snapshot, and scheduled/available/insufficient-data outcome state.
    - `POST /speech/transcribe` — short audio transcription through backend-held Sarvam credentials; the endpoint returns text and does not execute commands.
    - `POST /payments/intake`, `GET /payments/review`, `POST /payments/{id}/allocate`, `POST /payments/mappings` — synthetic payment intake, review queue for unmatched payments, manual allocation with merchant confirmation, and payer token mappings.
- **Mobile (`mobile/`):**
  - Expo SDK 58, React Native 0.88, and TypeScript app under `mobile/`.
  - Tabbed interface: Copilot, Pay Review, Inventory, Timeline, Insights.
  - "Aaj kaisa raha?" brief: queries facts/explanation and restores merchant-approved mock actions with a visible baseline and observation window.
  - Copilot text/voice input: limited deterministic parser for credit, repayment, balance, and stockout commands; transcripts remain editable and commands still need explicit confirmation.
  - Payer review flow: displays unmatched synthetic payments and allows merchant-confirmed allocation to known customers.
  - Inventory flow: stock lookup, stockout observation recording, physical inventory count reconciliation.
- **Required Environment Variables (redacted):**
  - Backend (`.env` in repository root or backend working directory, gitignored):
    - `GEMINI_API_KEY`: Google Gemini API key (tested model: `gemini-3.8-flash`).
    - `SARVAM_API_KEY`: Optional backend-only credential for short speech-to-text. Never put it in `mobile/.env` or `EXPO_PUBLIC_*`.
    - `MONGODB_URI`: Reserved for future MongoDB storage; demo runs on SQLite.
    - `VITE_API_BASE_URL`: Web / test client base URL setting.
  - Mobile (`mobile/.env` or Expo public config):
    - `EXPO_PUBLIC_API_BASE_URL`: URL of running FastAPI backend (e.g. `http://127.0.0.1:8000` for simulator, LAN IP for phone demo).

### Verification ledger

- **Verified from Git before this milestone:** remote refs fetched; `main` is `318863e` and includes PR #10; the mock-action branch is pushed and recorded below.
- **Verified by Codex:** `git diff --check` passed before the hardening commit; see the latest verification milestone below for runtime/mobile checks on the current branch.
- **Reported by Antigravity, not rerun on the hardening branch:** TypeScript typecheck and Android Expo export passed for the explainer implementation; fallback endpoint returned valid JSON; Gemini requests reportedly timed out or returned 503.
- **Reported in the later Antigravity audit:** mobile typecheck and Android Expo export passed; direct Gemini call timed out after about 15 seconds. The audit described backend facts/explainer as passing, but its supplied command history showed earlier pytest, TestClient, and direct Python smoke attempts exiting with code 1 without the later successful command/output. Codex subsequently reproduced the backend fallback path through local HTTP; details are below.
- **Verified by Codex on the hardening branch:** backend facts/explainer HTTP smoke with temporary SQLite and Gemini disabled; mobile typecheck; Android export.
- **Verified by Codex on the current product branch:** parser examples, ledger arithmetic, stockout observation behavior, mobile typecheck, and Android export. See latest milestone for exact outcomes.
- **Still not verified:** live Gemini response and full physical-phone-to-laptop demo.

## How to resume on another laptop

1. Clone or fetch the repository:
   ```bash
   git fetch origin --prune
   ```
2. Check out the current product branch:
   ```bash
   git checkout codex/merchant-command-flow
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
- **Outcome:** hardening code subsequently merged through PR #7; see the later verification milestone.

### 2026-10-30 — Follow-up audit report received

- **Goal:** preserve the remote audit findings without confusing reported results with independently verified results.
- **Changes:** Antigravity pushed `antigravity/handoff-audit` at `b813ac6`, based on `codex/explainer-hardening` at `6ce832d`. The remote commit changes only `docs/BUILD_LOG.md`; it does not add application code.
- **Checks reported:** mobile TypeScript check and Android export passed; Gemini direct call timed out; the report claims backend fact/explainer/fallback behavior passed.
- **Evidence gap:** the command history supplied with that report also lists backend pytest, TestClient smoke, and direct Python smoke attempts exiting with code 1. The report gives no exact successful backend command or output to reconcile those failures. Codex therefore records backend verification as unverified.
- **Outcome:** Codex later ran a reproducible local HTTP smoke check successfully; see the following milestone. PR #9 later merged the corrected verification log into `main`.

### 2026-10-30 — Codex backend and mobile verification

- **Goal:** independently verify the hardening branch after receiving the audit report.
- **Backend:** an isolated temporary SQLite database was seeded and exercised through local Uvicorn plus Python's standard-library HTTP client. `GET /insights/facts?persona=kirana` returned HTTP 200 with 5 facts; `POST /insights/explain` returned HTTP 200, used deterministic fallback without reading or using a Gemini key, and returned the fixed `counter_notice` action. OpenAPI exposed the POST route. **Passed.**
- **TestClient note:** the installed Starlette TestClient could not import because its optional `httpx2` dependency is absent. This is a test-client environment dependency, not an application runtime failure; the HTTP smoke check above exercised the real ASGI server instead. No test dependency was added.
- **Mobile dependencies:** `npm run typecheck` initially could not start because the existing `node_modules` lacked `tsc`. `npm ci` restored the lockfile dependencies without tracked file changes.
- **Mobile checks:** `npm run typecheck` exited 0. `npx expo export --platform android` exited 0 and bundled 706 modules into Hermes bytecode. **Passed.**
- **Dependency note:** `npm ci` reported 8 dependency advisories (5 low, 3 high). `npm audit --omit=dev` also exited 1 and identified high-severity transitive advisories in `deepmerge` and `zod` through Expo tooling. The suggested `npm audit fix --force` would downgrade Expo to 51, so no dependency changes were made. The branch does not change `package.json` or the lockfile; assess these existing advisories separately before release.
- **Limitations:** Gemini live connectivity was deliberately not tested; the fallback was forced so no local key or billable API request was used. Physical-device/LAN demo remains unverified.
- **Next:** continue product development from updated `main`; the dependency advisories are inherited from the Expo dependency tree and are not changed by the hardening PR.

### 2026-10-30 — Confirmed text-command workflow

- **Goal:** turn the Copilot text box from an utterance log into a bounded merchant workflow.
- **Changes:** added a deterministic parser for one supported request at a time: credit, repayment, balance lookup, and stockout observation. The Copilot resolves customer/product aliases through existing APIs, lets the merchant choose among ambiguous matches, previews writes, requires explicit confirmation, uses idempotency keys, and reports the result. Unsupported or incomplete commands do not write. A missing customer may be created only after confirmation of a new-credit preview; missing repayment customers and products are not created automatically.
- **Trust boundary:** this is a fixed-rule demo parser, not LLM command understanding. Stockout confirmation records an observation and leaves physical quantity unchanged. All records remain synthetic.
- **Demo arithmetic:** aligned the quick repayment example with the PRD: ₹500 opening due + ₹50 credit − ₹300 repayment = ₹250 due.
- **Files:** `mobile/src/features/home/parseMerchantCommand.ts`, `mobile/src/features/home/HomeScreen.tsx`, and `mobile/README.md`.
- **Branch:** `codex/merchant-command-flow`, based on `origin/main` `5577f98`.
- **Checks:** parser cases passed for credit, repayment, balance, stockout, mixed-action clarification, and excess decimal places. A local HTTP smoke with temporary SQLite confirmed the balance went from 50000 paise to 55000 after credit and 25000 after repayment; stockout was recorded while on-hand stayed at 12. `npm run typecheck` passed. `npx expo export --platform android` passed and bundled 707 modules.
- **Limitations:** parser supports a narrow set of Hindi/Hinglish/English phrases and does not support voice or arbitrary natural language. Physical-phone UX remains unverified.
- **Next:** rehearse the text commands on the demo phone with a seeded synthetic backend and tune the flow from that run.

### 2026-10-30 — Persisted merchant approval and outcome tracking

- **Goal:** Complete the trustworthy action loop after the merchant reviews a suggestion.
- **Changes:** Added append-only `mock_actions` storage; merchant-confirmed, idempotent `POST /actions/mock`; `GET /actions/latest`; baseline snapshot; scheduled seven-day outcome window; factual outcome status that stays pending until post-approval rows exist. The mobile brief now saves and restores approval and shows baseline/window/status.
- **Branch/base:** `codex/mock-action-outcomes`, based on `origin/main` at `318863e` (PR #10 merged); commit `0893ede` pushed to `origin`.
- **Data truth:** Current synthetic fixture ends on 2026-10-29 and has no post-approval rows. The demo therefore shows a scheduled outcome check; it does not fabricate a lift. If a completed window has no rows, status becomes `insufficient_data`. Any available comparison is observational and does not attribute a change to the mock action.
- **Checks:** `python -m compileall -q app` passed. An isolated SQLite service smoke passed for approval persistence, idempotency replay, latest-action restore, unconfirmed rejection, and mismatched-key rejection. `npm run typecheck` passed. `npx expo export --platform android` passed (707 modules; Hermes bundle exported). `git diff --check` passed.
- **Limitations:** No live offer publishing, live Paytm feed, or production authentication. The post-approval measurement cannot complete on the current fixed historical fixture.
- **Next:** Verify API idempotency/confirmation and mobile build, then move to a user-facing voice input slice or physical-device demo.

### 2026-10-30 — Sarvam voice transcription into confirmed command flow

- **Goal:** Let a merchant speak a short Hindi/Hinglish request, review the transcript, and use the existing safe command path.
- **Changes:** Added `POST /speech/transcribe` using Sarvam `saaras:v4` in transliteration mode with merchant/product keyterms; credentials stay server-side and short audio is not persisted. Added Expo Audio microphone recording with permission text and a 20-second stop, cache-file deletion after upload, transcript language label, and editable transcript in the command input. Sending a transcript enters the existing deterministic parser; any write still requires the normal preview/confirmation. Voice source is carried into ledger/customer/stockout records.
- **Branch/base:** `codex/sarvam-voice-input`, based on `codex/mock-action-outcomes` at `5a990b5` (which itself includes main through `318863e`); commit `91f62cc` pushed to `origin`.
- **Checks:** `python -m compileall -q app` passed; FastAPI OpenAPI includes `/speech/transcribe`; mocked Sarvam adapter check confirmed multipart fields, server-side key header, and response mapping without a live API request. A parser check confirmed a transliterated `Raju bhai ka 50 rupaye udhaar likh do` becomes a ₹50 preview for the exact `Raju bhai` alias. `npm run typecheck` passed. Android Expo export passed (722 modules). `git diff --check` passed.
- **Not yet verified:** Actual Sarvam account/credential connectivity and recording/transcription on a physical phone. No live API call was made to avoid consuming quota; type/build checks do not prove microphone or provider behavior on-device.
- **Limitations:** The fixed parser supports a narrow Romanized Hindi/Hinglish command set and numeric amounts; unclear or unsupported transcripts stop for manual correction. Recording cap is 20 seconds in the app; the backend also caps uploads at 12 MB. Text remains available if voice is unavailable.
- **Next:** Push this branch, then have the team try one spoken command on the demo phone with the backend's `SARVAM_API_KEY` configured. Use the observed transcript to fix recognition/parser issues before adding voice responses or broad language understanding.

### 2026-10-30 — Local browser preview

- **Goal:** Let the team review the actual app screens on the laptop browser as well as Expo Go.
- **Changes:** Added Expo Web runtime dependencies (`react-dom`, `react-native-web`), local-origin CORS middleware configurable by backend-only `MUNIM_CORS_ORIGINS`, and setup instructions. The preview ran at `http://localhost:8081/` against an isolated synthetic SQLite database; the business brief and pending action card rendered using deterministic Gemini fallback.
- **Checks:** CORS preflight for `http://localhost:8081` passed. Browser showed the synthetic brief, evidence rows, caveats, and the unapproved “Approve & Track for 7 Days” action. Typecheck was run; web bundle compile completed, but static web export stopped while processing existing 1×1 placeholder PNG assets with invalid CRCs (`icon.png`, `adaptive-icon.png`, `splash-icon.png`, and `favicon.png`). The development server renders successfully.
- **Limitations:** This laptop preview does not verify Android microphone behavior or Sarvam account connectivity. The four tiny PNG assets are existing placeholders and need replacement before a clean static web export or release build.
- **Next:** Keep the browser preview available for review, then run the voice flow on a physical phone.

### 2026-10-30 — Rupee amount normalization in merchant commands

- **Goal:** Make common Indian currency formatting work consistently in typed and transcribed commands without weakening the existing confirmation flow.
- **Changes:** `mobile/src/features/home/parseMerchantCommand.ts` now accepts grouped amounts such as `₹1,000` and `₹1,00,000`, validates comma placement before conversion to integer paise, and normalizes Devanagari digits (`०१२३...`) before intent and amount parsing. Malformed grouping still returns a clarification instead of being guessed. `mobile/README.md` now describes the implemented Sarvam STT path and parser limits instead of the stale “voice not included” status.
- **Branch/commit:** `codex/sarvam-voice-input`, commit `087c6b1` (`fix: parse grouped and Devanagari rupee amounts`), pushed to `origin`.
- **Review:** Diff reviewed; `git diff --cached --check` passed before commit. No automated tests or live provider calls were run in this step.
- **Safety:** The parser only creates a preview. Existing merchant confirmation, backend validation, idempotency, and ledger balance rules remain in force.
- **Limitations:** Spoken number words such as “pachaas” are not inferred. Sarvam recording/transcription still needs a real-device and live-credential check; no Paytm production integration is claimed.
- **Next:** Run an end-to-end merchant command rehearsal on a phone, capturing actual Sarvam transcripts and checking exact customer/product resolution and preview values before confirming any write.

### 2026-10-30 — Browser voice upload and provider connectivity diagnosis

- **Goal:** Fix the browser voice upload shape and identify why speech, Gemini, and MongoDB appeared disconnected.
- **Changes:** `mobile/src/api/ledgerClient.ts` now reads the browser recording URI as a real `Blob`, derives its MIME type (including removing codec parameters), and sends WebM with a `.webm` filename where appropriate. Native uploads retain the React Native file descriptor. `HomeScreen.tsx` displays the specific recording/transcription error inline and releases browser blob URLs after use.
- **Local secret configuration:** Sarvam was present in the separate local work checkout but missing from this checkout's `.env`; only the Sarvam entry was copied into this checkout's ignored `.env`. No credential was added to Git or printed. The backend resolver now finds it.
- **Connectivity:** A synthetic tone reached Sarvam directly (HTTP 200) and through local `POST /speech/transcribe` (HTTP 422 “No speech detected”), confirming auth, endpoint, and backend forwarding; a tone is intentionally not treated as successful speech recognition. MongoDB Atlas authenticated `ping` succeeded. Gemini returned HTTP 401 for the configured key (“API key not valid”); the facts flow will continue using deterministic fallback until that key is replaced. The app itself currently uses SQLite and does not use MongoDB.
- **Checks:** `npm run typecheck` passed. No real user audio was recorded or transmitted. No browser microphone permission was granted by Codex.
- **Limitations:** A real spoken recording from the browser or phone is still needed to verify audio capture and transcription end to end. A browser must be allowed microphone access; an in-app browser may restrict that permission. Gemini remains unconfigured effectively until a valid key is supplied.
- **Next:** Reopen/reload the local browser preview, allow microphone access if prompted, record one short spoken command, and confirm the returned transcript appears in the editable input. Then test the same flow on the Android device. Replace the invalid Gemini key separately if Gemini summaries are needed.

### 2026-10-30 — Normalize browser recording MIME metadata

- **Goal:** Resolve the reported `415 Unsupported audio format` error from browser voice uploads.
- **Cause:** Web `FormData` uses the MIME type stored on the Blob itself; deriving a normalized type for the filename alone did not remove codec parameters from that Blob. Browser media recorders may also label audio-only WebM as `video/webm` or `application/octet-stream`.
- **Changes:** The mobile client now wraps browser audio in a new Blob with a normalized supported audio MIME type. The backend strips MIME codec parameters, normalizes `video/webm`, and infers the media type from a known filename extension only when the upload advertises a generic binary type. Unsupported types still fail closed with a clearer error mentioning WebM.
- **Files:** `mobile/src/api/ledgerClient.ts`, `backend/app/api/speech.py`, and `docs/contracts/backend-api-v0.md`.
- **Checks:** Mobile `npm run typecheck` and backend `python -m compileall -q app` passed. A focused in-memory route check confirmed `audio/webm;codecs=opus`, `video/webm`, and `application/octet-stream` plus a `.webm` filename all normalize to `audio/webm` before forwarding. No real recording was captured in this check.
- **Runtime:** Restarted the local Uvicorn process so it loaded the updated route; `/health` remains available on port 8000. The Expo Web dev server remains on port 8081.
- **Next:** Retry a short real recording in the browser. If upload gets past validation, Sarvam should return either a transcript or a distinct “no speech detected” response. Report the exact new message if it still fails.

### 2026-10-30 — Strip transcript punctuation before exact customer matching

- **Finding:** Recent local backend logs show the speech endpoint returning HTTP 200 repeatedly, followed by a customer lookup query containing trailing punctuation (`Raju bhai .`). The preview database has no voice-tagged business events, so those attempts did not post a voice-originated ledger action.
- **Change:** `cleanCustomerQuery` now removes sentence periods and common Indic punctuation before exact-match lookup. This keeps recognized sentence-ending punctuation out of customer/product names while leaving the merchant's original utterance available for the preview/audit path.
- **Branch/commit:** `codex/sarvam-voice-input`, commit `63e6bff` (`fix: trim punctuation from voice customer names`), pushed to `origin`.
- **Checks:** Mobile TypeScript typecheck passed; `git diff --check` passed.
- **Next:** Retry a read-only voice command first. Confirm the editable transcript is clean and the customer lookup resolves before trying a write command; any ledger change still requires explicit confirmation.

### 2026-10-30 — Current delivery phases reconciled with implementation

- **Goal:** Make the remaining work clear after completing the main backend and mobile logic slices.
- **Change:** Replaced the archived five-phase draft with a live delivery tracker in `docs/HACKATHON_EXECUTION_PLAN.md`: merchant command/ledger, shop memory, mock payment reconciliation, merchant growth brief/action, and integrated demo readiness. Each phase now has an explicit status and evidence-based exit gate. Plan commit `7f46bff` is pushed to `codex/sarvam-voice-input`.
- **Current phase:** Phase 5, integrated demo readiness. The immediate acceptance item is one clean read-only voice command after the punctuation fix; a voice-originated write has not yet been confirmed in the local demo database.
- **Limitations:** Gemini is still unauthenticated and the app uses deterministic fallback; MongoDB is not integrated into this SQLite prototype; no real Paytm feed is connected.
- **Next:** Finish the voice acceptance gate, then rehearse the remaining flows against a clean synthetic seed and record any failures as small follow-up tasks.

### 2026-10-30 — Read-only voice request verified end to end

- **Evidence:** Local backend logged `POST /speech/transcribe` HTTP 200, `GET /customers/resolve?query=Raju bhai` HTTP 200, and `GET /ledger/customers/{id}/balance` HTTP 200 for the user's latest voice attempt.
- **Outcome:** Sarvam transcript, punctuation cleanup, exact alias resolution, and read-only balance retrieval all worked. The synthetic database remains unchanged by this read; it still has one text-sourced ₹50 credit and zero voice-originated ledger events.
- **Phase status:** Phase 1's read-only voice gate is passed. The remaining gate is one merchant-previewed and confirmed synthetic voice write with correct `source_channel=voice` attribution. Phase 5 remains in progress.
- **Next:** If the user wants to complete the voice-write gate, use a small synthetic credit command, inspect the preview, and confirm it only after verifying the customer and amount. Then check the persisted event source and balance.

### 2026-10-30 — Spoken Hindi rupee amount parsing

- **Finding:** Sarvam can transliterate a spoken numeric amount as a Hindi number word such as `das`; the existing parser only extracted digits, so it could not turn that transcript into an amount.
- **Change:** `parseMerchantCommand.ts` now converts common Hindi number words from 0–99 and simple `sau`/`hazaar`/`lakh` phrases to integer rupees only when they are followed by an explicit currency unit (`rupaye`, `rupees`, etc.). Grouped numeric amounts and Devanagari digits remain supported. A number word without a currency unit requests clarification; names such as `Raju Das` remain intact. The parser's clarification text and `mobile/README.md` were updated.
- **Branch/commit:** `codex/sarvam-voice-input`, commit `336e465` (`feat: parse spoken Hindi rupee amounts`), pushed to `origin`.
- **Checks:** `npm run typecheck` passed. A focused parser smoke check returned `credit / Raju bhai / 1000 paise` for “das rupaye”, `repayment / Raju bhai / 25000 paise` for “do sau pachaas rupaye”, preserved “Raju Das” as a customer query, and requested clarification when `das` lacked a rupee unit.
- **Safety:** This produces a preview only; financial writes still require merchant confirmation and backend balance validation.
- **Next:** Retry the same voice credit command using “das rupaye”; inspect the customer and ₹10 amount in the preview before confirming.

### 2026-10-30 — Phase 5 clean seed and core-flow rehearsal

- **Direction:** Per user instruction, stop iterating on Hindi voice recognition for now. Keep text as the reliable input path; voice remains optional and its number transcription is documented as inconsistent.
- **Voice audit:** The previous preview database contained a confirmed voice-originated credit of ₹10 (`source_channel=voice`) and two text-originated ₹50 credits. The read-only balance request also succeeded. That prior database was preserved; it was not cleared or overwritten.
- **Seed fix:** `backend/seed_demo.py` previously created its rows but exited with `UnicodeEncodeError` when printing `₹` on a Windows cp1252 console. The script now reconfigures stdout to UTF-8 where supported (code commit `580b4e1`). Re-running the idempotent seed succeeded and reported Raju opening due ₹500 and Maggi stock 12 packs.
- **Current preview state:** The backend on port 8000 now uses the separate temp database `munim-phase5-clean-demo-2026-10-30.sqlite3`; the previous preview database remains intact. Startup seeded the synthetic payment fixture. Read-only HTTP checks confirmed Raju resolution/balance, Maggi resolution/stock, empty initial payment-review queue, and local health.
- **Isolated flow rehearsal:** On a separate scratch database, verified ₹500 opening due → confirmed ₹50 credit → ₹300 successful mock payment enters review → merchant-confirmed allocation → ₹250 due. Verified stockout leaves 12 packs unchanged, a confirmed physical count sets stock to 10, insights return 5 facts, deterministic fallback is available, and a confirmed mock action is scheduled. Nine timeline events were recorded in the scratch scenario.
- **Phase status:** Core service-level Phase 5 rehearsal passed. Browser/phone UI rehearsal and phone-to-laptop networking remain.
- **Next:** Rehearse the text command, inventory count, payment review/allocation, insight brief, and mock action in the browser or on the phone using the clean seeded preview. Keep voice optional.

### 2026-10-30 — Browser command NLP assist (Gemini-backed, preview-only)

- **Goal:** Continue the browser product flow while pausing further microphone/STT tuning, and let the app understand a wider range of typed requests (or an existing transcript) without allowing AI to make writes.
- **Changes:** Added `POST /commands/interpret` and a Gemini-backed interpreter that returns only a bounded intent plus exact entity and amount spans quoted from the utterance. The browser calls it only when the deterministic parser says the command is unsupported. The response is re-parsed locally, then continues through exact customer/product resolution, existing preview, and explicit confirmation.
- **Synthetic NLP examples:** Added English and Hinglish patterns for credit, repayment, balance, stockout, missing amounts, ambiguous amounts, and mixed intents. These examples are prompt-only guidance; they do not train/fine-tune Gemini and do not contain merchant history. No ledger rows or entity IDs are sent to the model. When Gemini is enabled, only the utterance is sent to Google's API.
- **Fallback and safety:** Without a working Gemini credential or on provider/validation failure, the endpoint returns a controlled clarification/unavailable response. Amount spans must be copied from the original and include an explicit rupee marker/unit; the deterministic parser still performs any supported amount normalization. Model-suggested entity strings must appear verbatim in the utterance. No endpoint write was added.
- **Current provider state:** Existing local Gemini credential previously returned HTTP 401; the live model branch is therefore unverified and deterministic fallback remains expected until the credential is replaced. The default model ID remains configurable via backend-only `GEMINI_MODEL` (default `gemini-3.8-flash`).
- **Files:** `backend/app/domain/models.py`, `backend/app/main.py`, new `backend/app/api/commands.py`, new `backend/app/services/command_nlp.py`, `mobile/src/api/ledgerClient.ts`, `mobile/src/features/home/HomeScreen.tsx`, `docs/contracts/backend-api-v0.md`, `docs/HACKATHON_EXECUTION_PLAN.md`.
- **Checks:** Mobile TypeScript typecheck passed. Backend `compileall` passed. `git diff --check` passed. No live Gemini call was made during this implementation step.
- **Next:** Confirm the new clarification/fallback message in the browser using an unsupported typed phrasing. Once a valid Gemini key is configured, verify one benign balance query and one amount-bearing command end to end, inspecting the preview and cancelling before any write if desired.

### 2026-10-30 — Gemini key refresh check and browser payment-review readiness

- **Gemini configuration:** Confirmed a non-placeholder `GEMINI_API_KEY` is present in the ignored root `.env` without printing or committing it. Restarted the local backend without an environment override so it reads that value. Two browser-NLP route attempts returned controlled fallback; a direct minimal Gemini request returned HTTP 503. The key is being loaded, but successful Gemini inference is not verified yet.
- **Read-only browser-data audit:** Local demo database currently reports Raju due ₹250, Maggi stock 12, seven timeline events, and one successful unmatched mock payment of ₹300 with reason `payer_token_missing`.
- **Payment behavior:** Manual allocation of that ₹300 payment was rejected with HTTP 409 because it exceeds the customer's current ₹250 due. This is expected balance protection; no repayment was posted. Updated the browser error mapping to show both values and state that no ledger entry was created. Changed the next demo payment button to add a synthetic ₹200 payment so it can fit the current ₹250 due when manually confirmed.
- **Next:** Refresh the browser and use the new ₹200 mock payment for the eligible manual-allocation path. Keep the old ₹300 item unresolved as an example of an over-balance payment being held safely. Retry Gemini later when the provider stops returning 503.

### 2026-10-30 — Browser payment review verified; Phase 5 moved to inventory and growth brief

- **Browser evidence:** The latest backend timeline records a merchant-confirmed ₹300 payment allocation (`REPAYMENT_POSTED`), the payment review queue is empty, and Raju's balance is ₹250. This matches the demo arithmetic of ₹550 due before allocation and ₹250 after; the previous over-balance allocation attempt had no ledger effect.
- **Current shop state:** Maggi stock is 12 packs. A physical count is in the timeline, but there is no stockout-observation event yet. The latest actions lookup has no approved mock growth action.
- **Next Phase 5 work:** Browser walkthrough of the inventory distinction (observe stockout, verify stock remains 12, then confirm a physical count), followed by facts brief review and merchant-approved mock action. Phone-to-laptop access is still unverified.
- **Gemini responsiveness:** Both the command interpreter and facts explainer now cap upstream requests at 8 seconds before deterministic fallback. Recent command calls timed out; a direct minimal Gemini request returned HTTP 503. The valid-key inference path remains unverified; no secret was printed or committed.

### 2026-10-30 — Eight-second Gemini fallback verified

- **Facts explainer:** `POST /insights/explain` returned HTTP 200 with `fallback_used=true`, 4 evidence IDs, and the bounded `counter_notice` action type in 8.6 seconds.
- **Command NLP:** An unsupported synthetic balance phrasing returned HTTP 200 with `status=unavailable`, `provider_used=fallback`, and `fallback_used=true` in 8.3 seconds.
- **Conclusion:** Browser-facing insights and command routes complete safely with the updated key present even while the upstream model stalls. The request latency is bounded near the 8-second timeout. Gemini-generated output remains unverified.
- **Next:** In the browser, open Inventory, look up Maggi, record a stockout observation and verify stock remains 12; then enter and confirm a physical count of 10. After that, load the merchant brief and approve one mock action, verifying its “not published” label and scheduled outcome.

### 2026-10-30 — Browser inventory acceptance check not passed yet

- **Observed after user reported completion:** Maggi's current on-hand quantity is 23 packs; the latest timeline event is `STOCK_COUNT_RECORDED` with source utterance `Physical count: 23`. The timeline has no `STOCKOUT_OBSERVED` event.
- **Result:** The intended stockout-then-count check (stock stays at 12 after observation, then becomes 10 after the entered count) is not verified. No data was changed by this audit.
- **Next:** Repeat the stockout observation action, verify the quantity remains unchanged, then enter the intended physical count and confirm. Proceed to the growth brief/mock action after the inventory gate is clear.

### 2026-10-30 — Follow-up inventory audit

- **Read-only result:** Current Maggi on-hand quantity is 0 packs. Timeline now includes another `STOCK_COUNT_RECORDED` event with source utterance `Physical count: 0` (following the earlier count of 23 and seed count of 12).
- **Stockout status:** No `STOCKOUT_OBSERVED` event exists yet. Entering a physical count of zero sets on-hand to zero; it does not record the separate stockout observation.
- **No corrective write performed:** The audit did not change stock. Confirm the intended count before correcting it; for the demo distinction, record a stockout observation separately and verify that action itself leaves on-hand unchanged.

### 2026-10-30 — User confirmed zero inventory count is intentional

- The user confirmed the physical count of 0 packs for Maggi was intentional and reported the flow is working as expected.
- No corrective inventory write was made. The browser count flow is accepted; the distinct stockout-observation action remains unverified in this run.

### 2026-10-30 — Merchant brief audit and editable mock action

- **Read-only brief check:** Five synthetic facts and their evidence IDs load. The facts-only explanation returned a deterministic fallback after the Gemini timeout: four evidence IDs and the bounded `counter_notice` action type. The latest-action endpoint is empty; no merchant approval was created by this audit.
- **Merchant control improvement:** The browser action card now has an editable 240-character action field. Before approval, the merchant can change the suggested text; after approval, the card displays the exact saved text and the mock-only scheduled observation. Approval still requires the merchant to click the explicit button.
- **Default counter notice:** The server-owned fallback draft is now customer-facing copy: “Ask us about this week's in-store offers. UPI accepted.” This is editable, not automatically sent or published.
- **Checks:** Mobile TypeScript typecheck passed. The facts/explanation endpoint returned HTTP 200 with deterministic fallback and no mutation. No mock action has been approved yet.
- **Next:** In the browser, open “Aaj kaisa raha?”, edit or keep the notice, and click “Approve & Track for 7 Days (Mock).” Then verify the card says nothing was published and the outcome is scheduled. Phone/LAN rehearsal remains after that.

### 2026-10-30 — Merchant-approved growth action verified; clean browser runbook added

- **Browser-backed result:** `GET /actions/latest?persona=kirana` returns `APPROVED_MOCK`, `mock_only=true`, action type `counter_notice`, exact saved text `Ask us about this week's in-store offers. UPI accepted.`, and `outcome_status=scheduled`. The seven-day observation window is recorded and the backend says the action was not published.
- **Baseline:** The approval captured 209 synthetic transactions as its baseline count. The action comparison remains observational.
- **Runbook:** Added `docs/BROWSER_DEMO_WALKTHROUGH.md` with fresh-database PowerShell commands, expected demo arithmetic, browser flow, and truthful limitations. It uses a timestamped temp DB path and does not delete the current preview data.
- **Payment input:** Changed the mock payment amount from a fixed value to a positive rupee amount with up to two decimals. This allows the clean walkthrough to use ₹300 against the ₹550 due, while an already-modified demo can choose a smaller eligible amount.
- **Next:** Final environment acceptance: verify start commands, physical phone/LAN connectivity, then run the complete sequence from a new synthetic seed. Stockout observation remains a separate optional browser check; current Maggi count of zero is intentional.

### 2026-10-30 — Voice-ready merchant commands and detailed summaries

- **Request:** Expand the project beyond the growth brief so the merchant can check customer dues and inventory by voice, add a customer such as Rajju from speech, report stockouts/count stock, and get a detailed explanation of payment and timeline activity.
- **Command path:** Existing Sarvam transcript review and Send action now feed the same deterministic parser and Gemini assist as typed input. Added customer creation, latest recorded stock lookup, physical count, payment summary, and timeline summary intents. Voice is not permitted to bypass transcript review, exact entity resolution, previews, or explicit confirmation.
- **Customer safety:** `add new customer Rajju Sharma` previews the exact spelling; confirming creates only a customer profile. It does not create debt. Existing exact names are not duplicated; ambiguous aliases require selection.
- **Inventory behavior:** Stock lookup is read-only and clearly described as the latest recorded count, not a live sensor. Physical count requires a preview and confirmation; stockout observation remains a separate confirmed event and does not mutate quantity.
- **Payment and activity summaries:** Added read-only `GET /events/summary`, aggregating ledger credit/repayment separately from synthetic payment events by status, unresolved successful events, inventory events, and recent payment/timeline details. All summary output identifies the complete recorded demo history as synthetic; “today” does not mean a live daily Paytm feed.
- **Limitations:** Gemini remains intermittent (recent upstream requests returned HTTP 503/timeouts); deterministic common phrasing works without it. Voice spelling/number recognition is only as reliable as the transcript and must be reviewed. No Paytm production feed, MongoDB persistence, or live stock sensor is implied.
- **Checks:** Mobile TypeScript typecheck passed; backend Python `compileall` passed. `GET /events/summary` returned HTTP 200 against the preserved demo database (17 recorded events, 1 mock payment event, 2 posted repayments, 0 open reviews); no records were changed by this read-only check. Browser/device acceptance for new voice intents is still pending.
- **Files:** `backend/app/api/events.py`, `backend/app/domain/models.py`, new `backend/app/services/activity_summary.py`, `backend/app/services/command_nlp.py`, `mobile/src/api/ledgerClient.ts`, `mobile/src/features/home/HomeScreen.tsx`, `mobile/src/features/home/parseMerchantCommand.ts`, `mobile/src/features/timeline/TimelineScreen.tsx`, and this phase/runbook/contract documentation.

### 2026-10-30 — Next phases N0/N1: audit, migrations, supplier payable khata

- **Audit:** `docs/NEXT_PHASES_AUDIT.md` records the starting tree (`codex/sarvam-voice-input` @ `5bec501`, clean), architecture, constraints, endpoint plan, risks, and the acceptance-to-test checklist. `.env` is ignored; only placeholder `.env.example` files are tracked; no database files are tracked. A local ignored root `.env` was created from the template (no values entered).
- **Migrations:** New `backend/app/services/migrations.py` adds a `schema_migrations` table and ordered additive migrations. Migration 1 is the original schema (idempotent), so existing databases upgrade in place. Migration 2 adds `suppliers`, `supplier_aliases`, and append-only `supplier_payable_entries`.
- **Supplier khata:** New supplier service and `/suppliers` routes: create (confirmed + idempotent), list, exact resolve, derived balance with type breakdown, entry history, merchant-recorded payments (no transfer), and debit-note/adjustment entries. Decreases above current due return `409`. Contact phone is masked in all responses and never put in event summaries.
- **Seed:** `seed_demo.py` adds synthetic Sharma Distributors and Gupta Dairy (zero payable) and Amul Taaza (packet) / Dahi (cup) products. Two consecutive runs against a temporary DB produced the same IDs.
- **Checks:** `python -m pytest -q tests` → 8 passed (temp DB per test; no live providers).
- **Limitations:** Single demo shop; no authentication. Supplier payments are records only.

### 2026-10-30 — Next phases N2/N3: invoice photo proposals and atomic posting

- **Migration 3:** `product_unit_conversions`, `intake_proposals` (versioned working drafts), append-only `intake_proposal_revisions`, `stock_receipts` (unique per supplier + normalized invoice number), and append-only `stock_receipt_movements`. No existing table was altered; on-hand is now physical-count deltas plus receipt movements.
- **Intake (N2):** `POST /invoices/proposals` validates the actual image bytes (format sniffing, dimensions, size), calls a pluggable extraction provider (`gemini`/`fake`/`none`), and converts untrusted output to a draft with deterministic money/quantity parsing. Drafts carry per-field confidence, exact product/supplier matching with candidates, unit/conversion resolution, line and invoice arithmetic checks, and duplicate signals. A provider failure returns an empty manual draft. Image bytes are never stored (a test checks that the DB file has no PNG signature).
- **Posting (N3):** `POST /invoices/proposals/{id}/confirm` requires the current version and content hash, revalidates on the server, requires an explicit `paid_now_paise`, then appends the receipt, movements, `INVOICE_CREDIT` payable, and events in one transaction. An injected failure after the movements and payable were inserted left zero rows in all three tables.
- **Checks:** `python -m pytest -q tests` → 36 passed (temp DB per test; fake/failing providers only).
- **Limitations:** Live Gemini vision has not been exercised in this run. The provider path is covered with fakes, and recent live Gemini calls returned 503/timeouts. Quantities are whole numbers in the product's base unit. Proposal drafts are working state (updated in place) with an append-only revision history.
