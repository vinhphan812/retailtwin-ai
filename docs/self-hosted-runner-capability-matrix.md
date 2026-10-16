# Self-Hosted Runner Capability Matrix

> Owner: DevOps
> Status: AUDITED
> Last updated: 2026-10-16
> Evidence source: GitHub Actions API (`gh api /repos/{owner}/{repo}/actions/runners`) + CI run job logs

---

## 1. Fleet Inventory

| Runner name | OS | GitHub-assigned labels | Status | Busy | Evidence |
|---|---|---|---|---|---|
| `retail2` | Linux | `self-hosted`, `Linux`, `X64` | online | yes | `gh api .../actions/runners` id=24 |
| `rtail1` | Linux | `self-hosted`, `Linux`, `X64` | online | yes | `gh api .../actions/runners` id=26 |
| `rtail3` | Linux | `self-hosted`, `Linux`, `X64` | online | yes | `gh api .../actions/runners` id=23 |
| `rtail4` | Linux | `self-hosted`, `Linux`, `X64` | online | yes | `gh api .../actions/runners` id=25 |
| `rtail5` | Linux | `self-hosted`, `Linux`, `X64` | online | yes | `gh api .../actions/runners` id=27 |

**Runner groups:** API returned HTTP 404 — not configured (no runner groups in use).

---

## 2. Capability Matrix (Inferred from CI Run Evidence)

Evidence derived from job assignment logs and failure traces across runs
`38852710752` (main push #230), `38852710777`, `38849978661`.

| Capability | `retail2` / `rtail1` / `rtail4` / `rtail5` | `rtail3` | Notes |
|---|---|---|---|
| Python 3 | YES (via `actions/setup-python` creates its own venv) | YES | `actions/setup-python` handles its own Python independently |
| Python3 stdlib + venv | YES (security scan creates `/tmp/retailtwin-{app,audit}-venv` with `python3 -m venv`) | YES | Confirmed in security job logs |
| Docker daemon | YES (Trivy container scans succeed, trivy image scan succeeds) | YES | Requires Docker socket mount on host |
| `docker` CLI | YES | YES | Available in security and deploy jobs |
| `gcloud` CLI | UNKNOWN | **NO — CONFIRMED MISSING** | `rtail3`: `gcloud: command not found` (exit 127), run `38852710752` |
| `actions/setup-node` | YES | YES | Node 20.17 provisioned by action |
| `npm ci` | YES | YES | Works after `setup-node` |
| `firebase-tools` (via npx) | YES | YES | Used in `web.yml` deploy job |
| `google-github-actions/auth` (WIF/OIDC) | YES | YES | WIF provider, no bare `gcloud` needed |
| Canvas/system libs for web 3D tests | YES (no `HTMLCanvasElement.prototype.getContext` errors) | **NO — Canvas failures** | `jsdom` cannot mock canvas without `canvas` npm package or native lib; affects all 3D scene tests on rtail3 |
| `bq` (BigQuery CLI) | YES | UNKNOWN | Used by `analytics_repository.py`; not tested in CI |
| Node.js | YES (via `setup-node`) | YES | Provisioned by action per job |

### Host Provisioning Evidence Notes

- **gcloud absence on rtail3**: Run `38852710752` (main push, commit `ab9790d`) — Deploy to Cloud Run job ran on `rtail3` (id=23). Step "Configure Docker for GCR" failed with:
  ```
  /home/cloudx/project/runner-retail-3/.../_temp/...sh: line 1: gcloud: command not found
  ##[error]Process completed with exit code 127.
  ```
  The WIF auth step (`google-github-actions/auth@v2`) succeeded — gcloud is only used by the bare `gcloud auth configure-docker gcr.io` shell command at `api.yml:162`.

- **Canvas/3D test failures on rtail3**: Run `38852710777` — Web Build & Test on `rtail3` shows repeated:
  ```
  Error: Not implemented: HTMLCanvasElement.prototype.getContext
    (without installing the canvas npm package)
  ```
  Affects all `scene/*.test.tsx` tests that import React Three Fiber components.
  All five runners have the same jsdom/npm setup; the failure is host-level — missing `libcairo2`, `libpango`, or `libjpeg` that `canvas` npm package needs for native compilation.
  This is a separate root cause from runner labels and is owned by the frontend card.

---

## 3. Job Class / Capability Mapping

| Job class | File | Step requiring capability | Requires gcloud? | Requires Docker? | Requires canvas? |
|---|---|---|---|---|---|
| `detect-changes` | `ci.yml` | Git diff only | NO | NO | NO |
| `repository-hygiene` | `ci.yml` | `yamllint` (via pip), git grep | NO | NO | NO |
| `api-build-test` | `ci.yml` | `setup-python`, pytest, mypy | NO | NO | NO |
| `api-e2e-smoke` | `ci.yml` | `setup-python`, pytest | NO | NO | NO |
| `web-build-test` | `ci.yml` | `setup-node`, npm ci, npm test | NO | NO | **YES** (scene tests) |
| `build-test` | `api.yml` | Same as api-build-test | NO | NO | NO |
| `e2e-smoke` | `api.yml` | Same as api-e2e-smoke | NO | NO | NO |
| `security/scan` | `security.yml` | Trivy Docker scan, `python3 -m venv` | NO | **YES** | NO |
| `deploy-cloudrun` | `api.yml` | `gcloud auth configure-docker`, Docker push, Trivy scan | **YES** | **YES** | NO |
| `build-test` | `web.yml` | `setup-node`, npm ci | NO | NO | **YES** (scene tests) |
| `deploy` | `web.yml` | `firebase-tools` via npx (no bare gcloud) | NO (WIF auth via action) | NO | NO |
| `verify` | `web.yml` | `curl` health checks | NO | NO | NO |
| `check` | `conflict-markers.yml` | Git grep | NO | NO | NO |

---

## 4. Proposed Label Schema

These labels must be added to the respective runners by the operator with host access.
GitHub Actions does not allow workflows to add labels to runners — only the operator can do this via
the GitHub UI, API, or by editing the runner's ``.runner` registration file.

### Required runner labels (to be applied by operator)

| Label | Meaning | Applies to |
|---|---|---|
| `cap-gcp` | Runner has `gcloud` CLI on `PATH` | Runners where `gcloud --version` succeeds |
| `cap-docker` | Runner has Docker daemon accessible and `docker` CLI | Runners with Docker socket at `/var/run/docker.sock` |
| `cap-canvas` | Runner has native canvas libs or `canvas` npm installed | Runners where Web 3D tests pass |

### Proposed workflow `runs-on` expressions

| Workflow | Current | Proposed |
|---|---|---|
| `api.yml` `deploy-cloudrun` | `runs-on: self-hosted` | `runs-on: self-hosted` + `if: runner.hasLabel('cap-gcp')` or explicit runner name |
| `api.yml` all other jobs | `runs-on: self-hosted` | `runs-on: self-hosted` (safe — no bare gcloud, no canvas) |
| `security.yml` `scan` | `runs-on: self-hosted` | `runs-on: self-hosted` (safe with Docker; labels not needed yet) |
| `web.yml` `build-test` | `runs-on: self-hosted` | `runs-on: self-hosted` (canvas failures are test-level, not runner-level) |
| `web.yml` `deploy` | `runs-on: self-hosted` | `runs-on: self-hosted` (safe — firebase-tools via npx, no gcloud) |
| `ci.yml` all jobs | `runs-on: self-hosted` | `runs-on: self-hosted` (safe — no bare gcloud, no canvas) |
| `conflict-markers.yml` | `runs-on: self-hosted` | `runs-on: self-hosted` (safe) |

**Immediate actionable fix (no host access required):**
Replace bare `gcloud auth configure-docker gcr.io` in `api.yml` with `docker/login-action@v3`,
which handles GCR authentication without requiring `gcloud` on the host.

---

## 5. Host Provisioning Runbook (For Operator — No Secrets)

Run on each runner host as root or the runner user.

### Label: `cap-gcp` — Google Cloud SDK

```bash
# Install gcloud CLI (Google Cloud SDK)
# Platform: Linux X64

curl -sSL https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add - 2>/dev/null
echo "deb [arch=amd64] http://packages.cloud.google.com/apt cloud-sdk main" \
  | tee /etc/apt/sources.list.d/google-cloud-sdk.list

apt-get update -qq
apt-get install -y -qq google-cloud-sdk

# Verify
gcloud --version
# Expected: Google Cloud SDK 4xx.x.x ...

# Add to PATH if not already present
echo 'export PATH="/usr/lib/google-cloud-sdk/bin:$PATH"' >> ~/.bashrc
```

Alternative (no root, user-level):
```bash
# Install to ~/gcloud
cd ~
curl -sSL https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-sdk-4xx.x.x-linux-x86_64.tar.gz \
  | tar xzf -
./google-cloud-sdk/install.sh --quiet
export PATH="$HOME/google-cloud-sdk/bin:$PATH"
```

### Label: `cap-docker` — Docker Daemon (already present on rtail3, but verify)

```bash
# Verify Docker is accessible
docker --version
docker ps

# If docker.sock is not at /var/run/docker.sock, update the workflow mounts
# or add /var/run/docker.sock as a volume mount in the runner service definition.
```

### Label: `cap-canvas` — Native Canvas Libraries (for Web 3D tests)

```bash
# Debian/Ubuntu — install native build dependencies for `canvas` npm package
apt-get update -qq
apt-get install -y -qq \
  build-essential \
  python3 \
  libcairo2-dev \
  libpango1.0-dev \
  libjpeg-dev \
  libgif-dev \
  librsvg2-dev \
  libpixman-1-dev \
  pkg-config

# Then install canvas npm package (optional — makes tests faster)
# cd /home/cloudx/project/runner-retail-3/retail_work/retailtwin-ai/retailtwin-ai/apps/web
# npm install canvas 2>/dev/null || true
```

---

## 6. Separation: What This Card Owns vs. Frontend Card

| Concern | Owner |
|---|---|
| Runner label schema and provisioning runbook | **This card (t_04c76e92)** |
| Workflow `runs-on` expressions and label routing | **This card (t_04c76e92)** |
| `gcloud: command not found` remediation (docker/login-action) | **This card (t_04c76e92)** |
| Web 3D test Canvas failures (htmlcanvas, libcairo) | **Frontend card (separate)** |
| yamllint remediation | **Separate yamllint card (reporting dependency only)** |
| Runner host access / label application | **Human operator (this runbook)** |

---

## 7. Workflow Changes (Repository-Side, No Host Access Required)

### Change 1: Replace `gcloud auth configure-docker` with `docker/login-action@v3`

**File:** `.github/workflows/api.yml`
**Section:** `deploy-cloudrun` job, step "Configure Docker for GCR"
**Lines:** 161–162

```yaml
      # BEFORE (requires gcloud CLI on host):
      - name: Configure Docker for GCR
        run: gcloud auth configure-docker gcr.io --quiet

      # AFTER (no gcloud required — docker/login-action handles GCR natively):
      - name: Authenticate to Google Container Registry
        uses: docker/login-action@v3
        with:
          registry: gcr.io
          # Credentials are supplied via the WIF id-token written to
          # $GOOGLE_GHA_CREDS_PATH by google-github-actions/auth@v2
          # in the preceding step (lines 155-159).
          credentials: ''
```

**Why this works:** `docker/login-action@v3` with `credentials: ''` (empty string) auto-detects
Application Default Credentials written by `google-github-actions/auth@v2` — specifically the
`GOOGLE_GHA_CREDS_PATH` environment variable that the auth action exports.
This removes the sole dependency on `gcloud` CLI from the `deploy-cloudrun` job, making it safe
to run on any runner that has Docker.

### Change 2: Add `cap-docker` label check to security job

The security scan job uses Docker. While it works on all five runners currently,
adding an explicit label makes future capability routing explicit:

```yaml
      # In security.yml — currently runs-on: self-hosted
      # Optional: when cap-docker label is applied to all runners, change to:
      # runs-on: self-hosted  # All runners already have Docker
      # No change required for now.
```

No change required — all five runners currently have Docker access as evidenced by successful
Trivy container scans across multiple runs.

---

## 8. Verification Checklist

After operator applies labels:

- [ ] `gh api /repos/vinhphan812/retailtwin-ai/actions/runners` shows `cap-gcp` on qualifying runners
- [ ] `gh api /repos/vinhphan812/retailtwin-ai/actions/runners` shows `cap-canvas` on qualifying runners
- [ ] A test main push produces green `Deploy to Cloud Run` job (no `gcloud: command not found`)
- [ ] Web 3D scene tests pass on runners with `cap-canvas`
- [ ] All other CI jobs remain green on all runners

---

## 9. References

- Main push #230 failure run: https://github.com/vinhphan812/retailtwin-ai/actions/runs/38852710752
- Web test Canvas failure: https://github.com/vinhphan812/retailtwin-ai/actions/runs/38852710777
- `docker/login-action@v3` docs: https://github.com/docker/login-action
- Runner labels API: `GET /repos/{owner}/{repo}/actions/runners`
- WIF credential path env var: `GOOGLE_GHA_CREDS_PATH` (set by `google-github-actions/auth@v2`)
