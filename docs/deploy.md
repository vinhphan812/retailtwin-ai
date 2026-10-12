# Day-0 FastAPI Cloud Run Deployment

Issue [#9](https://github.com/retailtwin-ai/retailtwin-ai/issues/9)

Reproducible, non-interactive deployment of the RetailTwin API to Cloud Run.
Prerequisites: Docker, Google Cloud SDK (`gcloud`), an active GCP project with billing
enabled and the **Cloud Run API** enabled.

> **Security posture:** non-root container (UID 10001), no service-account key files,
> no secrets baked in, no IAM widening. The default Compute Engine service account
> is used (Cloud Run-managed, short-lived tokens). Secrets live in Secret Manager
> and are injected at runtime via `--set-secrets`.

---

## 1. Build and Push the Container

```bash
# Authenticate Docker to GCR (one-time)
gcloud auth configure-docker gcr.io

# Build (from repo root)
docker build -t retailtwin-api:local .

# Tag for GCR
docker tag retailtwin-api:local \
  gcr.io/retailtwin-ai-511002/retailtwin-api:t_1821a674

# Push
docker push gcr.io/retailtwin-ai-511002/retailtwin-api:t_1821a674
```

Expected output:
```
The push refers to repository [gcr.io/retailtwin-ai-511002/retailtwin-api]
…
t_1821a674: digest: sha256:<IMAGE_DIGEST> size: 856
```

---

## 2. Deploy to Cloud Run

```bash
gcloud run deploy retailtwin-api \
  --image gcr.io/retailtwin-ai-511002/retailtwin-api:t_1821a674 \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8080 \
  --min-instances 0 \
  --max-instances 10 \
  --memory 512Mi \
  --cpu 1 \
  --timeout 60
```

Expected output:
```
Deploying container to Cloud Run service [retailtwin-api] …
Setting IAM Policy......................................done
Creating Revision.....................................................................done
Routing traffic.....done
Done.
Service [retailtwin-api] revision [retailtwin-api-00001-wz4]
  has been deployed and is serving 100 percent of traffic.
Service URL: https://retailtwin-api-<hash>.us-central1.run.app
```

---

## 3. Verify the Deployment

```bash
# Health check
curl -s https://<SERVICE_URL>/health

# Store read
curl -s https://<SERVICE_URL>/store | python -m json.tool
```

Expected output:
```json
{
  "status": "ok",
  "service": "retailtwin-api",
  "environment": "development",
  "store_id": "store-001",
  "fixture_loaded": true
}
```

```json
{
  "store_id": "store-001",
  "context_version": "store-001:v1",
  "version": "v1",
  "products": [
    {
      "store_id": "store-001",
      "sku": "P001",
      "shelf_id": "A01",
      "slot_id": "A01-S01",
      "facings": 3,
      "shelf_quantity": 8,
      "backroom_quantity": 42,
      "version": 1
    }
  ]
}
```

### Revision Evidence

```bash
gcloud run revisions describe retailtwin-api-00001-wz4 \
  --region us-central1 --format=yaml | grep -E "name:|Image:|creationTimestamp:"
```

```
name: retailtwin-api-00001-wz4
creationTimestamp: '2026-10-12T07:53:19.600983Z'
Image: gcr.io/retailtwin-ai-511002/retailtwin-api@sha256:97a6d04…
Service account: 537192856637-compute@developer.gserviceaccount.com
```

---

## 4. Environment Variables (Runtime)

| Variable | Default | Notes |
|---|---|---|
| `PORT` | `8080` | Set by Cloud Run; do not override |
| `UVICORN_HOST` | `0.0.0.0` | Bind address |
| `UVICORN_PORT` | `8080` | Mirror PORT for uvicorn |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `STORE_FIXTURE_PATH` | `data/schemas/store-state.example.json` | Day-0 read model |
| `STORE_ID` | `store-001` | Store scope |
| `APP_ENV` | `development` | Reported by `/health` |

---

## 5. CI/CD Integration

In GitHub Actions, add a job after tests pass:

```yaml
deploy-cloud-run:
  needs: [test]
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: docker/setup-buildx-action@v3
    - id: auth
      uses: google-github-actions/auth@v2
      with:
        workload_identity_provider: projects/<PROJECT_NUMBER>/locations/global/workloadIdentityPools/<POOL>/providers/<PROVIDER>
        service_account: <SA>@retailtwin-ai-511002.iam.gserviceaccount.com
    - uses: docker/build-push-action@v5
      with:
        push: true
        tags: gcr.io/retailtwin-ai-511002/retailtwin-api:${{ github.sha }}
    - name: Deploy to Cloud Run
      uses: google-github-actions/deploy-cloudrun@v2
      with:
        service: retailtwin-api
        region: us-central1
        image: gcr.io/retailtwin-ai-511002/retailtwin-api:${{ github.sha }}
        allow_unauthenticated: true
        port: 8080
        memory: 512Mi
        cpu: 1
        max_instances: 10
    - name: Health check
      run: |
        curl -f https://${{ env.SERVICE_URL }}/health || exit 1
```

---

## 6. Production Hardening (Issue #34)

Production hardening applied after Day-0 proof.

| Feature | Status | Details |
|---|---|---|
| Structured JSON logging | Done | Cloud Logging-compatible JSON per request/event |
| Correlation IDs | Done | `X-Correlation-ID` injected, echoed in response headers |
| Readiness probe | Done | `GET /ready` returns 503 when fixture unavailable |
| Liveness probe | Done | `GET /health` always 200 if container alive |
| Settings validation | Done | `APP_ENV`, `LOG_LEVEL` validated at startup |
| Production env flag | Done | `APP_ENV=production` sets `is_production=True` |
| Min-instances=1 | Planned | Prevents cold-start; configured in CI/script |
| Dedicated service account | Planned | Workload identity for CI; no JSON keys |
| Secret Manager integration | Planned | Store fixture path in Secret Manager |

### Readiness vs Liveness Separation

```
Cloud Run LB
    ├── /health  → liveness probe (always 200 if container alive)
    └── /ready   → readiness probe (200=serve, 503=drain)
```

The readiness probe returns 503 when the store fixture is unavailable, causing Cloud Run to drain traffic away from that instance. This is the correct behavior for a store-read-only service.

### Structured Logs

Every log line is a JSON object:

```json
{"message":"request.start","severity":"INFO","timestamp":"2026-10-12T09:00:00.000Z","correlation_id":"abc-123","method":"GET","path":"/ready","client_host":"192.168.0.1","service":"retailtwin-api","logger":"retailtwin_api.middleware","level":"INFO"}
```

Cloud Logging parses these automatically from container stdout.

---

## 7. Rollback

```bash
# List revisions
gcloud run revisions list --service retailtwin-api --region us-central1

# Route 100% traffic to a previous revision
gcloud run services update-traffic retailtwin-api \
  --to-revisions retailtwin-api-00001-wz3=100 \
  --region us-central1
```

---

## Exclusions (do not attempt in this PR)

- Multi-service mesh / Istio hardening — tracked in issue #34
- Service-account key file creation — use workload identity federation instead
- IAM permission widening beyond the default Cloud Run service account
- Hardcoded secrets in environment variables — use Secret Manager with
  `--set-secrets STORE_FIXTURE_PATH=store-fixture:latest` (Secret Manager setup is out of scope)
- Dedicated CI service account (WIF provider not yet configured in GitHub repo vars)

---

## Files Changed

| File | Purpose |
|---|---|
| `Dockerfile` | Multi-stage build; non-root runtime; uv dependency management |
| `apps/api/retailtwin_api/middleware.py` | Structured JSON logging + correlation ID middleware |
| `apps/api/retailtwin_api/routes.py` | Readiness probe `/ready`; correlation IDs in logs |
| `apps/api/retailtwin_api/settings.py` | Production env guard + settings validation |
| `apps/api/retailtwin_api/schemas.py` | `ReadyResponse`, `app_env` in `HealthResponse` |
| `apps/api/tests/test_health.py` | 12 tests: probes, correlation IDs, settings, logs |
| `.github/workflows/api.yml` | Production `deploy-cloudrun` job (on merge to main) |
| `scripts/deploy-cloudrun.sh` | Local deploy script with verification |
| `.env.example` | Production Cloud Run environment variable hints |
| `docs/deploy.md` | Production hardening docs, structured logging example |
