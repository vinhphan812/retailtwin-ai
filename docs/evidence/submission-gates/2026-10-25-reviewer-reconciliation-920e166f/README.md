# Reviewer Reconciliation Evidence — submission SHA 920e166f

- **Submission SHA:** `920e166f3526947e66ced3644bed40e761a88133`
- **Active deployment:** Cloud Run `retailtwin-api`, `us-central1`, revision `retailtwin-api-00053-6k7`, 100% traffic; live `/version` and `/health` both report `git_sha=920e166f…`
- **Live API:** `https://retailtwin-api-5rgtvr4gpa-uc.a.run.app`
- **Live web:** `https://retailtwin-ai-511002.web.app/`
- **GCP project:** `retailtwin-ai-511002` (numeric project ID `537192856637`)
- **Collected:** 2026-10-25 by the `reviewer` profile for Issue #367

## Contents

| File | What it evidences |
|---|---|
| `FINAL-CHECKLIST-RECONCILIATION.md` | Authoritative row-level reconciliation (PASS / FAIL / BLOCKED + durable evidence link per row) |
| `autonomy-sequence-full.txt` | Deployed autonomy run: event → observer → 6 tool calls → evidence → plans → `status=failed reason=SimulationStoreUnavailable` |
| `autonomy-timeline-reviewer-events.txt` | Same timeline as raw log lines |
| `cloudsigning-decision-store-unavailable.json` | `DecisionStoreUnavailable` / `SimulationStoreUnavailable` tracebacks (100 entries) |
| `cloudsigning-pubsub-push-401.json`, `cloudsigning-pubsub-push-summary.txt` | Pub/Sub push requests reaching Cloud Run and rejected HTTP 401 |
| `pubsub-subscription-store-events-agent.json`, `pubsub-push-config-summary.txt` | Subscription push config with **no `oidcToken`** |
| `iam-project-policy.json`, `iam-runtime-sa.json`, `iam-summary-final.txt` | Project IAM: runtime SA has no `serviceAccountTokenCreator`, no BigQuery write role |
| `live-health.json`, `live-ready.json`, `live-version.json`, `live-store.json` | Live API responses at the submission SHA |
| `live-inventory-P001.json`, `live-inventory-P017.json` | Live P001/P017 inventory (P017 conflict) |
| `live-agent-events.json`, `live-post-events-response.json` | `POST /events` → HTTP 201, but `/agent/events` returns `{"events":[]}` |
| `live-simulations-seed-001-raw.txt`, `live-simulations-seed-001.json` | Live `/simulations/sim-seed-001` → HTTP 500 |
| `live-frontend-index.html`, `live-frontend-headers.txt` | Firebase Hosting reachability |
| `firebase-hosting-site.json`, `firebase-hosting-releases.json` | Hosting site and release metadata |
| `github-actions-runs-at-submission-sha.txt`, `github-actions-jobs-ci-39894366821.txt`, `github-actions-api-ci-job-steps.txt`, `github-actions-web-build-test-steps.txt`, `github-actions-ci-hygiene-conflict-version-steps.txt` | Exact-SHA CI runs, jobs and step conclusions |
| `github-actions-artifacts-*.txt` | Artifacts published by exact-SHA runs |
| `bq-dataset-tables.json`, `bq-sales-events-by-day-sku.json`, `bq-agent-actions-count.json` | BigQuery tables, `sales_events` volume, `agent_actions` = 0 rows, no `agent_action_audit` |
| `vertex-gemini-toolcall.json` | Vertex `gemini-2.5-flash` probes (`finishReason: STOP`, `functionCall: NONE`) |
| `wif-providers.json`, `wif-summary.txt`, `wif-pools-list.json` | Workload Identity Federation pool and provider |
| `cloudrun-service.json`, `cloudrun-env-summary.txt` | Deployed service configuration and environment |
| `document-checklist-at-submission-sha.txt` | Presence/absence of every checklist-referenced document at the SHA |
| `live-revenue.json`, `live-anomalies.json`, `live-flagship-status.json` | Additional live endpoint responses |
| `SHA256SUMS.txt` | Checksums for every file in this bundle |

## Method

Direct inspection only: GitHub REST + `gh`, Cloud Run REST, Cloud Logging REST, Pub/Sub REST, BigQuery REST, Firestore REST, IAM REST, Firebase Hosting REST and live HTTP probes against the active deployment. No claim in the reconciliation rests on an authored summary alone.

## Redaction

No API keys, tokens, passwords, secrets, credentials or connection strings are retained in this bundle. OAuth access tokens were used transiently for API calls only and are not stored. The bundle was scanned for credential patterns before publication.
