# Continuous Team Workflow

**Current working agreement:** Parth, Priyanshu, Rachit, Codex, and Antigravity can work in parallel on separate, reviewable tasks. Do not wait for five numbered phases to finish before integration. Keep `main` usable by pushing small changes and merging reviewed PRs as each task is ready.

## Product decisions already made

- **Product names:** Munim-AI is the shopkeeper-facing copilot; KiranaOS is its structured business-memory layer.
- **Track:** Merchant Growth AI.
- **Data:** synthetic/demo data only; no live Paytm integration is claimed.
- **Provider access:** use provider-neutral mocks until API credentials and permitted models are confirmed.
- **Backend direction:** FastAPI + SQLite for a single synthetic shop; money is stored as integer paise.
- **Mobile direction:** Expo + React Native + TypeScript, Android-first; text input stays available even if voice is down.
- **Trust rules:** AI proposes typed actions; backend validates; merchant confirms; ledger is append-only; balances are derived; ambiguous payment matches go to review.
- **Demo arithmetic:** Raju starts at ₹500 due; confirmed ₹50 credit makes ₹550; a matching ₹300 repayment leaves ₹250.

These decisions are enough to keep moving. Avoid reopening them unless the team finds a concrete implementation blocker or organizer rule that changes the constraints.

## Current remote state (checked 30 October 2026)

- `main` has the initial PRD/workflow docs.
- `codex/phase-1-contracts` has the contracts and backend health scaffold.
- `codex/phase-2-ledger-api` adds customer/alias, credit/repayment, derived-balance, and idempotency work on top.
- `codex/inventory-timeline` adds confirmed physical stock counts, separate stockout observations, and a read-only append-only activity timeline (latest checkpoint `3b77e9f`).
- `codex/business-facts` adds the deterministic synthetic facts endpoint, latest checkpoint `ae2d84d`; it is based on `codex/inventory-timeline`.
- `codex/payment-review` adds mocked payment intake, exact synthetic payer mapping, safe automatic allocation, and a merchant-confirmed review allocation path; latest checkpoint `485206e`, based on `codex/business-facts`.
- No Antigravity branch was visible on GitHub at the last fetch. Its changes may still be local; Codex cannot inspect or integrate unpushed files.

Next time you resume or ask Codex to check progress, fetch the remote first and inspect branch tips/PRs. Frequent remote commits let both machines fetch the same work. Do not use force-push to overwrite another teammate's branch.

## Parallel ownership

| Workstream | Primary owner | Own these paths | Coordinate through |
|---|---|---|---|
| Backend/data integrity | Priyanshu + Codex | `backend/`, backend API docs | Contracts in `docs/contracts/`; review ledger changes together. |
| Mobile app | Rachit + Antigravity | `mobile/` | Use mock responses first, then integrate against `docs/contracts/backend-api-v0.md`. |
| AI, language, voice | Parth | Future `backend/app/ai/` or a separate `backend/app/interpretation/` module | Command proposal and facts contracts; keep credentials local. |
| Data/demo story | Priyanshu + Rachit | `data/synthetic/`, demo assets | Keep scenario manifest and expected arithmetic current. |
| Integration and judge story | All | Root docs and app entry points | Small PR review; one agreed source of truth for claims. |

Do not let two people edit the same file at the same time. If a shared contract must change, one owner proposes the change, pushes it, and tells everyone the commit hash; other work fetches that branch before using the new shape.

## Git loop: continuous, task-sized changes

1. **Fetch before starting or resuming:** `git fetch origin --prune`; check the current branch and working tree before editing.
2. **Use one short-lived branch per task**, named for owner and task where useful, e.g. `antigravity/mobile-shell`, `rachit/mobile-command-flow`, `parth/intent-parser`, `codex/stockout-api`, `priyanshu/payment-review-queue`.
3. **Keep work isolated by path.** The mobile owner can use mock data while backend work proceeds. Avoid editing root config, contracts, or shared schema files without coordination.
4. **Commit as soon as a coherent, safe unit exists**—a small endpoint, screen, schema update, or fix. Push that branch to GitHub so the other laptop can fetch it. During active work, push at least at natural checkpoints (roughly every 30–60 minutes), not only at the end of the day.
5. **Open/update a PR early** to `main` when the task is independently reviewable. Keep the PR small and keep pushing commits to the same source branch; the PR updates automatically.
6. **Review and merge continuously.** Another teammate reviews; the owner responds; merge after the PR is understandable and its stated checks/manual steps pass. Delete the branch after merge and start the next task from latest `main`.
7. **For dependent work**, fetch the branch that contains the dependency. Prefer waiting for the small dependency PR to merge. If work must proceed before merge, make the dependency explicit in the PR and do not force-push or silently change its base.
8. **Before a demo checkpoint**, pull latest `main`, launch both services, and rehearse the current integrated path. If a branch is not ready, it remains isolated; do not break the demo branch for unfinished work.

Use the repository's [PR template](../.github/pull_request_template.md). Each PR should state the behavior changed, files owned, exact verification performed, screenshot/recording for UI, and known gaps. Do not claim verification that was not run. No long-lived `develop`, `phase-1`, or `phase-2` integration branch is needed once the current bootstrap branches are merged.

## How Codex and Antigravity coordinate

- Antigravity pushes its branch and reports the branch name plus latest commit SHA. The user can paste that SHA/PR URL here; Codex can fetch and review the exact remote state.
- Codex pushes its own task branch and gives the branch/commit/PR link. Antigravity can fetch it on its machine.
- Codex cannot see Antigravity's local unsaved or unpushed changes and cannot continuously poll the friend's laptop. GitHub is the shared handoff point; ask for a fetch/review after a push or share the branch URL.
- Keep one person responsible for final integration during a demo rehearsal. Do not have both tools edit the same file or commit directly to the same branch.
- Do not add credentials, real transaction exports, customer contact details, or raw voice recordings to Git. Use `.env.example` placeholders only.

## Decisions still to confirm (not blockers for current work)

1. Confirm Parth, Priyanshu, and Rachit all have write access to the GitHub repository.
2. Confirm which Android phone will run Expo Go and that the laptop/phone can share a network for the demo.
3. Confirm Sarvam/LLM access when the team is ready to implement those adapters; until then use mocks and text.
4. Confirm event rules and judge criteria from organizer materials; the current brief is team-supplied.

## Next independent tasks

- **Antigravity:** finish/push the mobile shell branch; report SHA and PR URL. Keep to `mobile/` and avoid the backend/contracts files.
- **Codex:** next review/integrate the mobile and language branches against the latest backend contracts. Do not claim production payment reconciliation or live Paytm integration.
- **Parth:** choose the actual LLM provider/available credits and keep the request/response behind an adapter; voice can remain mocked until access is verified.
- **Team:** open and merge the current contract/backend PRs in an order that gives mobile a stable API contract. A single combined bootstrap PR is acceptable if the Phase 1 and Phase 2 branches are still unmerged.
