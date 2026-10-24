# Final Submission Validation Checklist — Reviewer Reconciliation

**Submission SHA (canonical):** `920e166f3526947e66ced3644bed40e761a88133`
**Active Cloud Run deployment:** service `retailtwin-api`, region `us-central1`, revision `retailtwin-api-00053-6k7`, 100% traffic, `GIT_SHA=920e166f…`, live `/version` and `/health` both report `git_sha=920e166f…`
**Live API:** `https://retailtwin-api-5rgtvr4gpa-uc.a.run.app` · **Live web:** `https://retailtwin-ai-511002.web.app/`
**Checklist source of rows:** PR #407 (`docs/cr12-licence-provenance`, head `bc894af1f80a78ebb874d9ba36050ee695c7ef68`), exported verbatim to `.review-tmp/ck407_upstream.md`
**Evidence bundle (this directory):** `docs/evidence/submission-gates/2026-10-25-reviewer-reconciliation-920e166f/`
**Reviewer:** `reviewer` · **Date:** 2026-10-25 · **Issue:** #367

## Verdict

**🔴 BLOCKED — NO SIGN-OFF.**

The submission cannot be signed off at `920e166f`. Three independent deployed blockers and one licence blocker are confirmed by direct evidence:

1. **Pub/Sub push authentication is broken.** Subscription `store-events-agent` carries **no `oidcToken`**, and the runtime service account has **no `serviceAccountTokenCreator`** binding anywhere in project IAM. Google-originated push requests *do* reach Cloud Run and are **rejected HTTP 401**. → `pubsub-push-config-summary.txt`, `cloudsigning-pubsub-push-401.json`, `iam-project-policy.json`
2. **Firestore decision/simulation persistence is broken in the deployed image.** `DecisionStoreUnavailable: Application Default Credentials are not available: KeyError` → `SimulationStoreUnavailable`. The working inventory path and the failing decision path use **different token acquisition mechanisms**. → `cloudsigning-decision-store-unavailable.json`, `autonomy-sequence-full.txt`
3. **Licence (CR12) is not satisfied at the submission SHA.** No root `LICENSE`, no `THIRD_PARTY_NOTICES.md`; GitHub licence detector reports none. → upstream audit `t_57fcdbdf`
4. **Final-SHA evidence is not durable.** The `920e166f` gate package exists only in local worktree `t_b539a304` (commit `9b56f11d`), which is not reachable from any `origin` branch or PR head. This reviewer bundle is published on an `origin` branch and is therefore durable.

**Critical correction to the earlier reading.** The deployed autonomy pipeline is **not** dead at ingress. A live run proves the chain executes through to planning and fails **only** at persistence:

```
event.accepted event_id=reviewer-smoke-20261024T212749Z-direct duplicate=False store_id=store-001
observer  … outcome=started investigation_id=inv-reviewer-smoke-20261024T212749Z-direct
tool name=get_inventory    capability=READ ok=True
tool name=get_shelf_state  capability=READ ok=True
tool name=get_sales_history capability=READ ok=True
tool name=forecast_demand  capability=READ ok=True
tool name=get_promotions   capability=READ ok=True
tool name=get_planogram    capability=READ ok=True
evidence collected correlation_id=reviewer-smoke-20261024T212749Z sku=P001 is_sufficient=True missing=
plans created (deterministic) correlation_id=reviewer-smoke-20261024T212749Z sku=P001 decisions=1
autonomy finished correlation_id=reviewer-smoke-20261024T212749Z status=failed reason=SimulationStoreUnavailable
```
→ `autonomy-sequence-full.txt`

Consequences for sign-off: F01–F03 and G05–G06 are **live-verified** at the exact SHA; F04 (2–3 candidates) **fails** — the deployed planner produced `decisions=1` via the *deterministic* path; F05–F12 and CR04 are **not reachable** because the run aborts at the simulation stage.

---

## §1 — Autonomy chain (F01–F12)

| Row | Requirement | Status | Durable evidence | Note |
|---|---|---|---|---|
| F01 | `POST /events` accepts `sale.completed` without human prompt | 🟢 PASS | `live-post-events-response.json` | HTTP 201; `event.accepted` logged |
| F02 | Observer starts exactly one investigation per accepted sale | 🟢 PASS | `autonomy-sequence-full.txt` | one `investigation_id` per accepted event |
| F03 | Investigator collects versioned EvidenceBundle through allow-listed tool registry | 🟢 PASS | `autonomy-sequence-full.txt` | 6 READ tools `ok=True`; `is_sufficient=True` |
| F04 | Planner proposes **2–3** bounded candidate actions bound to evidence | 🔴 FAIL | `autonomy-sequence-full.txt` | `decisions=1` via **deterministic** planner, not 2–3 LLM candidates |
| F05 | Simulator clones Live Twin and scores candidates with `simulation-kpi-v1` | 🔴 FAIL | `cloudsigning-decision-store-unavailable.json` | `SimulationStoreUnavailable` |
| F06 | Decision Context Guard (6 gates) returns ALLOW/DENY/REFRESH_REQUIRED/HUMAN_REVIEW | 🔴 FAIL | `cloudsigning-decision-store-unavailable.json` | `DecisionStoreUnavailable`; no verdict produced |
| F07 | No-Stale-Commit re-checks Live Twin versions before commit | ⛔ BLOCKED | `autonomy-sequence-full.txt` | run aborts before the guard; never reached |
| F08 | HMAC-signed single-use authorization issued on `ALLOW` | ⛔ BLOCKED | `autonomy-sequence-full.txt` | never reached |
| F09 | Guarded Executor commits to Live Twin atomically (Firestore) | ⛔ BLOCKED | `autonomy-sequence-full.txt` | never reached |
| F10 | Verifier re-reads Live Twin and reports VERIFIED/REGRESSION/INCONCLUSIVE | ⛔ BLOCKED | `autonomy-sequence-full.txt` | never reached |
| F11 | Auto-replan on `REFRESH_REQUIRED` discards binding and replans | ⛔ BLOCKED | `autonomy-sequence-full.txt` | never reached |
| F12 | Agent-action audit trail written to BigQuery `retailtwin.agent_action_audit` | 🔴 FAIL | `bq-dataset-tables.json`, `bq-agent-actions-count.json` | table **absent**; `agent_actions` has **0** rows; runtime SA has no BigQuery write role |

## §2 — Runtime and platform (G01–G10)

| Row | Requirement | Status | Durable evidence | Note |
|---|---|---|---|---|
| G01 | Cloud Run `retailtwin-api` deployed in `us-central1` | 🟢 PASS | `cloudrun-service.json`, `live-version.json` | revision `00053-6k7`, 100% traffic, `GIT_SHA=920e166f…` |
| G02 | `GET /health`, `/ready`, `/store` return 200 on deployed Cloud Run | 🟢 PASS | `live-health.json`, `live-ready.json`, `live-store.json` | `/store` → 557 products |
| G03 | `LIVE_TWIN_BACKEND=firestore` on deployed Cloud Run | 🟢 PASS | `cloudrun-env-summary.txt` | Firestore inventory (557 SKUs) matches live `/store` exactly |
| G04 | `LLM_PROVIDER=vertex_gemini` with ADC auth (no API key) | 🟢 PASS | `cloudrun-env-summary.txt`, `vertex-gemini-toolcall.json` | ADC token; no API-key variable in deployment env |
| G05 | Vertex Gemini `gemini-2.5-flash` live tool call succeeds | 🟢 PASS | `autonomy-sequence-full.txt` | deployed investigator issued and executed 6 live tool calls. Contradiction logged — see §6 item 7 |
| G06 | One `get_inventory` tool call via Vertex adapter | 🟢 PASS | `autonomy-sequence-full.txt` | `tool name=get_inventory capability=READ ok=True` |
| G07 | Firestore `stores/store-001/inventory` has 20 SKUs (P001–P020) | 🟢 PASS | `live-store.json` | 557 distinct SKUs after full pagination; P001–P020 present |
| G08 | BigQuery `retailtwin.sales_events` has historical data | 🟢 PASS | `bq-sales-events-by-day-sku.json` | 49 rows, 2 SKUs, 1 store, 1 event type — thin, see §6 item 8 |
| G09 | Pub/Sub `store-events` topic exists and accepts events | 🟢 PASS | `pubsub-subscription-store-events-agent.json` | publish accepted, message ID `22453167541411325` |
| G10 | Firebase Hosting `retailtwin-ai-511002.web.app` serves frontend | 🟢 PASS | `firebase-hosting-site.json`, `firebase-hosting-releases.json`, `live-frontend-index.html` | HTTP 200, HTML served |

## §3 — UX and 3D (U01–U06)

| Row | Requirement | Status | Durable evidence | Note |
|---|---|---|---|---|
| U01 | 3D store renders with shelves A01, A02, B01, B02 | ⛔ BLOCKED | `live-store.json` | required proof type is the demo video, which does not exist; live `/store` does expose those shelf IDs |
| U02 | 3D move cue: product hops from source to destination slot | 🟢 PASS | `docs/CLOUD_RUNTIME_MATRIX.md`, `apps/web/src` cues | code review (ADR 0022), `moveCue` implemented |
| U03 | 3D facings cue: capacity enforcement and overflow flag | 🟢 PASS | `apps/web/src` cues | `facingsCue` implemented |
| U04 | 3D replenishment cue: `Shelf +N` / `Backroom -N` on product card | 🟢 PASS | `apps/web/src` cues | `replenish` cue implemented |
| U05 | Agent Activity panel shows 8-stage evidence timeline | 🟢 PASS | `apps/web/src`, ADR 0037 | component present (code-review criterion); live feed is empty — tracked under D08 |
| U06 | Live Twin state reflects committed changes (shelf, facings) | ⛔ BLOCKED | `live-inventory-P017.json` | no commit occurred (run aborted pre-commit); live P017 conflicts with both fixtures — §6 item 4 |

## §4 — Deployed smoke rows (D-S01–D-S12)

| Row | Requirement | Status | Durable evidence | Note |
|---|---|---|---|---|
| D-S01 | Backend liveness: `GET /health` → 200, `app_env=production` | 🟢 PASS | `live-health.json` | `app_env=production`, `git_sha=920e166f…` |
| D-S02 | Backend readiness: `GET /ready` → 200 | 🟢 PASS | `live-ready.json` | `ready=true` |
| D-S03 | Firestore-backed `GET /store` → store-001 with products | 🟢 PASS | `live-store.json` | store-001, 557 products |
| D-S04 | P001 inventory read: HTTP 200, all required fields | 🟢 PASS | `live-inventory-P001.json` | all fields present |
| D-S05 | P017 inventory read: HTTP 200, competition fixture present | 🔴 FAIL | `live-inventory-P017.json` | HTTP 200 but live values (shelf 12, facings 3) contradict the documented fixture (shelf 8, facings 2) |
| D-S06 | BigQuery `sales_events` query under byte cap | 🟢 PASS | `bq-sales-events-by-day-sku.json` | 49 rows, well under cap |
| D-S07 | Pub/Sub deterministic event published to `store-events` | 🟢 PASS | `pubsub-push-config-summary.txt` | publish accepted — but push delivery 401, see D-S08 |
| D-S08 | Agent Activity: `/agent/events` shows activity for smoke run | 🔴 FAIL | `live-agent-events.json` | `{"events":[],"cursor":null}`; Firestore activity collections empty |
| D-S09 | Vertex Gemini live `generateContent` → HTTP 200 | 🟢 PASS | `vertex-gemini-toolcall.json` | HTTP 200 |
| D-S10 | Simulation safe outcome: `sim-seed-001` status=pending | 🔴 FAIL | `live-simulations-seed-001-raw.txt` | **HTTP 500** on the active revision |
| D-S11 | No secrets in captured endpoint output | 🟢 PASS | bundle-wide secret-pattern scan | clean; only `.env.example` is tracked in git |
| D-S12 | Firebase Hosting frontend reachable, serves HTML | 🟢 PASS | `live-frontend-index.html`, `live-frontend-headers.txt` | HTTP 200, HTML |

## §5 — Workload identity and runtime IAM (W01–W04)

| Row | Requirement | Status | Durable evidence | Note |
|---|---|---|---|---|
| W01 | Workload Identity Federation pool + provider configured | 🟢 PASS | `wif-providers.json`, `wif-summary.txt` | pool `github-actions-pool`, provider ACTIVE |
| W02 | `github-actions@…` has Cloud Run deploy role | 🟢 PASS | `iam-project-policy.json` | `roles/run.admin` |
| W03 | `retailtwin-api@…` has Firestore + BigQuery + Pub/Sub roles | 🔴 FAIL | `iam-project-policy.json`, `iam-summary-final.txt` | Firestore ✅ (`datastore.user`), Pub/Sub ✅ (`pubsub.publisher`), BigQuery read ✅ (`viewer`) — but **no BigQuery write role** and **no `serviceAccountTokenCreator`** → F12 and the Pub/Sub push OIDC both impossible |
| W04 | No long-lived JSON service account keys | 🟢 PASS | `iam-runtime-sa.json` | every inspected key is `SYSTEM_MANAGED` |

## §6 — Gate results and documentation rows

### Gate results

| Gate | Status | Durable evidence | Note |
|---|---|---|---|
| G02 Twin Control (#49) | 🟢 PASS | `document-checklist-at-submission-sha.txt` | closed #314; verified at its gate-run SHA |
| G03 Autonomous (#50) | 🔴 FAIL | `autonomy-sequence-full.txt` | in-process gate passes 8/8, but the **deployed** run aborts: `status=failed reason=SimulationStoreUnavailable` |
| G04 Guard (#51) | 🔴 FAIL | `cloudsigning-decision-store-unavailable.json` | no DCG verdict produced in the deployed path |
| G05 Live Commit (#52) | 🔴 FAIL | `live-inventory-P017.json`, `bq-agent-actions-count.json` | no live commit; audit table absent |
| G06 Submission (#53) | 🔴 FAIL | `github-actions-runs-at-submission-sha.txt` | 20-row matrix exists only in-process and locally (`9b56f11d`, not on `origin`); `run-submission-gate-cloudrun.sh` is a stub exiting 78; `run-submission-gate.sh` is fail-open |

### Documentation rows (D01–D15 of the checklist's documentation table)

| Row | Requirement | Status | Durable evidence |
|---|---|---|---|
| D01 | `README.md` current with architecture, setup, deployment | 🟢 PASS | `document-checklist-at-submission-sha.txt` |
| D02 | `docs/COMPETITION_README.md` | 🟢 PASS | `document-checklist-at-submission-sha.txt` |
| D03 | `docs/SUBMISSION_DECK.md` | 🟢 PASS | `document-checklist-at-submission-sha.txt` |
| D04 | `docs/SUBMISSION_INDEX.md` | 🟢 PASS | `document-checklist-at-submission-sha.txt` |
| D05 | `docs/ARCHITECTURE_DIAGRAM.md` | 🟢 PASS | `document-checklist-at-submission-sha.txt` |
| D06 | `docs/ARCHITECTURE.md` | 🟢 PASS | `document-checklist-at-submission-sha.txt` |
| D07 | `docs/DEMO_AND_ACCEPTANCE.md` | 🟢 PASS | `document-checklist-at-submission-sha.txt` |
| D08 | `docs/CLOUD_RUNTIME_MATRIX.md` | 🟢 PASS | `document-checklist-at-submission-sha.txt` — **content contradicts deployed reality, see §7 item 11** |
| D09 | `docs/DOMAIN_AND_DATA_MODEL.md` | 🟢 PASS | `document-checklist-at-submission-sha.txt` |
| D10 | `docs/CURRENT_STATUS.md` | 🟢 PASS | `document-checklist-at-submission-sha.txt` — **content contradicts deployed reality, see §7 item 11** |
| D11 | ADRs 0001–0023, 0037, 0039, 0040, 0041 merged on `main` | 🟢 PASS | `document-checklist-at-submission-sha.txt` | all six ADR identifiers verified present at the submission SHA |
| D12 | `docs/demo-video/shot-list.md` | 🟢 PASS | `document-checklist-at-submission-sha.txt` | contains the P017 contradiction, §7 item 4 |
| D13 | `docs/demo-video/production-checklist.md` | 🟢 PASS | `document-checklist-at-submission-sha.txt` | |
| D14 | `docs/demo-video/acceptance-criteria.md` | 🟢 PASS | `document-checklist-at-submission-sha.txt` | |
| D15 | `docs/licensing/CONTRIBUTOR-LICENSE-PROVENANCE.md` | 🔴 FAIL | `document-checklist-at-submission-sha.txt` | **absent at `920e166f`** — exists only on PR #407 |

> Note: `docs/demo/README.md` **is** present at `920e166f`. Top-level `demo/` and `demo/README.md` are **absent**. These are distinct paths and are not collapsed here.

## §7 — Competition requirements (CR01–CR12)

| Row | Requirement | Status | Durable evidence | Note |
|---|---|---|---|---|
| CR01 | Live 3D Digital Twin (not decorative) | 🟢 PASS | `live-store.json`, `apps/web/src/state/twin.store.ts` | `/store` drives the 3D scene |
| CR02 | Autonomous: no human prompt to trigger investigation | 🟢 PASS | `autonomy-sequence-full.txt` | event → observer → investigation, unattended |
| CR03 | AI gathers evidence, plans, simulates before acting | 🔴 FAIL | `autonomy-sequence-full.txt` | evidence ✅, plan ✅, **simulation ✗** |
| CR04 | Safety: DCG prevents stale/invalid commits | 🔴 FAIL | `cloudsigning-decision-store-unavailable.json` | guard never reached; commit path unproven |
| CR05 | Google AI (Gemini on Vertex AI) for inference | 🟢 PASS | `vertex-gemini-toolcall.json`, `cloudrun-env-summary.txt` | `LLM_PROVIDER=vertex_gemini`, ADC, live tool calls executed — see §7 contradiction 7 |
| CR06 | Google Cloud: Cloud Run, Firestore, BigQuery, Pub/Sub | 🔴 FAIL | `iam-project-policy.json`, `cloudsigning-pubsub-push-401.json` | all four services present, but the Pub/Sub→agent path is 401 and BigQuery write is unavailable |
| CR07 | Firebase Hosting for web delivery | 🟢 PASS | `firebase-hosting-releases.json` | |
| CR08 | Reproducible flagship scenario | 🔴 FAIL | `github-actions-runs-at-submission-sha.txt` | matrix not durable; gate runner fail-open; `/simulations` 500 |
| CR09 | Demo video under required duration | 🔴 FAIL | §7 item 3 | no MP4, no SRT, no published URL |
| CR10 | Public repository | 🟢 PASS | `gh api repos/vinhphan812/retailtwin-ai` → `public` | |
| CR11 | No secrets/credentials in repo | 🟢 PASS | `github-actions-ci-hygiene-conflict-version-steps.txt` | CI secret scan `success` at the SHA; bundle scan clean |
| CR12 | License declared | 🔴 FAIL | upstream audit `t_57fcdbdf`; `document-checklist-at-submission-sha.txt` | `MISSING at 920e166f` → `DECLARED` only after one licence PR merges → `VERIFIED` only with contributor authority |

## §8 — Missing, contradictory and stale evidence

| # | Item | Class | Detail |
|---|---|---|---|
| 1 | CR12 licence material | **missing** | No root `LICENSE`, no `THIRD_PARTY_NOTICES.md` at `920e166f`; GitHub licence detector reports none. MIT text exists only on OPEN PRs #398 (`ebb70b64`) and #397 (`4fae32de`) with byte-identical blobs — exactly one may be merged. |
| 2 | Contributor authority | **missing** | No CLA / CONTRIBUTING / copyright-holder record for the MIT grant (10 human contributors). CR12 cannot reach 🟢 without it. |
| 3 | Demo video | **missing / contradicted** | No MP4, no SRT, no published URL, no evidence bundle in any git ref, deployed surface, GCS/Firebase Storage, or checked local media dir. Delivery card `t_447662e4` claims a 165-second MP4 — **not found**. |
| 4 | P017 three-way conflict | **contradictory** | `docs/demo-video/shot-list.md`: shelf 8 / backroom 54 · `data/schemas/store-state.demo.json`: shelf 8 / backroom 35 · live Firestore: shelf 12 / facings 3, `version=1`. No durable explanation reconciles them. |
| 5 | Final-SHA gate package durability | **missing** | `docs/evidence/submission-gates/2026-10-25-deployed-920e166f/` exists only in local worktree `t_b539a304` (commit `9b56f11d`); not reachable from any `origin` branch or PR head. |
| 6 | Container licence notice | **missing** | `.dockerignore` excludes `LICENSE` and the Dockerfile never copies it → the live image ships first-party MIT source with no MIT notice; the hosted site serves SPA HTML at `/LICENSE`. |
| 7 | Vertex function-call evidence | **contradictory** | Standalone probes of `gemini-2.5-flash` with explicit `get_inventory` declarations and `toolConfig.functionCallingConfig.mode="ANY"` returned `finishReason: STOP`, `functionCall: NONE`, text instead of a function call (`vertex-gemini-toolcall.json`). The **deployed** run nevertheless executed six live tool calls, so G05/G06 rest on deployed evidence, not on the probe. The probe is reported as-is and is **not** claimed as proof of a function call. |
| 8 | BigQuery event volume | **weak** | `sales_events` holds only 49 rows, 2 distinct SKUs, 1 store and 1 event type. It does not independently demonstrate broad event coverage. |
| 9 | BigQuery audit target | **contradictory** | The checklist names `retailtwin.agent_action_audit`; that table **does not exist**. The dataset contains `agent_actions` (0 rows), `inventory_events`, `sales_events`. The runtime SA has no BigQuery write role, so the audit insert cannot succeed even if the table existed. |
| 10 | CI at the submission SHA | **failing** | API CI run `39894366963` concluded **failure** (Trivy could not auth to GCR — `docker-credential-gcloud` absent). Release Gate runs `39895459588` / `40118447542` concluded **failure** via the fail-closed Same-SHA CI barrier, leaving all 12 deployed-stack smoke steps **skipped**, never green. |
| 11 | Documentation vs deployed reality | **contradictory** | `docs/CLOUD_RUNTIME_MATRIX.md` and `docs/CURRENT_STATUS.md` describe the Pub/Sub and autonomy paths as operational, while deployed logs show HTTP 401 on the push path and `SimulationStoreUnavailable`/`DecisionStoreUnavailable` on the persistence path. |
| 12 | Live `/simulations/sim-seed-001` | **failing** | HTTP 500 on the active revision `00053-6k7` — pre-existing, tracked as `t_d8476d4b`. |
| 13 | Checklist file conflict | **procedural** | PR #407 owns the checklist wording. If a licence PR merges first, `docs/FINAL_SUBMISSION_VALIDATION_CHECKLIST.md` conflicts — resolve in favour of the **#407** wording. |

## §9 — Remediation list (required before any sign-off)

1. **Merge exactly one licence PR** (#398 `ebb70b64` **or** #397 `4fae32de` — byte-identical blobs, not both) and record contributor authority (CLA or written confirmation from `anh-nguyen-3103`, `k-pham08`, `longshaww`). → `t_bee77d54`, `t_0a0dd267`, `t_85565f08`, `t_86107ed9`
2. **Ship the licence notice with the artefacts** — un-exclude `LICENSE` from `.dockerignore`, copy it in the Dockerfile, and publish the repository licence on the hosted site. → `t_f34e7fb6`
3. **Repair the deployed Firestore token path** — make `firestore_decisions.py` / `firestore_simulations.py` / `firestore_agent_activity.py` use the same working Application Default Credentials mechanism as `firestore_twin.py`. → `t_d8476d4b`
4. **Configure Pub/Sub push OIDC** — attach an `oidcToken` (service account `service-537192856637@gcp-sa-pubsub.iam.gserviceaccount.com`, audience = the Cloud Run service URL) to subscription `store-events-agent`, grant that account `serviceAccountTokenCreator` on `retailtwin-api@…`, and confirm `_verify_pubsub_push_bearer` accepts it.
5. **Grant the runtime SA BigQuery write** on `retailtwin-ai-511002.retailtwin` and reconcile the audit table name (`agent_action_audit` vs `agent_actions`) with the code in `apps/api/retailtwin_api/audit/trail.py`.
6. **Fix the planner** so it proposes **2–3** bounded candidates bound to collected evidence (deployed run produced `decisions=1` via the deterministic path).
7. **Reconcile P017** — align `docs/demo-video/shot-list.md`, `data/schemas/store-state.demo.json` and live Firestore to one value, or document the legitimate commit mutation.
8. **Produce and publish the demo video** (MP4 ≤ 3:00, English narration, SHA + deployed-URL overlay) and record its URL in `demo/README.md`; correct the contradictory `t_447662e4` claim. → `t_447662e4`
9. **Publish the gate package on an `origin` ref** — re-run G03–G06 against the deployed revision and commit `docs/evidence/submission-gates/<timestamp>-deployed-<newsha>/` with `SHA256SUMS.txt` reachable from `origin` or a PR head.
10. **Fix CI at the new SHA** — land the release-gate/scan fixes so API CI and Release Gate conclude success at the submission SHA and the 12 deployed-stack smoke steps actually run rather than being skipped. → `t_1b643909`, `t_c4d76fb8`
11. **Correct the conflicting documentation** in `docs/CLOUD_RUNTIME_MATRIX.md` and `docs/CURRENT_STATUS.md` once the Pub/Sub and persistence paths are genuinely healthy.
12. **Re-run this reconciliation** under the resulting canonical SHA — every row above must be re-verified against the new SHA and the new active Cloud Run deployment.

## §10 — Sign-off

**Not signed off.** The submission remains **BLOCKED**. Rows F04, F05, F06, F12, D-S05, D-S08, D-S10, W03, D15, G03–G06 and CR03, CR04, CR06, CR08, CR09, CR12 are failed or blocked. Sign-off may be reconsidered only after §9 is complete and this checklist is re-verified against the resulting submission SHA and its active Cloud Run deployment.
