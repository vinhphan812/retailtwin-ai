# RetailTwin AI — Final Submission Validation Checklist

**Issue:** tracks completion of all pre-submission requirements for the AI Builder Google 2026 competition.
**Status:** `OPEN — NOT READY`
**Owner:** maintainers
**Last updated:** 2026-10-22

> **Current evidence boundary:** G03–G06 were executed offline at
> `c20fb073e4ab919fdced85b7285751e38090cbe3` and retained under
> `docs/evidence/submission-gates/2026-10-22T1556Z/`. They remain 🟡 until the
> eventual final submission SHA is independently executed, has green CI, and is
> deployed/verified where a deployment claim is required.

---

## 0. Glossary — How to Read This Checklist

### Evidence column conventions

Every **Evidence Required** entry is one of:

| Prefix | Meaning |
|--------|---------|
| *(static reference)* | An authored document or ADR — a fixed statement of intent or design. Not executable proof. |
| `tests/…` — live run required | A test file; must be **executed** to produce proof. Evidence is the JSON artifact or exit code, not the filename alone. |
| `scripts/…` — live run required | A shell script; must be **executed** to produce proof. |
| `Gate …` | A named gate harness (e.g. `G03`, `G04`); must be **run** and the evidence matrix recorded. |
| `smoke …` | A CI/CD smoke-test job; must **succeed at the submission SHA** for the entry to be considered verified. |
| `ci.yml / …` | A CI workflow job name; must **pass at the submission SHA** to be considered verified. |

> **Key distinction — authored evidence vs. verified evidence.** A static reference (ADR, fixture path, code-review citation) is a human-authored statement. It is accurate as of the SHA it was written at, but it is **not** automatically re-verified. It becomes *verified evidence* only when the linked artifact (test run, smoke job, gate matrix) is executed at the submission SHA and produces a green result.

### Status column key

| Emoji | Meaning |
|-------|---------|
| 🟢 | Verified — live execution at the submission SHA produced a green result. |
| 🟡 | Pending — static reference exists; live execution or human review has not confirmed it for the submission SHA. |
| 🔴 | Missing or failed — no evidence exists, or a live run has failed. |
| ⚫ | Does not apply. |

### CI status is not reviewed status

A passing CI workflow at one SHA does **not** mean the code is reviewed. CI proves automated checks pass; review proves human judgement was applied. This checklist treats:
- **CI passing** → green 🟢 only when the job ran at the specific submission SHA.
- **Human review** → tracked separately; not in scope for this checklist.

> **⚠ CI status at a different SHA is not current evidence.** The CI column reflects the last recorded run, not necessarily the current `HEAD`. Always re-run CI at the submission SHA before marking any C-entry 🟢.

---

## 1. Required Features — All Must Be Working

### 1.1 Autonomous Control Loop (OBSERVE → DETECT → INVESTIGATE → PLAN → SIMULATE → GUARD → ACT → VERIFY)

| # | Feature | Evidence Required | Status |
|---|---------|-------------------|--------|
| F01 | `POST /events` accepts `sale.completed` without human prompt | *(static reference)* `tests/e2e/gates/g03_autonomous_gate.py` — run required to produce proof | 🔴 NOT VERIFIED |
| F02 | Observer starts exactly one investigation per accepted sale | *(static reference)* Gate G03 evidence JSON — run required | 🔴 NOT VERIFIED |
| F03 | Investigator collects versioned EvidenceBundle through allow-listed tool registry | *(static reference)* ADR 0011; `FakeLlmProvider` tools fire — live run required | 🔴 NOT VERIFIED |
| F04 | Planner proposes 2–3 bounded candidate actions bound to evidence | *(static reference)* Gate G03 evidence — run required | 🔴 NOT VERIFIED |
| F05 | Simulator clones Live Twin and scores candidates with `simulation-kpi-v1` | *(static reference)* Gate G05 evidence — run required | 🔴 NOT VERIFIED |
| F06 | Decision Context Guard (6 gates) returns `ALLOW` / `DENY` / `REFRESH_REQUIRED` / `HUMAN_REVIEW` | *(static reference)* Gate G04 evidence — run required | 🔴 NOT VERIFIED |
| F07 | No-Stale-Commit re-checks Live Twin versions before commit | *(static reference)* Gate G04 evidence — stale decision blocked, run required | 🔴 NOT VERIFIED |
| F08 | HMAC-signed single-use authorization issued on `ALLOW` | *(static reference)* Gate G05 evidence — run required | 🔴 NOT VERIFIED |
| F09 | Guarded Executor commits to Live Twin atomically (Firestore) | *(static reference)* Gate G05 evidence — Live Twin mutated, run required | 🔴 NOT VERIFIED |
| F10 | Verifier re-reads Live Twin and reports `VERIFIED` / `REGRESSION` / `INCONCLUSIVE` | *(static reference)* Gate G05 evidence — verifier verdict, run required | 🔴 NOT VERIFIED |
| F11 | Auto-replan on `REFRESH_REQUIRED` discards binding and replans | *(static reference)* Gate G04 evidence — D1 refused, D2 approved, run required | 🔴 NOT VERIFIED |
| F12 | Agent-action audit trail written to BigQuery `retailtwin.agent_action_audit` | *(static reference)* Gate G05 evidence — correlation_id round-trip, run required | 🔴 NOT VERIFIED |

### 1.2 Safety Stack

| # | Feature | Evidence Required | Status |
|---|---------|-------------------|--------|
| S01 | DCG reads Live Twin only; never writes | *(static reference)* ADR 0014 code review | 🟡 IN CODE |
| S02 | No-Stale-Commit refuses decisions built at version N once SKU is N+1 | *(static reference)* Gate G04 — live run required | 🔴 NOT VERIFIED |
| S03 | Signed single-use authorization (HMAC-SHA256, 30s TTL, nonce) | *(static reference)* ADR 0016; Gate G05 — live run required | 🔴 NOT VERIFIED |
| S04 | Guarded Executor is the **only** Live Twin writer | *(static reference)* ADR 0016 code review | 🟡 IN CODE |
| S05 | Bounded retry: `RETAILTWIN_REPLAN_MAX_REFRESHES=1` stops after one refresh | *(static reference)* Gate G04 — live run required | 🔴 NOT VERIFIED |

### 1.3 GCP Integration

| # | Feature | Evidence Required | Status |
|---|---------|-------------------|--------|
| G01 | Cloud Run `retailtwin-api` deployed in `us-central1` | *(static reference)* `scripts/verify-cloud-preflight.sh` — run required at submission SHA | 🟡 PARTIAL |
| G02 | `GET /health`, `/ready`, `/store` return 200 on deployed Cloud Run | *(static reference)* smoke job `smoke-backend-health`, `smoke-backend-readiness` — run required at submission SHA | 🟡 PARTIAL |
| G03 | `LIVE_TWIN_BACKEND=firestore` on deployed Cloud Run | *(static reference)* smoke job `smoke-firestore-store` — run required at submission SHA | 🟡 PARTIAL |
| G04 | `LLM_PROVIDER=vertex_gemini` with ADC auth (no API key) | *(static reference)* ADR 0020; smoke job `smoke-vertex-gemini` — run required at submission SHA | 🟡 PARTIAL |
| G05 | Vertex Gemini `gemini-2.5-flash` live tool call succeeds | *(static reference)* smoke job `smoke-vertex-gemini` — run required at submission SHA | 🟡 PARTIAL |
| G06 | One `get_inventory` tool call via Vertex adapter | *(static reference)* Gate G05 / smoke jobs `smoke-p001-inventory`, `smoke-p017-inventory` — run required at submission SHA | 🔴 NOT VERIFIED |
| G07 | Firestore `stores/store-001/inventory` has 20 SKUs (P001–P020) | *(static reference)* Production data audit run (#216): 8/8 PASS — verified at audit SHA, re-verify at submission SHA recommended | 🟢 PASSED |
| G08 | BigQuery `retailtwin.sales_events` has historical data | *(static reference)* Production data audit run (#216): 49 rows, 2 SKUs — verified at audit SHA | 🟢 PASSED |
| G09 | Pub/Sub `store-events` topic exists and accepts events | *(static reference)* Production data audit run (#216) — verified at audit SHA | 🟢 PASSED |
| G10 | Firebase Hosting `retailtwin-ai-511002.web.app` serves frontend | *(static reference)* smoke job `smoke-frontend-availability` — run required at submission SHA | 🟡 PARTIAL |

### 1.4 3D Digital Twin UI

| # | Feature | Evidence Required | Status |
|---|---------|-------------------|--------|
| U01 | 3D store renders with shelves A01, A02, B01, B02 | *(static reference)* Demo video — video required as proof | 🔴 NOT VERIFIED |
| U02 | 3D move cue: product hops from source to destination slot | *(static reference)* ADR 0022 — code review, not automated proof | 🟡 IN CODE |
| U03 | 3D facings cue: capacity enforcement and overflow flag | *(static reference)* ADR 0022 — code review | 🟡 IN CODE |
| U04 | 3D replenishment cue: `Shelf +N` / `Backroom -N` on product card | *(static reference)* ADR 0022 — code review | 🟡 IN CODE |
| U05 | Agent Activity panel shows 8-stage evidence timeline | *(static reference)* ADR 0037 — code review, not automated proof | 🔴 NOT VERIFIED |
| U06 | Live Twin state reflects committed changes (shelf, facings) | *(static reference)* Gate G05 evidence + demo video — live run and video required | 🔴 NOT VERIFIED |

### 1.5 Flagship Scenario — Weekend Demand Surge (SKU P017, store-001)

| # | Feature | Evidence Required | Status |
|---|---------|-------------------|--------|
| P01 | P017 starts at baseline: shelf=8, facings=2, slot=A02-S03, backroom=54 | *(static reference)* `data/synthetic/weekend-demand-surge.json` fixture — verified at fixture SHA | 🟡 IN FIXTURE |
| P02 | 13 `sale.completed` events produce +46% velocity spike | *(static reference)* `tests/e2e/gates/run_flagship_scenario.py` — run required to produce proof | 🔴 NOT VERIFIED |
| P03 | DCG intentionally returns `REFRESH_REQUIRED` on stale context | *(static reference)* Gate G04 negative case — run required | 🔴 NOT VERIFIED |
| P04 | Agent auto-replans and second decision passes DCG | *(static reference)* Gate G04 — run required | 🔴 NOT VERIFIED |
| P05 | Guarded commit changes P017 to shelf=20, facings=4 | *(static reference)* Gate G05 — run required | 🔴 NOT VERIFIED |
| P06 | 20 consecutive runs produce identical evidence (determinism) | *(static reference)* Gate G06: `artifacts/submission-gate/matrix.json` — 20-run harness required | 🔴 NOT VERIFIED |

---

## 2. CI Passing

> **⚠ CI passing at a previous SHA is not verified evidence for submission.** Every CI entry below is 🟡 UNKNOWN until CI runs at the **submission SHA** and the job succeeds. A green CI badge on a different SHA means the workflow definition is correct — it does not mean the code at `HEAD` passes. Re-run CI before submission and update the Status column with the run URL and SHA.

| # | Check | Workflow | Required | Status |
|---|-------|----------|----------|--------|
| C01 | Repository Hygiene (no merge conflicts, no secrets, no `.env`) | `ci.yml` — always runs | ✅ | 🟡 UNKNOWN — requires CI run at submission SHA |
| C02 | YAML workflow files valid | `ci.yml` | ✅ | 🟡 UNKNOWN — requires CI run at submission SHA |
| C03 | API mypy type-check passes | `ci.yml` — API paths changed | ✅ | 🟡 UNKNOWN — requires CI run at submission SHA |
| C04 | Forecasting tests pass (risk + demand) | `ci.yml` | ✅ | 🟡 UNKNOWN — requires CI run at submission SHA |
| C05 | API pytest with coverage (branch threshold enforced) | `ci.yml` | ✅ | 🟡 UNKNOWN — requires CI run at submission SHA |
| C06 | Critical-path coverage policy enforced | `ci.yml` | ✅ | 🟡 UNKNOWN — requires CI run at submission SHA |
| C07 | Simulation KPI tests pass with coverage | `ci.yml` | ✅ | 🟡 UNKNOWN — requires CI run at submission SHA |
| C08 | API E2E smoke suite passes | `ci.yml` — API paths changed | ✅ | 🟡 UNKNOWN — requires CI run at submission SHA |
| C09 | Web TypeScript build succeeds | `web.yml` | ✅ | 🟡 UNKNOWN — requires CI run at submission SHA |
| C10 | Web tests pass | `web.yml` | ✅ | 🟡 UNKNOWN — requires CI run at submission SHA |
| C11 | Web coverage collected | `web.yml` | ✅ | 🟡 UNKNOWN — requires CI run at submission SHA |
| C12 | Same-SHA barrier: API CI + Web CI both succeeded for head SHA | `release-gate.yml` gate job | ✅ | 🟡 UNKNOWN — requires CI run at submission SHA |
| C13 | No merge-conflict markers in any committed file | `conflict-markers.yml` | ✅ | 🟡 UNKNOWN — requires CI run at submission SHA |
| C14 | Version consistency (version files in sync) | `version-consistency.yml` | ✅ | 🟡 UNKNOWN — requires CI run at submission SHA |
| C15 | Security: dependency + container scans | `security.yml` | ✅ | 🟡 UNKNOWN — requires CI run at submission SHA |

> **CI passing ≠ reviewed.** A passing CI workflow proves automated checks succeed at a given SHA. It does **not** prove human-reviewed quality. Human review is a separate gate tracked outside this checklist.

---

## 3. Deployment Verified

### 3.1 Release Gate Smoke Tests (must all PASS)

| # | Smoke Check | Workflow Job | Status |
|---|-------------|--------------|--------|
| D01 | Backend liveness: `GET /health` → 200, `app_env=production` | `smoke-backend-health` | 🟡 PARTIAL — smoke job required at submission SHA |
| D02 | Backend readiness: `GET /ready` → 200 | `smoke-backend-readiness` | 🟡 PARTIAL — smoke job required at submission SHA |
| D03 | Firestore-backed `GET /store` → store-001 with products | `smoke-firestore-store` | 🟡 PARTIAL — smoke job required at submission SHA |
| D04 | P001 inventory read: HTTP 200, all required fields | `smoke-p001-inventory` | 🟡 PARTIAL — smoke job required at submission SHA |
| D05 | P017 inventory read: HTTP 200, competition fixture present | `smoke-p017-inventory` | 🟡 PARTIAL — smoke job required at submission SHA |
| D06 | BigQuery `sales_events` query under byte cap | `smoke-bigquery-analytics` | 🟡 PARTIAL — smoke job required at submission SHA |
| D07 | Pub/Sub deterministic event published to `store-events` | `smoke-pubsub-event` | 🟡 PARTIAL — smoke job required at submission SHA |
| D08 | Agent Activity: `/agent/events` shows activity for smoke run | `smoke-agent-activity` | 🟡 PARTIAL — smoke job required at submission SHA |
| D09 | Vertex Gemini live `generateContent` → HTTP 200 | `smoke-vertex-gemini` | 🟡 PARTIAL — smoke job required at submission SHA |
| D10 | Simulation safe outcome: `sim-seed-001` status=pending | `smoke-simulation-dcg` | 🟡 PARTIAL — smoke job required at submission SHA |
| D11 | No secrets in captured endpoint output | `smoke-secret-scan` | 🟡 PARTIAL — smoke job required at submission SHA |
| D12 | Firebase Hosting frontend reachable, serves HTML | `smoke-frontend-availability` | 🟡 PARTIAL — smoke job required at submission SHA |

### 3.2 Deployment Artifacts

| # | Artifact | Location | Verification |
|---|----------|----------|--------------|
| A01 | Cloud Run container image | `gcr.io/retailtwin-ai-511002/retailtwin-api:{SHA}` | `gcloud artifacts docker describe` |
| A02 | Cloud Run latest ready revision matches gate SHA | Cloud Run service `status.latestReadyRevisionName` | Release gate image digest check |
| A03 | Firebase Hosting release present | `retailtwin-ai-511002.web.app` | Firebase Hosting REST API |
| A04 | Web build artifact (web-dist) | GitHub Actions artifact | `gh api /actions/runs/{id}/artifacts` |

### 3.3 WIF / IAM

| # | Check | Status |
|---|-------|--------|
| W01 | Workload Identity Federation pool + provider configured | 🟡 UNKNOWN |
| W02 | `github-actions@retailtwin-ai-511002.iam.gserviceaccount.com` has Cloud Run deploy role | 🟡 UNKNOWN |
| W03 | `retailtwin-api@retailtwin-ai-511002.iam.gserviceaccount.com` has Firestore + BigQuery + Pub/Sub roles | 🟡 UNKNOWN |
| W04 | No long-lived JSON service account keys | 🟢 VERIFIED (WIF in use) |

---

## 4. Submission Gate Evidence Summary

> **Evidence type key:** *(static reference)* = authored doc, SHA-stable; *(run required)* = must be executed to produce proof; *(live run)* = requires deployed infrastructure.

| Gate | Issue | Status | Evidence |
|------|-------|--------|----------|
| Day-0 Foundation | #10 | 🔴 NOT PASSED | *(static reference)* `scripts/verify-day0-gate.sh`; `docs/DAY0_GATE_RUNBOOK.md` — run required at submission SHA |
| G02 Twin Control | #49 | 🟢 PASSED (closed #314) | *(run required)* agent tool changes Simulation Twin + 3D; Live unchanged — verified at gate run SHA |
| G03 Autonomous | #50 | 🟡 OFFLINE PASS — final-SHA rerun required | `docs/evidence/submission-gates/2026-10-22T1556Z/g03_autonomous.json`: `result=PASS`; tested SHA `c20fb073e4ab919fdced85b7285751e38090cbe3`; command/timestamp/checksums in retained `README.md`/`SHA256SUMS.txt` |
| G04 Guard | #51 | 🟡 OFFLINE PASS — final-SHA rerun required | `docs/evidence/submission-gates/2026-10-22T1556Z/g04_guard.json`: `result=PASS`; tested SHA `c20fb073e4ab919fdced85b7285751e38090cbe3`; command/timestamp/checksums in retained `README.md`/`SHA256SUMS.txt` |
| G05 Live Commit | #52 | 🟡 OFFLINE PASS — final-SHA rerun required | `docs/evidence/submission-gates/2026-10-22T1556Z/g05_live_commit.json`: `result=PASS`; tested SHA `c20fb073e4ab919fdced85b7285751e38090cbe3`; command/timestamp/checksums in retained `README.md`/`SHA256SUMS.txt` |
| G06 Submission | #53 | 🟡 OFFLINE PASS (20/20) — final-SHA rerun required | `docs/evidence/submission-gates/2026-10-22T1556Z/g06-matrix.json`: `passed=20`, `failed=0`; 20 per-run JSON artifacts bind SHA `c20fb073e4ab919fdced85b7285751e38090cbe3`; exact command/timestamp/checksums in retained `README.md`/`SHA256SUMS.txt` |
| Production Data Audit | #216 | 🟡 LIVE PROOF DONE (reviewer acceptance pending) | *(live run)* `docs/PRODUCTION_DATA_AUDIT_RUN.md`: 8/8 PASS — verified at audit SHA, re-verify recommended at submission SHA |

---

## 5. Document Checklist

| # | Document | Required | Status |
|---|----------|----------|--------|
| D01 | `README.md` current with architecture, setup, deployment | ✅ | 🟢 CURRENT — static reference; currency verified |
| D02 | `docs/COMPETITION_README.md` | ✅ | 🟡 EXISTS — verify currency at submission SHA |
| D03 | `docs/SUBMISSION_DECK.md` | ✅ | 🟡 EXISTS — verify currency at submission SHA |
| D04 | `docs/SUBMISSION_INDEX.md` | ✅ | 🟡 EXISTS — verify currency at submission SHA |
| D05 | `docs/ARCHITECTURE_DIAGRAM.md` | ✅ | 🟡 EXISTS — verify currency at submission SHA |
| D06 | `docs/ARCHITECTURE.md` | ✅ | 🟡 EXISTS — verify currency at submission SHA |
| D07 | `docs/DEMO_AND_ACCEPTANCE.md` | ✅ | 🟡 EXISTS — verify currency at submission SHA |
| D08 | `docs/CLOUD_RUNTIME_MATRIX.md` | ✅ | 🟡 EXISTS — verify currency at submission SHA |
| D09 | `docs/DOMAIN_AND_DATA_MODEL.md` | ✅ | 🟡 EXISTS — verify currency at submission SHA |
| D10 | `docs/CURRENT_STATUS.md` | ✅ | 🟡 EXISTS — verify currency at submission SHA |
| D11 | ADRs 0001–0023, 0037, 0039, 0040, 0041 merged on `main` | ✅ | 🟡 EXISTS — verify all ADRs on `main` at submission SHA |
| D12 | `docs/demo-video/shot-list.md` | ✅ | 🟡 EXISTS — verify currency at submission SHA |
| D13 | `docs/demo-video/production-checklist.md` | ✅ | 🟡 EXISTS — verify currency at submission SHA |
| D14 | `docs/demo-video/acceptance-criteria.md` | ✅ | 🟡 EXISTS — verify currency at submission SHA |

---

## 6. Competition Requirements

| # | Requirement | Evidence | Status |
|---|-------------|----------|--------|
| CR01 | Live 3D Digital Twin (not decorative) | *(static reference)* `GET /store` drives 3D; `apps/web/src/state/twin.store.ts` — code review, not automated proof | 🟡 IN CODE |
| CR02 | Autonomous: no human prompt to trigger investigation | *(run required)* Gate G03 — run required at submission SHA | 🔴 NOT VERIFIED |
| CR03 | AI gathers evidence, plans, simulates before acting | *(run required)* Gates G03/G05 — run required at submission SHA | 🔴 NOT VERIFIED |
| CR04 | Safety: DCG prevents stale/invalid commits | *(run required)* Gate G04 — run required at submission SHA | 🔴 NOT VERIFIED |
| CR05 | Google AI (Gemini on Vertex AI) for inference | *(static reference)* ADR 0020/0021; smoke job `smoke-vertex-gemini` — run required at submission SHA | 🟡 PARTIAL |
| CR06 | Google Cloud: Cloud Run, Firestore, BigQuery, Pub/Sub | *(run required)* smoke jobs D01–D12 — run required at submission SHA | 🟡 PARTIAL |
| CR07 | Firebase Hosting for web delivery | *(run required)* smoke job `smoke-frontend-availability` — run required at submission SHA | 🟡 PARTIAL |
| CR08 | Reproducible flagship scenario | *(run required)* Gate G06: 20-run matrix — run required at submission SHA | 🔴 NOT VERIFIED |
| CR09 | Demo video under required duration | *(static reference)* `docs/DEMO_VIDEO.md` — video artifact required | 🔴 NOT VERIFIED |
| CR10 | Public repository | `github.com/vinhphan812/retailtwin-ai` | ✅ PUBLIC |
| CR11 | No secrets/credentials in repo | *(run required)* CI C03 + C13 — run required at submission SHA | 🟡 UNKNOWN |
| CR12 | License declared | MIT License at repository root (`LICENSE`); third-party provenance/permission remains a separate supply-chain review | 🟢 DECLARED |

---

## 7. Final Sign-off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Tech Lead | | | |
| Safety Reviewer | | | |
| Cloud Ops | | | |
| Documentation | | | |

### Summary

- **Features (F01–F12, S01–S05, G01–G10, U01–U06, P01–P06):** no final-submission-SHA verification recorded
- **CI checks (C01–C15):** requires green live run at final submission SHA; `origin/main` CI at the recorded evidence SHA was red
- **Deployment (D01–D12, A01–A04, W01–W04):** 🟡 PARTIAL — no deployment acceptance claim is made for this evidence set
- **Release gates (G02–G06, #216):** G02 passed; G03–G06 offline PASS at `c20fb073…`, but final-SHA rerun remains required
- **Competition requirements (CR01–CR12):** license declared; deployment-dependent requirements remain 🟡/🔴
- **Documentation (D01–D14):** 14 documents present; currency not verified  

> **Verdict:** Not ready for submission. Committed offline artifacts demonstrate G03–G06 passes at `c20fb073e4ab919fdced85b7285751e38090cbe3`, but that is not the final submission SHA and does not establish deployment acceptance. Before any green deployment/submission claim: repair the unrelated red CI on `main`, build a final submission SHA, run the relevant gates and CI at that SHA, deploy it, and independently verify the deployed revision.

---

*This checklist is the authoritative pre-submission sign-off tracker. Update the Status column as each item is verified. A green overall status requires all 37 feature items, all 15 CI checks, all 12 deployment smoke checks, and all 12 competition requirements to be 🟢 VERIFIED.*
