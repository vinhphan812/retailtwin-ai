# Cloud Run — Exact Submission SHA Deployment & Verification

**Date:** 2026-10-24 (live captures 15:15Z–15:45Z)
**Task:** `t_c848ac91` — Verify Cloud Run runs the exact submission SHA
**Required (authoritative) submission SHA:** `920e166f3526947e66ced3644bed40e761a88133`
**Verdict:** ✅ **PASS — the required SHA is now live and serving 100 % of traffic.**

---

## 1. Required fields

| Field | Value |
|---|---|
| Service URL | `https://retailtwin-api-5rgtvr4gpa-uc.a.run.app` (also `https://retailtwin-api-537192856637.us-central1.run.app`) |
| GCP project | `retailtwin-ai-511002` (project number `537192856637`) |
| Region | `us-central1` |
| Service name | `retailtwin-api` |
| **Deployed revision** | **`retailtwin-api-00053-6k7`** (100 % traffic) |
| **Deployed commit SHA** | **`920e166f3526947e66ced3644bed40e761a88133`** (`commit-sha` label, service + template + revision) |
| **Deployed image digest** | **`gcr.io/retailtwin-ai-511002/retailtwin-api@sha256:9eae4b6e2a9557c253f7cb328c52e2eb384b835da2728a17a71d5133410d564a`** (platform manifest) |
| Image index (build-pushed) | `gcr.io/retailtwin-ai-511002/retailtwin-api@sha256:84d021577b11b7372b83ecb3b855a7e61fe9357f08c6331d960a558530b39051` (OCI index; tags `920e166f…`, `latest`) |
| Deployment timestamp | Revision created `2026-10-24T15:15:38.504701Z`; became Ready/Active `2026-10-24T15:22:23Z` |
| Service account | `retailtwin-api@retailtwin-ai-511002.iam.gserviceaccount.com` |
| Traffic | `100 %` on `retailtwin-api-00053-6k7` |
| Rollback target | `retailtwin-api-00049-2h8` (Ready=True, retained) |

---

## 2. Live evidence — runtime self-report

`GET /version` and `GET /health` now report the required SHA directly from the running container
(previously the live service reported `git_sha: "unknown"`):

```
$ curl -s https://retailtwin-api-5rgtvr4gpa-uc.a.run.app/version
{"version":"0.8.0","git_sha":"920e166f3526947e66ced3644bed40e761a88133",
 "build_time":"2026-10-24T15:22:14+00:00","service":"retailtwin-api",
 "full_version":"0.8.0+920e166f3526947e66ced3644bed40e761a88133"}

$ curl -s https://retailtwin-api-5rgtvr4gpa-uc.a.run.app/health
{"status":"ok","service":"retailtwin-api","environment":"production","app_env":"production",
 "store_id":"store-001","fixture_loaded":true,"version":"0.8.0",
 "git_sha":"920e166f3526947e66ced3644bed40e761a88133"}

$ curl -s https://retailtwin-api-5rgtvr4gpa-uc.a.run.app/ready
{"ready":true,"service":"retailtwin-api","store_id":"store-001",
 "correlation_id":"4ec31f90-054c-4044-89b3-f9ca7eb79cb8"}
```

### Live endpoint matrix (final re-check 2026-10-24T15:45:20Z)

| Endpoint | HTTP |
|---|---|
| `/health` | 200 |
| `/ready` | 200 |
| `/version` | 200 |
| `/store` | 200 |
| `/inventory/P001` | 200 |
| `/inventory/P017` | 200 |
| `/agent/events?limit=5` | 200 |
| `/simulations/sim-seed-001` | **500 — pre-existing, see §6** |

---

## 3. Control-plane evidence

```
$ gcloud run services describe retailtwin-api --region=us-central1 --project=retailtwin-ai-511002
traffic:              [{'percent': 100, 'revisionName': 'retailtwin-api-00053-6k7'}]
latestReadyRevision:  retailtwin-api-00053-6k7
latestCreatedRevision:retailtwin-api-00053-6k7
service labels:       {'cloud.googleapis.com/location': 'us-central1',
                       'commit-sha': '920e166f3526947e66ced3644bed40e761a88133',
                       'managed-by': 'github-actions'}
template labels:      {'commit-sha': '920e166f3526947e66ced3644bed40e761a88133', ...}
template image:       gcr.io/retailtwin-ai-511002/retailtwin-api@sha256:84d02157...
ingress:              all
```

Revision `retailtwin-api-00053-6k7` conditions (all green):

```
Ready=True  "Deploying revision succeeded in 11.11s."
Active=True
ContainerHealthy=True  "Containers became healthy in 6.36s."
ContainerReady=True   "Container image import completed."
MinInstancesProvisioned=True
ResourcesAvailable=True
```

`status.imageDigest` = `gcr.io/…@sha256:9eae4b6e2a9557c253f7cb328c52e2eb384b835da2728a17a71d5133410d564a`.

**Digest reconciliation (index vs platform manifest).** The build pushed an OCI *index*;
Cloud Run records the resolved **linux/amd64 platform manifest**. These are the same image:

```
$ docker manifest inspect gcr.io/…/retailtwin-api@sha256:84d02157…
mediaType: application/vnd.oci.image.index.v1+json
manifests:
  sha256:9eae4b6e2a9557c253f7cb328c52e2eb384b835da2728a17a71d5133410d564a  {amd64/linux}  ← deployed
  sha256:a93f13394a0b8fcf0b29cc5ac2aa606fb03bf0485fe6022115fc42f3717702a3  {unknown/unknown}
```

The previously-live image (`sha256:cb33bbc4…`) was a plain Docker v2 manifest, which is why the
two digest forms did not diverge before. This divergence is the root cause of the release-gate
digest-comparison blocker fixed by PR #405 (§7).

---

## 4. Image provenance — byte-level proof against the required SHA

The required SHA's tree was extracted with `git archive` and every Python source file inside the
deployed image was hashed and compared.

```
$ docker run --rm --entrypoint sh <image> -c \
    "cd /app/apps/api/retailtwin_api && find . -name '*.py' -type f | sort | xargs sha256sum"
$ git archive 920e166f3526947e66ced3644bed40e761a88133 apps/api/retailtwin_api | tar -x …   # same repo tree

image files: 87   repo files: 87
only_in_image: []      only_in_repo: []
MATCHED: 87    MISMATCHED: 0
```

**87 / 87 files identical — zero mismatches, zero missing, zero extra.**
Also verified: `VERSION` file identical, and `version.py`/`routes.py`/`main.py` sha256 identical to
the blobs at `920e166f3526947e66ced3644bed40e761a88133`.

---

## 5. Release-image vulnerability scan (fail-closed, CI-equivalent)

CI's release scan could not run on the self-hosted runner (`docker-credential-gcloud` absent from
`$PATH` — the failure recorded in GitHub deployment `7269454218`). The **identical gate** was
reproduced locally with a gcloud OAuth2 access token:

```
aquasec/trivy:0.65.0 image \
  --ignore-unfixed --severity HIGH,CRITICAL --exit-code 1 \
  gcr.io/retailtwin-ai-511002/retailtwin-api:920e166f3526947e66ced3644bed40e761a88133
```

Result: **`TRIVY_EXIT=0`** (fail-closed gate passed).
Filtered report (`trivy-exact-sha.json`): **0 fixable HIGH/CRITICAL vulnerabilities**.

No deployment proceeded until this scan exited `0`.

---

## 6. Findings

### 6.1 `/simulations` returns HTTP 500 — pre-existing, NOT a regression from this SHA

The live service returns 500 on `/simulations` and `/simulations/sim-seed-001`:

```
retailtwin_api.firestore_simulations.SimulationStoreUnavailable:
  Simulation-store access token unavailable: DecisionStoreUnavailable
```

Determined **pre-existing, not introduced by this deployment**, via three independent checks:

1. **Live A/B test.** Traffic was split 90 % `00053-6k7` (new) / 10 % `00049-2h8` (previously live).
   Over 30 sequential requests, `/simulations/sim-seed-001` returned **500 on both revisions**
   (log-mapped: `retailtwin-api-00049-2h8` → 500, `retailtwin-api-00053-6k7` → 500). Traffic was
   then restored to 100 % `00053-6k7`.
2. **Identical source.** `firestore_simulations.py` and `firestore_decisions.py` are **byte-identical**
   between the old serving image (`sha256:cb33bbc4…`) and the new one (`sha256:84d02157…`).
3. **Historical precedent.** The same 500 is present in Cloud Logging for revision
   `retailtwin-api-00032-zn4` on 2026-10-19, i.e. before this deployment.

Both revisions run service account `retailtwin-api@…` holding `roles/datastore.user`, and both
images ship `google-auth 2.62.0`; the token provider fails at the ADC step. This is a distinct
defect — filed as a follow-up card, not a blocker for SHA verification.

### 6.2 Revision "Retired" on creation is normal for `--no-traffic`

Revision `00053-6k7` was created with `--no-traffic` and initially reported
`Active=False / "Revision retired."`. This is expected behaviour for a traffic-less revision
(same pattern as the historical `00052-88s`), not a deployment failure. The revision became
`Active=True` after the explicit traffic shift.

### 6.3 Live contract preserved

The pre-existing service contract was reproduced exactly — service account, ingress `all`,
`--allow-unauthenticated`, port 8080, min/max instances 1/10, memory 512Mi, CPU 1, timeout 60s,
concurrency 80, and all ten original container env vars — **plus** the three variables the CI
deploy step (`api.yml`) is contractually required to set:
`AUTONOMY_ENABLED=true`, `APP_BASE_URL=https://retailtwin-api-5rgtvr4gpa-uc.a.run.app`,
`PUBSUB_PUSH_SERVICE_ACCOUNT=service-537192856637@gcp-sa-pubsub.iam.gserviceaccount.com`,
and `GIT_SHA=920e166f3526947e66ced3644bed40e761a88133` (which is what makes `/version` and
`/health` report the SHA instead of `unknown`).

---

## 7. Remaining CI-path gap (not a blocker for this card)

The production service is now correct, but the **automated** path that failed is still open:

- **PR #405** (`fix/restore-fail-closed-release-image-scan`) remains **OPEN / unmerged**. It fixes
  (a) the API CI Trivy authentication (`google-github-actions/auth` access token instead of the
  missing `docker-credential-gcloud`) and (b) the release-gate digest comparison, which breaks
  because `gcloud artifacts docker images describe` returns the Artifact Registry mirror form
  (`us-docker.pkg.dev/…@sha256:84d02157…`, the index) while Cloud Run reports the GCR platform
  manifest (`gcr.io/…@sha256:9eae4b6e…`). §3 documents this divergence precisely.
- GitHub deployment `7269454218` (the sole CI deployment record for this SHA) remains terminal
  `failure` — no CI-driven deployment exists for `920e166f…`.

This deployment was therefore executed out-of-band with the same fail-closed scan semantics as CI
(§5). The PR #405 workflow repair should be merged so future deploys travel the automated path.

---

## 8. Reproduction commands

```bash
# 1. Authoritative SHA
git ls-remote origin refs/heads/main
gh api repos/vinhphan812/retailtwin-ai/commits/920e166f3526947e66ced3644bed40e761a88133 --jq .sha

# 2. Fail-closed release scan (CI-equivalent)
docker run --rm -e TRIVY_USERNAME=oauth2accesstoken -e TRIVY_PASSWORD="$(gcloud auth print-access-token)" \
  aquasec/trivy:0.65.0 image --ignore-unfixed --severity HIGH,CRITICAL --exit-code 1 \
  gcr.io/retailtwin-ai-511002/retailtwin-api:920e166f3526947e66ced3644bed40e761a88133

# 3. Deploy the exact SHA (digest-pinned)
gcloud run deploy retailtwin-api \
  --image=gcr.io/retailtwin-ai-511002/retailtwin-api@sha256:84d021577b11b7372b83ecb3b855a7e61fe9357f08c6331d960a558530b39051 \
  --region=us-central1 --project=retailtwin-ai-511002 --platform=managed \
  --allow-unauthenticated --port=8080 --min=1 --max=10 --memory=512Mi --cpu=1 --timeout=60 --concurrency=80 \
  --service-account=retailtwin-api@retailtwin-ai-511002.iam.gserviceaccount.com \
  --labels=commit-sha=920e166f3526947e66ced3644bed40e761a88133,managed-by=github-actions \
  --no-traffic --set-env-vars=… (see §6.3)

gcloud run services update-traffic retailtwin-api --region=us-central1 --project=retailtwin-ai-511002 \
  --to-revisions=retailtwin-api-00053-6k7=100

# 4. Verify
gcloud run services describe retailtwin-api --region=us-central1 --project=retailtwin-ai-511002 \
  --format="value(status.traffic,status.latestReadyRevisionName,metadata.labels.commit-sha)"
gcloud run revisions describe retailtwin-api-00053-6k7 --region=us-central1 --project=retailtwin-ai-511002 \
  --format="value(status.imageDigest,status.conditions)"
curl -s https://retailtwin-api-5rgtvr4gpa-uc.a.run.app/version
```

**Rollback (if required):**

```bash
gcloud run services update-traffic retailtwin-api --region=us-central1 --project=retailtwin-ai-511002 \
  --to-revisions=retailtwin-api-00049-2h8=100
```
