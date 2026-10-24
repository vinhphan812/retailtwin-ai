# RetailTwin AI — Final Submission Validation Checklist

**Issue:** tracks completion of all pre-submission requirements for the AI Builder Google 2026 competition.
**Status:** `OPEN — NOT READY`
**Owner:** maintainers
**Last updated:** 2026-10-25

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

### CR12 licence states — DECLARED vs VERIFIED

CR12 uses two additional states, defined in §6.1 and used **only** for the licence requirement:

| State | Meaning |
|-------|---------|
| 🟡 **DECLARED** | A licence file exists at the repository root and the README references it. The project *states* a licence; nothing is asserted about the authority to grant it. |
| 🟢 **VERIFIED** | Provenance and authority evidence exists for the grant — a CLA, or written confirmation from each non-owner human contributor, recorded in the repository. |

These are **not** interchangeable. A licence file on its own is never sufficient for 🟢 VERIFIED,
and a pre-merge pull-request head must never be cited as though the licence existed at that SHA.

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
| G03 Autonomous | #50 | 🔴 NOT PASSED | *(run required)* `tests/e2e/gates/g03_autonomous_gate.py` — run required at submission SHA |
| G04 Guard | #51 | 🔴 NOT PASSED | *(run required)* `tests/e2e/gates/g04_guard_gate.py` — run required at submission SHA |
| G05 Live Commit | #52 | 🔴 NOT PASSED | *(run required)* `tests/e2e/gates/g05_live_commit_gate.py` — run required at submission SHA |
| G06 Submission | #53 | 🔴 NOT PASSED | *(run required)* `scripts/run-submission-gate.sh` → 20-row `matrix.json` — run required at submission SHA |
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
| D15 | `docs/licensing/CONTRIBUTOR-LICENSE-PROVENANCE.md` | ✅ | 🟡 EXISTS — contributor-authority record for the MIT grant; states the open owner actions (CR12, see §6.1) |
| D16 | `CLA.md` (repository root) | ✅ | 🟡 EXISTS — Individual Contributor Licence Agreement, owner-signed; the three non-owner acceptance rows are **not yet accepted** (CR12, see §6.1) |
| D17 | `CONTRIBUTING.md` (repository root) | ✅ | 🟡 EXISTS — contributor guide; states the CLA acceptance requirement before a contribution is merged |

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
| CR12 | License declared | *(static reference)* MIT licence text and third-party notice exist **only on open PRs #398 (`ebb70b64`) / #397 (`4fae32de`)** — byte-identical blobs; **no root `LICENSE` at submission SHA `920e166f`**. Contributor-authority artefact `CLA.md` now exists at the root (owner-signed; three non-owner acceptances outstanding). See §6.1 | 🔴 MISSING at `920e166f` → 🟡 DECLARED (post-merge) → 🟢 VERIFIED (provenance confirmed) — see §6.1 |

> **Requirement label.** The second column reproduces the competition requirement wording
> verbatim ("License declared", per Issue #367). The prose of this document uses the UK
> spelling *licence* for the noun, and the repository's own file and heading names — `LICENSE`,
> `THIRD_PARTY_NOTICES.md`, `License.txt`, README `## License` — are quoted exactly as they
> appear on disk.

> ⚠️ **Merge-conflict note.** PR #398 and PR #397 both amend the CR12 row and the
> CR-summary line of this file. If either licence PR is merged before this change, the CR12 row
> and the CR-summary line will conflict and must be resolved **in favour of this wording**
> (which states the SHA-bound distinction) — not in favour of a bare `🟢 DECLARED` with no
> SHA-bound evidence and no DECLARED/VERIFIED distinction. The licence material itself
> (`LICENSE`, `THIRD_PARTY_NOTICES.md`) is identical on both PRs, so there is nothing to
> reconcile there.

### 6.1 CR12 — licence evidence

**Reproduce in one step** (from the repository root):

```bash
git ls-tree --name-only 920e166f | grep -iE '^(LICENSE|THIRD_PARTY_NOTICES|COPYING|NOTICE)'
gh api repos/vinhphan812/retailtwin-ai/license
```

The first command is SHA-exact and is the authoritative check. The second reads the repository's
**default branch head** — currently `920e166f` — and returns HTTP 404 with no `licenseInfo`,
which is GitHub's licence detector reporting that it finds no licence.

At submission SHA `920e166f` both commands show **no licence**. The first is expected to print
nothing and exit non-zero (`grep` reporting "no match") — that empty result *is* the finding, not
a command error. README §License states "This repository does not currently declare a license
file".

#### The two states, and what each requires

| State | Meaning | Preconditions | True today? |
|---|---|---|---|
| 🟡 **DECLARED** | A licence file exists at the repository root and the README references it. Proves the project *states* a licence. Proves nothing about who had the authority to grant it. | Exactly one of PR #397 / #398 merged, and a **new submission SHA** cut from that merge. | **No** — both PRs are open; neither licence file is in the tree. |
| 🟢 **VERIFIED** | Provenance/authority evidence exists for the MIT grant — a CLA, or written confirmation from each non-owner human contributor, recorded in-repo. | DECLARED **and** the contributor-authority record closed. | **No** — the CLA artefact `CLA.md` now exists at the repository root and the owner has signed its acceptance register, but **none of the three non-owner contributors has accepted**: acceptance requests #408, #409 and #410 are open with no response. |

**CR12 cannot read 🟢 VERIFIED on the strength of the licence text alone.** The MIT text asserts
`Copyright (c) 2026 RetailTwin AI Contributors`, but the repository held no record that every
contributor authorised that grant. `THIRD_PARTY_NOTICES.md` covers *third-party* provenance only
and does **not** close this gap.

**Progress on the contributor-authority gap (A2).** The mechanism is now in place: `CLA.md` at the
repository root is an inbound Individual Contributor Licence Agreement with an acceptance register
at §5, adopted and owner-signed on 2026-10-25. Acceptance requests are open for the three
non-owner human contributors as issues [#408](https://github.com/vinhphan812/retailtwin-ai/issues/408)
(`anh-nguyen-3103`), [#409](https://github.com/vinhphan812/retailtwin-ai/issues/409) (`k-pham08`)
and [#410](https://github.com/vinhphan812/retailtwin-ai/issues/410) (`longshaww`). **No acceptance
has been received.** A request is not a confirmation: the three rows stay `NOT EVIDENCED` in
`docs/licensing/CONTRIBUTOR-LICENSE-PROVENANCE.md` §5 until each acceptance is actually received
and recorded. **CR12 therefore remains blocked at 🟡/🔴 and cannot read 🟢 VERIFIED.**

#### Authoritative files and the SHA they bind to

| File | Path | Git blob SHA | SHA-256 | Size | Bound to |
|---|---|---|---|---|---|
| Licence text | `LICENSE` (repository root) | `45b8da20817cb3ae9926b65c8d831ed88db9d23f` | `1d1e0b4b81b98b360932a440d6857c5f182e8392b18a8058ed4862a0e778f4c7` | 1083 B | **PR #398** head `ebb70b646f48365bfbb724df71170a09e85442cf` (OPEN) — byte-identical on **PR #397** head `4fae32dea25c43d4af2fd49d86da11f03fb1e172` (OPEN). **Absent at `920e166f`.** |
| Third-party notice | `THIRD_PARTY_NOTICES.md` (repository root) | `29dfe959868e3724094fdaf1bd20052199dc2e48` | — | 5466 B | As above — same two open PR heads. **Absent at `920e166f`.** |
| Contributor-authority record | `docs/licensing/CONTRIBUTOR-LICENSE-PROVENANCE.md` | *this branch* | — | — | Present from this commit onwards; states the open items explicitly. |
| Contributor licence agreement | `CLA.md` (repository root) | *this branch* | — | — | Inbound Individual Contributor Licence Agreement, adopted and owner-signed 2026-10-25; acceptance register at §5. **Absent at `920e166f`.** The three non-owner rows read *not yet accepted* — requests #408 / #409 / #410 open, no response. |

> ⚠️ **Do not cite a pre-merge SHA as if the licence existed at it.** The licence is bound to the
> **merge commit** of whichever licence PR is merged, not to that PR's head. The submission SHA
> changes on merge, and the deployment must be re-cut at the new SHA before CR12 can be signed off.

#### Outstanding owner actions (not resolved by this checklist)

| # | Action | Status |
|---|---|---|
| A1 | Choose **exactly one** of PR #397 / PR #398 to merge as the canonical licence delivery; close the other (identical licence blobs and overlapping gate-evidence trees). | ⛔ Owner decision — outstanding |
| A2 | Record contributor-authority confirmation for the MIT grant (CLA, or written confirmation from `anh-nguyen-3103`, `k-pham08`, `longshaww`). Tracked in `docs/licensing/CONTRIBUTOR-LICENSE-PROVENANCE.md` §7. | 🟡 **In progress** — `CLA.md` adopted and owner-signed 2026-10-25; acceptance requests #408 / #409 / #410 open with **no response received** |
| A3 | Re-cut the submission SHA from the merge, then re-evaluate CR12 at that SHA. | ⛔ Blocked by A1, A2 |
| A4 | Re-deploy Cloud Run and the web artefact at the new SHA; confirm the MIT notice travels with the distributed artefacts. | ⛔ Blocked by A3 — card `t_f34e7fb6` |

See `docs/licensing/CONTRIBUTOR-LICENSE-PROVENANCE.md` for the per-contributor evidence index and
the re-runnable commands behind every claim above.

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
- **Competition requirements (CR01–CR12):** 2 confirmed, 1 missing (CR12 licence — 🔴 MISSING at submission SHA `920e166f`; reaches 🟡 DECLARED only once one licence PR is merged and a new SHA is cut, and 🟢 VERIFIED only with contributor-authority evidence — the `CLA.md` artefact exists and is owner-signed, but the three non-owner acceptances are still outstanding — see §6.1), rest 🟡/🔴  
- **Documentation (D01–D17):** 17 documents present; currency not verified  

> **Verdict:** Not ready for submission. The code is largely in place but no release gate evidence (G03–G06) has been recorded. Cloud preflight (G01) and production data audit (#216) are green. The first action is to run the G03–G06 submission gate harnesses and record the evidence matrices.

---

*This checklist is the authoritative pre-submission sign-off tracker. Update the Status column as each item is verified. A green overall status requires all 37 feature items, all 15 CI checks, all 12 deployment smoke checks, and all 12 competition requirements to be 🟢 VERIFIED.*
