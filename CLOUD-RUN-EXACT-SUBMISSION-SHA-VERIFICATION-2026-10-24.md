# Cloud Run exact-submission-SHA verification — Issue #367 (2026-10-24)

**VERDICT: BLOCKED.** The Cloud Run service is active and healthy, but it is **not** serving the exact submission commit SHA required by Issue #367. No other branch, commit, image, tag or stale revision has been accepted as substitute evidence.

All values below were re-captured live by the coordinator in this run (2026-10-24), not copied from upstream handoffs.

## 1. Required submission identity (authoritative)

| Field | Value | Provenance (captured this run) |
|---|---|---|
| Repository | `vinhphan812/retailtwin-ai` | `gh auth status` → logged in as `vinhphan812` |
| Authoritative ref | `main` | Issue #367 submission branch |
| **Required commit SHA** | `920e166f3526947e66ced3644bed40e761a88133` | `git ls-remote origin refs/heads/main` → `920e166f3526947e66ced3644bed40e761a88133` |
| Commit subject | `Merge pull request #392 … t_f1fa4c27-p0-fix-flaky-autonomous-trigger-ack-test` | commit URL <https://github.com/vinhphan812/retailtwin-ai/commit/920e166f3526947e66ced3644bed40e761a88133> |
| Deployment record for that SHA | GitHub deployment `7269454218` (ref `main`, environment `production`, task `deploy`) | `gh api repos/vinhphan812/retailtwin-ai/deployments?per_page=5` → `7269454218 920e166f… main production 2026-10-23T03:29:29Z` |
| Deployment terminal state | `failure` at `2026-10-23T03:31:16Z` | `gh api …/deployments/7269454218/statuses` → `failure 2026-10-23T03:31:16Z` |
| Failed job | [Deploy to Cloud Run (production) — job 120224191482](https://github.com/vinhphan812/retailtwin-ai/actions/runs/39894366963/job/120224191482) | Release Gate run `920e166f3` → `completed/failure` (`gh run list --branch main`) |
| Latest `main` workflow results | `Release Gate 920e166f3 completed/failure`, `API CI 920e166f3 completed/failure`, `CI (Required Checks) 920e166f3 completed/success` | `gh run list --branch main --limit 10` |

## 2. Live Cloud Run service (observed)

| Field | Observed value | Source |
|---|---|---|
| Project | `retailtwin-ai-511002` (namespace/project number `537192856637`) | `gcloud run services describe retailtwin-api --project retailtwin-ai-511002 --region us-central1 --format=json` |
| Region | `us-central1` | same |
| Service | `retailtwin-api` (only Cloud Run service in the project) | same |
| Service URL | `https://retailtwin-api-5rgtvr4gpa-uc.a.run.app` (also `https://retailtwin-api-537192856637.us-central1.run.app`) | `status.url` / `run.googleapis.com/urls` annotation |
| **Traffic allocation** | **100 % → `retailtwin-api-00049-2h8`** (single traffic entry) | `status.traffic` = `[{'percent': 100, 'revisionName': 'retailtwin-api-00049-2h8'}]` |
| `latestReadyRevision` | `retailtwin-api-00049-2h8` | `status.latestReadyRevisionName` |
| `latestCreatedRevision` | `retailtwin-api-00052-88s` (retired on creation — 0 % traffic) | `status.latestCreatedRevisionName` |
| Service generation | 59 | `metadata.generation` |
| **Serving image digest** | `gcr.io/retailtwin-ai-511002/retailtwin-api@sha256:cb33bbc47f9311acc684d59cc676c7b8be443212d8aea9fa7871908751ceb1cc` | `gcloud run revisions describe retailtwin-api-00049-2h8` → `status.imageDigest` |
| Serving image tag | `fix-credential` | `gcloud container images list-tags gcr.io/retailtwin-ai-511002/retailtwin-api` → digest `cb33bbc47f93` carries tag `fix-credential` |
| `commit-sha` label (service + template + revision) | `27d8edc14533103ad0aa9228907a9ed617d420b6` | `metadata.labels.commit-sha`, `spec.template.metadata.labels.commit-sha` |
| Revision creation timestamp | `2026-10-19T05:47:39.284798Z` | `metadata.creationTimestamp` |
| Service last updated | `2026-10-20T05:40:00.565074Z` (generation 59) | service annotation / `latestCreatedRevision` |
| Deployer of record | `serving.knative.dev/creator` / `lastModifier` = `vinhphan812@gmail.com`, label `managed-by: github-actions` | service metadata |

### Discrepancy

```text
required : 920e166f3526947e66ced3644bed40e761a88133
live label: 27d8edc14533103ad0aa9228907a9ed617d420b6
live digest: sha256:cb33bbc47f9311acc684d59cc676c7b8be443212d8aea9fa7871908751ceb1cc   (tag: fix-credential)
required-image digest (built, never deployed): sha256:84d021577b11…  (tags: 920e166f…, latest)
```

The live `commit-sha` label does **not** identify the serving image: tag `27d8edc1…` resolves to a different digest (`sha256:06e85dd98694…`). The label is therefore not SHA provenance and must not be read as one.

### Required SHA was never deployed

- Full revision inventory (52 revisions, `gcloud run revisions list --limit=60`): **0** revisions reference `sha256:84d02157…` and **0** carry label `920e166f…` — the required SHA was never promoted.
- The required-SHA image **was** built and pushed (`sha256:84d021577b11…`, tags `920e166f3526947e66ced3644bed40e761a88133` and `latest`) — the build succeeded; only the deploy step was skipped after the fail-closed Trivy release-image scan aborted (`docker-credential-gcloud: executable file not found in $PATH`).

## 3. Live endpoint probes (health only — not identity)

Unauthenticated GET to `https://retailtwin-api-5rgtvr4gpa-uc.a.run.app`:

```text
/health  200 {"status":"ok","service":"retailtwin-api","environment":"production","app_env":"production",
               "store_id":"store-001","fixture_loaded":true,"store_error":null,"version":"0.8.0","git_sha":"unknown"}
/ready   200 {"ready":true,"service":"retailtwin-api","store_id":"store-001","correlation_id":"44fe477c-…"}
/version 200 {"version":"0.8.0","git_sha":"unknown","build_time":"2026-10-23T01:24:41+00:00",
               "service":"retailtwin-api","full_version":"0.8.0+unknown"}
```

`/health` and `/version` report `git_sha: "unknown"`, so the runtime endpoints **cannot** independently prove submission identity. Identity evidence is the Cloud Run revision label + image digest, and they do not match the required SHA.

## 4. Remediation still outstanding (unchanged)

1. Merge PR #405 — `fix(ci): restore fail-closed production image scan and release digest gate`, head `08cd0cbdf6046f2ab1e10e954e28cbc86659b25d`, currently `state: OPEN`, `mergedAt: null` (`gh pr view 405`). The repaired gate has therefore never run on `main`, and `origin/main` is still `920e166f…`.
2. Re-run the API CD workflow on `main` = `920e166f3526947e66ced3644bed40e761a88133` so that the deploy step is actually executed (the image for that SHA already exists in the registry).
3. Move 100 % traffic to a revision whose image digest / `commit-sha` label equals `920e166f3526947e66ced3644bed40e761a88133`, and record its immutable digest and timestamps.
4. Re-run `/health`, `/ready`, `/version`; `/version` must expose a non-`unknown` matching SHA (or document an equivalent authoritative runtime identity mechanism).

**No deployment, workflow re-run, merge or build was triggered by this verification task.** Promoting the submission SHA is an authorised release decision, not a code-local action; this card therefore remains `blocked/needs_input`.

## 5. Reproduction commands

```bash
git ls-remote origin refs/heads/main
gh api repos/vinhphan812/retailtwin-ai/deployments?per_page=5
gh api repos/vinhphan812/retailtwin-ai/deployments/7269454218/statuses
gh run list --branch main --limit 10
gh pr view 405 --json number,state,mergedAt,headRefOid
gcloud run services describe retailtwin-api --region us-central1 --project retailtwin-ai-511002 --format=json
gcloud run revisions describe retailtwin-api-00049-2h8 --region us-central1 --project retailtwin-ai-511002 --format=json
gcloud run revisions list --region us-central1 --project retailtwin-ai-511002 --format="value(metadata.name,status.imageDigest,metadata.creationTimestamp)" --limit=60
gcloud container images list-tags gcr.io/retailtwin-ai-511002/retailtwin-api --format="table(digest,tags)" --limit=60
curl -s https://retailtwin-api-5rgtvr4gpa-uc.a.run.app/health
curl -s https://retailtwin-api-5rgtvr4gpa-uc.a.run.app/ready
curl -s https://retailtwin-api-5rgtvr4gpa-uc.a.run.app/version
```
