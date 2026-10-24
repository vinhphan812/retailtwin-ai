# Cloud Run submission-SHA re-verification — 2026-10-24

## Verdict

**BLOCKED.** The Cloud Run service is healthy, but it is not serving the exact submission commit required by Issue #367. No other branch, image, revision, or deployment has been substituted as valid evidence.

## Required submission identity

| Field | Verified value |
|---|---|
| Authoritative ref | `origin/main` |
| Required commit SHA | `920e166f3526947e66ced3644bed40e761a88133` |
| Commit timestamp | `2026-10-23T03:19:07Z` |
| Commit | [Merge pull request #392 — P0 Fix flaky autonomous-trigger ack test](https://github.com/vinhphan812/retailtwin-ai/commit/920e166f3526947e66ced3644bed40e761a88133) |
| Exact-SHA deployment record | [GitHub deployment 7269454218](https://api.github.com/repos/vinhphan812/retailtwin-ai/deployments/7269454218) |
| Deployment created | `2026-10-23T03:29:29Z` |
| Deployment terminal state / timestamp | `failure` / `2026-10-23T03:31:16Z` |
| Deployment log | [Deploy to Cloud Run (production)](https://github.com/vinhphan812/retailtwin-ai/actions/runs/39894366963/job/120224191482) |

The GitHub API returned exactly one deployment for the required SHA. Its deployment job built and pushed an image, then failed at **“Scan release image for fixable critical/high vulnerabilities”**. The subsequent **Deploy to Cloud Run**, autonomous-runtime verification, and production-deployment verification steps were all **skipped**. Therefore no successful Cloud Run promotion record exists for this SHA.

## Active Cloud Run service observed

| Field | Observed value |
|---|---|
| Project | `retailtwin-ai-511002` |
| Region | `us-central1` |
| Service | `retailtwin-api` |
| URL | https://retailtwin-api-537192856637.us-central1.run.app |
| Revision receiving traffic | `retailtwin-api-00049-2h8` (100%) |
| Revision created / ready | `2026-10-19T05:47:39.284798Z` / `2026-10-19T05:48:10.192554Z` |
| Revision `commit-sha` label | `27d8edc14533103ad0aa9228907a9ed617d420b6` |
| Labeled commit | [fix(api): use WIF impersonation and deploy secrets correctly](https://github.com/vinhphan812/retailtwin-ai/commit/27d8edc14533103ad0aa9228907a9ed617d420b6), `2026-10-14T17:07:59Z` |
| Image digest | `gcr.io/retailtwin-ai-511002/retailtwin-api@sha256:cb33bbc47f9311acc684d59cc676c7b8be443212d8aea9fa7871908751ceb1cc` |
| Cloud Logging evidence | [revision logs](https://console.cloud.google.com/logs/viewer?project=retailtwin-ai-511002&resource=cloud_run_revision/service_name/retailtwin-api/revision_name/retailtwin-api-00049-2h8&advancedFilter=resource.type%3D%22cloud_run_revision%22%0Aresource.labels.service_name%3D%22retailtwin-api%22%0Aresource.labels.revision_name%3D%22retailtwin-api-00049-2h8) |

The active revision label SHA is different from the required SHA:

```text
required: 920e166f3526947e66ced3644bed40e761a88133
live:     27d8edc14533103ad0aa9228907a9ed617d420b6
```

## Live health checks

Fresh unauthenticated GET probes to the service URL returned HTTP 200:

```text
/health  200 {"status":"ok","service":"retailtwin-api",...,"git_sha":"unknown"}
/ready   200 {"ready":true,"service":"retailtwin-api","store_id":"store-001",...}
/version 200 {"version":"0.8.0","git_sha":"unknown","build_time":"2026-10-23T01:24:41+00:00",...}
```

This proves service health only. Because `/health` and `/version` report `git_sha: "unknown"`, the endpoints cannot independently prove submission identity; the active Cloud Run revision label provides the identity evidence and it does not match the submission SHA.

## Required remediation before re-verification

1. Remediate or explicitly adjudicate the failed release-image Trivy gate without weakening the required security gate.
2. Deploy an image built from exactly `920e166f3526947e66ced3644bed40e761a88133`.
3. Preserve evidence that 100% traffic reaches the new ready revision, whose `commit-sha` label equals the required SHA, and record its immutable image digest and timestamps.
4. Re-run `/health`, `/ready`, and `/version`; `/version` must expose a non-unknown matching SHA or another authoritative runtime identity mechanism must be documented.
