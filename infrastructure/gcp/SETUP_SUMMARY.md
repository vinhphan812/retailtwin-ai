# GCP Setup Summary — RetailTwin AI (#9, #81)

## Foundation Status: VERIFIED

All GCP day-0 resources are provisioned and verified. Run `python infrastructure/gcp/verify.py` to re-check.

### Verified Resources

| Resource | Status | Details |
|---|---|---|
| Project | ✓ | `retailtwin-ai-511002`, billing enabled |
| Firestore `(default)` | ✓ | Standard, Native, us-central1, free tier, delete protection on |
| Pub/Sub `store-events` | ✓ | us-central1 storage restriction, `retailtwin-api` has publisher IAM |
| BigQuery `retailtwin` | ✓ | us-central1, on-demand |
| GCS `retailtwin-ai-511002-assets` | ✓ | us-central1, STANDARD, uniform, private |
| Artifact Registry `retailtwin` | ✓ | Docker, us-central1, 0 MB used |
| APIs | ✓ | All 10 required APIs enabled; 5 forbidden APIs off |
| IAM | ✓ | `retailtwin-api`: datastore.user + logging.logWriter; `retailtwin-agent`: aiplatform.user |
| Keys | ✓ | No user-managed keys on either service account |
| Cloud Run | ✓ | No services deployed (ready for issue #9) |
| Secrets | ✓ | None in Secret Manager |
| Budget alert | ⏸ | Needs billing admin — current account cannot manage billing |

### Acceptance Criteria

| # | Criterion | Status |
|---|---|---|
| 1 | `.env` configured with all required variables | ✓ Done |
| 2 | GCP authentication working | ✓ gcloud auth active for `vinhphan812@gmail.com` |
| 3 | Firestore connection verified | ✓ `verify.py` PASS |
| 4 | BigQuery connection verified | ✓ `verify.py` PASS via REST API |
| 5 | Gemini API accessible | ⏸ Needs `GOOGLE_API_KEY` — see #2 |
| 6 | CI/CD service account configured | ✓ `retailtwin-api@...` runtime identity ready |
| 7 | Cloud Run deployment ready | ✓ Artifact Registry ready, Cloud Build enabled |

## Files Created

```
.env                              ← Local overrides (gitignored)
apps/web/.env.local               ← Vite API URL for web dev server
infrastructure/gcp/verify.py     ← Windows-native foundation verification
infrastructure/gcp/AUTHENTICATION.md ← gcloud ADC setup guide
infrastructure/gcp/README.md     ← Updated with verify.py usage
```

## What's Still Needed

### `GOOGLE_API_KEY` (Issue #2)
Gemini calls require an API key. Get one at https://aistudio.google.com/apikey and add to `.env`:

```
GOOGLE_API_KEY=your_key_here
```

The `GEMINI_MODEL` is already set to `gemini-2.0-flash` in `.env`.

### Budget Alert (Billing Admin Required)
The `retailtwin-dev-guard` budget alert requires a billing administrator account.
Current account (`vinhphan812@gmail.com`) lacks billing management permission.

Ask a billing admin to run:
```bash
gcloud billing budgets create \
  --billing-account=YOUR_BILLING_ACCOUNT \
  --billing-project=retailtwin-ai-511002 \
  --display-name=retailtwin-dev-guard \
  --budget-amount=25000VND \
  --calendar-period=month \
  --filter-projects=projects/retailtwin-ai-511002 \
  --threshold-rule=percent=0.5 \
  --threshold-rule=percent=0.9 \
  --threshold-rule=percent=1.0
```

### CI/CD Service Account (Issue #9)
For Cloud Run deployment via GitHub Actions, configure Workload Identity Federation:
1. Enable WI on the `retailtwin-api` service account
2. Create a GitHub OIDC provider
3. Bind the appropriate IAM roles
4. Add secrets to GitHub repository

## Quick Reference

```bash
# Verify foundation (Windows)
python infrastructure/gcp/verify.py

# Re-provision if needed (idempotent)
set CONFIRM_GCP_BOOTSTRAP=yes
python infrastructure/gcp/bootstrap.py

# Start local API
cd apps/api && python -m retailtwin_api

# Start web dev server
cd apps/web && npm run dev
```

## Notes

- `bootstrap.sh` / `bootstrap.py` are idempotent — safe to re-run
- `verify.sh` requires Unix `python3` in PATH — use `verify.py` on Windows
- `bq.cmd` has permission issues on this machine — `verify.py` uses BigQuery REST API instead
- `GOOGLE_API_KEY` is intentionally NOT in `.env.example` — it must be added manually after issue #2
