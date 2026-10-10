# GCP Authentication Guide — RetailTwin AI

## Overview

Local development uses **Application Default Credentials (ADC)** via the gcloud CLI.
No service-account JSON keys are created. Cloud Run uses Workload Identity instead.

## Setup Steps

### 1. Authenticate with gcloud

```bash
gcloud auth login
gcloud auth application-default login
```

Or for a specific account:

```bash
gcloud auth login your-email@gmail.com
gcloud auth application-default login
```

### 2. Verify authentication

```bash
gcloud auth list
gcloud config get-value account
gcloud config get-value project
```

Expected output:
```
ACTIVE: *
ACCOUNT: your-email@gmail.com

retailtwin-ai-511002
```

### 3. Set the active project

```bash
gcloud config set project retailtwin-ai-511002
```

### 4. Verify connectivity

```bash
python infrastructure/gcp/verify.py
```

Expected: exit code 0 (foundation matches) or exit code 2 (foundation matches, budget needs billing admin).

## Service Account Accounts

Two runtime service accounts are configured in GCP:

| Account | Purpose | May do |
|---|---|---|
| `retailtwin-api@...` | API runtime | Firestore read/write, log write, publish to Pub/Sub |
| `retailtwin-agent@...` | Agent runtime | Vertex AI calls only |

Do NOT assign `roles/editor`, `roles/owner`, or `roles/aiplatform.user` to `retailtwin-api`.
Do NOT assign `roles/datastore.user` or `roles/aiplatform.user` to `retailtwin-agent` (it only needs `roles/aiplatform.user`).

## CI/CD

CI/CD uses a dedicated service account authenticated via Workload Identity Federation (WIF).
See `.github/workflows/` for the service account email used by GitHub Actions.

## Local API without GCP

The API starts without GCP credentials using a built-in fixture.
Set `APP_ENV=development` (default) to use the fixture.

To use real GCP:
1. Authenticate with gcloud (steps above)
2. Add `GOOGLE_API_KEY=...` to `.env` for Gemini calls
3. Restart the API

## Troubleshooting

### `google.auth.default` fails

```bash
gcloud auth application-default login
gcloud auth list
```

### Permission denied on GCP resources

Verify the correct project is set:
```bash
gcloud config get-value project
```

If wrong, reset:
```bash
gcloud config set project retailtwin-ai-511002
```

### Budget alert blocked

The 25000 VND budget alert requires a billing admin account.
Ask a billing administrator to run:
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
