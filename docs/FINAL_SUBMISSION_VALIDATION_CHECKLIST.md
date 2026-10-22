# RetailTwin AI — Final Submission Validation Checklist

**Issue:** tracks completion of all pre-submission requirements for the AI Builder Google 2026 competition.  
**Status:** `OPEN — NOT READY`  
**Owner:** maintainers  
**Last updated:** 2026-10-20

---

## 1. Required Features — All Must Be Working

### 1.1 Autonomous Control Loop (OBSERVE → DETECT → INVESTIGATE → PLAN → SIMULATE → GUARD → ACT → VERIFY)

| # | Feature | Evidence Required | Status |
|---|---------|-------------------|--------|
| F01 | `POST /events` accepts `sale.completed` without human prompt | `tests/e2e/gates/g03_autonomous_gate.py` passes | 🔴 NOT VERIFIED |
| F02 | Observer starts exactly one investigation per accepted sale | Gate G03 evidence JSON | 🔴 NOT VERIFIED |
| F03 | Investigator collects versioned EvidenceBundle through allow-listed tool registry | ADR 0011 evidence; `FakeLlmProvider` tools fire | 🔴 NOT VERIFIED |
| F04 | Planner proposes 2–3 bounded candidate actions bound to evidence | Gate G03 evidence | 🔴 NOT VERIFIED |
| F05 | Simulator clones Live Twin and scores candidates with `simulation-kpi-v1` | Gate G05 evidence | 🔴 NOT VERIFIED |
| F06 | Decision Context Guard (6 gates) returns `ALLOW` / `DENY` / `REFRESH_REQUIRED` / `HUMAN_REVIEW` | Gate G04 evidence | 🔴 NOT VERIFIED |
| F07 | No-Stale-Commit re-checks Live Twin versions before commit | Gate G04 evidence: stale decision blocked | 🔴 NOT VERIFIED |
| F08 | HMAC-signed single-use authorization issued on `ALLOW` | Gate G05 evidence | 🔴 NOT VERIFIED |
| F09 | Guarded Executor commits to Live Twin atomically (Firestore) | Gate G05 evidence: Live Twin mutated | 🔴 NOT VERIFIED |
| F10 | Verifier re-reads Live Twin and reports `VERIFIED` / `REGRESSION` / `INCONCLUSIVE` | Gate G05 evidence: verifier verdict present | 🔴 NOT VERIFIED |
| F11 | Auto-replan on `REFRESH_REQUIRED` discards binding and replans | Gate G04 evidence: D1 refused, D2 approved | 🔴 NOT VERIFIED |
| F12 | Agent-action audit trail written to BigQuery `retailtwin.agent_action_audit` | Gate G05 evidence: correlation_id round-trip | 🔴 NOT VERIFIED |

### 1.2 Safety Stack

| # | Feature | Evidence Required | Status |
|---|---------|-------------------|--------|
| S01 | DCG reads Live Twin only; never writes | ADR 0014 code review | 🟡 IN CODE |
| S02 | No-Stale-Commit refuses decisions built at version N once SKU is N+1 | Gate G04 | 🔴 NOT VERIFIED |
| S03 | Signed single-use authorization (HMAC-SHA256, 30s TTL, nonce) | ADR 0016; Gate G05 | 🔴 NOT VERIFIED |
| S04 | Guarded Executor is the **only** Live Twin writer | ADR 0016 code review | 🟡 IN CODE |
| S05 | Bounded retry: `RETAILTWIN_REPLAN_MAX_REFRESHES=1` stops after one refresh | Gate G04 | 🔴 NOT VERIFIED |

### 1.3 GCP Integration

| # | Feature | Evidence Required | Status |
|---|---------|-------------------|--------|
| G01 | Cloud Run `retailtwin-api` deployed in `us-central1` | `scripts/verify-cloud-preflight.sh` | 🟡 PARTIAL |
| G02 | `GET /health`, `/ready`, `/store` return 200 on deployed Cloud Run | Release gate smoke 1–3 | 🟡 PARTIAL |
| G03 | `LIVE_TWIN_BACKEND=firestore` on deployed Cloud Run | Release gate smoke 3 | 🟡 PARTIAL |
| G04 | `LLM_PROVIDER=vertex_gemini` with ADC auth (no API key) | ADR 0020; gate smoke 9 | 🟡 PARTIAL |
| G05 | Vertex Gemini `gemini-2.5-flash` live tool call succeeds | Gate smoke 9 | 🟡 PARTIAL |
| G06 | One `get_inventory` tool call via Vertex adapter | Gate G05 / smoke 4–5 | 🔴 NOT VERIFIED |
| G07 | Firestore `stores/store-001/inventory` has 20 SKUs (P001–P020) | Production data audit run (#216): 8/8 PASS | 🟢 PASSED |
| G08 | BigQuery `retailtwin.sales_events` has historical data | Production data audit run (#216): 49 rows, 2 SKUs | 🟢 PASSED |
| G09 | Pub/Sub `store-events` topic exists and accepts events | Production data audit run (#216) | 🟢 PASSED |
| G10 | Firebase Hosting `retailtwin-ai-511002.web.app` serves frontend | Release gate smoke 12 | 🟡 PARTIAL |

### 1.4 3D Digital Twin UI

| # | Feature | Evidence Required | Status |
|---|---------|-------------------|--------|
| U01 | 3D store renders with shelves A01, A02, B01, B02 | Demo video | 🔴 NOT VERIFIED |
| U02 | 3D move cue: product hops from source to destination slot | ADR 0022 | 🟡 IN CODE |
| U03 | 3D facings cue: capacity enforcement and overflow flag | ADR 0022 | 🟡 IN CODE |
| U04 | 3D replenishment cue: `Shelf +N` / `Backroom -N` on product card | ADR 0022 | 🟡 IN CODE |
| U05 | Agent Activity panel shows 8-stage evidence timeline | ADR 0037 | 🔴 NOT VERIFIED |
| U06 | Live Twin state reflects committed changes (shelf, facings) | Gate G05 + demo video | 🔴 NOT VERIFIED |

### 1.5 Flagship Scenario — Weekend Demand Surge (SKU P017, store-001)

| # | Feature | Evidence Required | Status |
|---|---------|-------------------|--------|
| P01 | P017 starts at baseline: shelf=8, facings=2, slot=A02-S03, backroom=54 | `data/synthetic/weekend-demand-surge.json` | 🟡 IN FIXTURE |
| P02 | 13 `sale.completed` events produce +46% velocity spike | `tests/e2e/gates/run_flagship_scenario.py` | 🔴 NOT VERIFIED |
| P03 | DCG intentionally returns `REFRESH_REQUIRED` on stale context | Gate G04 negative case | 🔴 NOT VERIFIED |
| P04 | Agent auto-replans and second decision passes DCG | Gate G04 | 🔴 NOT VERIFIED |
| P05 | Guarded commit changes P017 to shelf=20, facings=4 | Gate G05 | 🔴 NOT VERIFIED |
| P06 | 20 consecutive runs produce identical evidence (determinism) | Gate G06: `artifacts/submission-gate/matrix.json` | 🔴 NOT VERIFIED |

---

## 2. CI Passing

| # | Check | Workflow | Required | Status |
|---|-------|----------|----------|--------|
| C01 | Repository Hygiene (no merge conflicts, no secrets, no `.env`) | `ci.yml` — always runs | ✅ | 🟡 UNKNOWN |
| C02 | YAML workflow files valid | `ci.yml` | ✅ | 🟡 UNKNOWN |
| C03 | API mypy type-check passes | `ci.yml` — API paths changed | ✅ | 🟡 UNKNOWN |
| C04 | Forecasting tests pass (risk + demand) | `ci.yml` | ✅ | 🟡 UNKNOWN |
| C05 | API pytest with coverage (branch threshold enforced) | `ci.yml` | ✅ | 🟡 UNKNOWN |
| C06 | Critical-path coverage policy enforced | `ci.yml` | ✅ | 🟡 UNKNOWN |
| C07 | Simulation KPI tests pass with coverage | `ci.yml` | ✅ | 🟡 UNKNOWN |
| C08 | API E2E smoke suite passes | `ci.yml` — API paths changed | ✅ | 🟡 UNKNOWN |
| C09 | Web TypeScript build succeeds | `web.yml` | ✅ | 🟡 UNKNOWN |
| C10 | Web tests pass | `web.yml` | ✅ | 🟡 UNKNOWN |
| C11 | Web coverage collected | `web.yml` | ✅ | 🟡 UNKNOWN |
| C12 | Same-SHA barrier: API CI + Web CI both succeeded for head SHA | `release-gate.yml` gate job | ✅ | 🟡 UNKNOWN |
| C13 | No merge-conflict markers in any committed file | `conflict-markers.yml` | ✅ | 🟡 UNKNOWN |
| C14 | Version consistency (version files in sync) | `version-consistency.yml` | ✅ | 🟡 UNKNOWN |
| C15 | Security: dependency + container scans | `security.yml` | ✅ | 🟡 UNKNOWN |

> **Note:** CI status is `UNKNOWN` — requires a live CI run against the final submission SHA to confirm. The workflow definitions are correct; execution proof is required.

---

## 3. Deployment Verified

### 3.1 Release Gate Smoke Tests (must all PASS)

| # | Smoke Check | Workflow Job | Status |
|---|-------------|--------------|--------|
| D01 | Backend liveness: `GET /health` → 200, `app_env=production` | `smoke-backend-health` | 🟡 PARTIAL |
| D02 | Backend readiness: `GET /ready` → 200 | `smoke-backend-readiness` | 🟡 PARTIAL |
| D03 | Firestore-backed `GET /store` → store-001 with products | `smoke-firestore-store` | 🟡 PARTIAL |
| D04 | P001 inventory read: HTTP 200, all required fields | `smoke-p001-inventory` | 🟡 PARTIAL |
| D05 | P017 inventory read: HTTP 200, competition fixture present | `smoke-p017-inventory` | 🟡 PARTIAL |
| D06 | BigQuery `sales_events` query under byte cap | `smoke-bigquery-analytics` | 🟡 PARTIAL |
| D07 | Pub/Sub deterministic event published to `store-events` | `smoke-pubsub-event` | 🟡 PARTIAL |
| D08 | Agent Activity: `/agent/events` shows activity for smoke run | `smoke-agent-activity` | 🟡 PARTIAL |
| D09 | Vertex Gemini live `generateContent` → HTTP 200 | `smoke-vertex-gemini` | 🟡 PARTIAL |
| D10 | Simulation safe outcome: `sim-seed-001` status=pending | `smoke-simulation-dcg` | 🟡 PARTIAL |
| D11 | No secrets in captured endpoint output | `smoke-secret-scan` | 🟡 PARTIAL |
| D12 | Firebase Hosting frontend reachable, serves HTML | `smoke-frontend-availability` | 🟡 PARTIAL |

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

| Gate | Issue | Status | Evidence |
|------|-------|--------|----------|
| Day-0 Foundation | #10 | 🔴 NOT PASSED | `scripts/verify-day0-gate.sh`; `docs/DAY0_GATE_RUNBOOK.md` |
| G02 Twin Control | #49 | 🟢 PASSED (closed #314) | agent tool changes Simulation Twin + 3D; Live unchanged |
| G03 Autonomous | #50 | 🟢 PASSED | `tests/e2e/gates/g03_autonomous_gate.py` (passed) |
| G04 Guard | #51 | 🟢 PASSED | `tests/e2e/gates/g04_guard_gate.py` (passed) |
| G05 Live Commit | #52 | 🟢 PASSED | `tests/e2e/gates/g05_live_commit_gate.py` (passed) |
| G06 Submission | #53 | 🟢 PASSED (20/20 runs) | `scripts/run-submission-gate.sh` → `artifacts/submission-gate/matrix.json` |
| Production Data Audit | #216 | 🟡 LIVE PROOF DONE (reviewer acceptance pending) | `docs/PRODUCTION_DATA_AUDIT_RUN.md`: 8/8 PASS |

---

## 5. Document Checklist

| # | Document | Required | Status |
|---|----------|----------|--------|
| D01 | `README.md` current with architecture, setup, deployment | ✅ | 🟢 CURRENT |
| D02 | `docs/COMPETITION_README.md` | ✅ | 🟡 EXISTS |
| D03 | `docs/SUBMISSION_DECK.md` | ✅ | 🟡 EXISTS |
| D04 | `docs/SUBMISSION_INDEX.md` | ✅ | 🟡 EXISTS |
| D05 | `docs/ARCHITECTURE_DIAGRAM.md` | ✅ | 🟡 EXISTS |
| D06 | `docs/ARCHITECTURE.md` | ✅ | 🟡 EXISTS |
| D07 | `docs/DEMO_AND_ACCEPTANCE.md` | ✅ | 🟡 EXISTS |
| D08 | `docs/CLOUD_RUNTIME_MATRIX.md` | ✅ | 🟡 EXISTS |
| D09 | `docs/DOMAIN_AND_DATA_MODEL.md` | ✅ | 🟡 EXISTS |
| D10 | `docs/CURRENT_STATUS.md` | ✅ | 🟡 EXISTS |
| D11 | ADRs 0001–0023, 0037, 0039, 0040, 0041 merged on `main` | ✅ | 🟡 EXISTS |
| D12 | `docs/demo-video/shot-list.md` | ✅ | 🟡 EXISTS |
| D13 | `docs/demo-video/production-checklist.md` | ✅ | 🟡 EXISTS |
| D14 | `docs/demo-video/acceptance-criteria.md` | ✅ | 🟡 EXISTS |

---

## 6. Competition Requirements

| # | Requirement | Evidence | Status |
|---|-------------|----------|--------|
| CR01 | Live 3D Digital Twin (not decorative) | `GET /store` drives 3D; `apps/web/src/state/twin.store.ts` | 🟡 IN CODE |
| CR02 | Autonomous: no human prompt to trigger investigation | Gate G03 | 🔴 NOT VERIFIED |
| CR03 | AI gathers evidence, plans, simulates before acting | Gates G03/G05 | 🔴 NOT VERIFIED |
| CR04 | Safety: DCG prevents stale/invalid commits | Gate G04 | 🔴 NOT VERIFIED |
| CR05 | Google AI (Gemini on Vertex AI) for inference | ADR 0020/0021; gate smoke 9 | 🟡 PARTIAL |
| CR06 | Google Cloud: Cloud Run, Firestore, BigQuery, Pub/Sub | Gate D01–D12 | 🟡 PARTIAL |
| CR07 | Firebase Hosting for web delivery | Gate D12 | 🟡 PARTIAL |
| CR08 | Reproducible flagship scenario | Gate G06: 20-run matrix | 🔴 NOT VERIFIED |
| CR09 | Demo video under required duration | `docs/DEMO_VIDEO.md` | 🔴 NOT VERIFIED |
| CR10 | Public repository | `github.com/vinhphan812/retailtwin-ai` | ✅ PUBLIC |
| CR11 | No secrets/credentials in repo | CI C03 + C13 | 🟡 UNKNOWN |
| CR12 | License declared | MIT License (`LICENSE`) | 🟢 VERIFIED |

---

## 7. Final Sign-off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Tech Lead | | | |
| Safety Reviewer | | | |
| Cloud Ops | | | |
| Documentation | | | |

### Summary

- **Features (F01–F12, S01–S05, G01–G10, U01–U06, P01–P06):** 0 / 37 verified  
- **CI checks (C01–C15):** requires live run  
- **Deployment (D01–D12, A01–A04, W01–W04):** 🟡 PARTIAL — cloud preflight and data audit passed  
- **Release gates (G02–G06, #216):** G02 passed; G03–G06 NOT PASSED  
- **Competition requirements (CR01–CR12):** 2 confirmed, 1 missing (license), rest 🟡/🔴  
- **Documentation (D01–D14):** 14 documents present; currency not verified  

> **Verdict:** Not ready for submission. The code is largely in place but no release gate evidence (G03–G06) has been recorded. Cloud preflight (G01) and production data audit (#216) are green. The first action is to run the G03–G06 submission gate harnesses and record the evidence matrices.

---

*This checklist is the authoritative pre-submission sign-off tracker. Update the Status column as each item is verified. A green overall status requires all 37 feature items, all 15 CI checks, all 12 deployment smoke checks, and all 12 competition requirements to be 🟢 VERIFIED.*
