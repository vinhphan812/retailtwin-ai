#!/usr/bin/env bash
# Provision Pub/Sub push delivery for the autonomous agent (ADR 0023).
#
# Production is push-only: the `store-events-agent` subscription must deliver
# `store-events` messages to POST /pubsub/agent-events on the same Cloud Run
# instance, and the Pub/Sub push identity must be allowed to invoke it.
#
# This is a one-time, idempotent platform-provisioning step. It is NOT part of
# the per-deploy Cloud Run pipeline: the subscription and its IAM binding are
# project resources, and the deploy pipeline (`.github/workflows/api.yml`)
# only owns the container revision and its environment.
#
# The API refuses push requests that do not satisfy the OIDC contract
# (apps/api/retailtwin_api/routes.py):
#   * `aud` must equal APP_BASE_URL on the service, and
#   * `email` must equal PUBSUB_PUSH_SERVICE_ACCOUNT on the service.
# Both values are set by the deploy pipeline, so the push endpoint URL below
# must be exactly the API_BASE_URL configured on the service.
#
# Usage, from the repository root, with gcloud authenticated:
#   scripts/provision-pubsub-push.sh
#   API_BASE_URL=https://retailtwin-api-5rgtvr4gpa-uc.a.run.app \
#     scripts/provision-pubsub-push.sh
#
# Idempotent: re-running converges the binding and the push config; it never
# recreates the subscription and never touches the analytics subscription.

set -euo pipefail

PROJECT="${PROJECT:-retailtwin-ai-511002}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-retailtwin-api}"
SUBSCRIPTION="${SUBSCRIPTION:-store-events-agent}"
TOPIC="${TOPIC:-store-events}"
# Identity Pub/Sub signs the push OIDC token with when no explicit push
# authentication service account is configured. It is also the identity the
# API binds to (PUBSUB_PUSH_SERVICE_ACCOUNT), so only tokens issued for it can
# invoke the autonomous agent endpoint.
PUSH_IDENTITY="${PUSH_IDENTITY:-service-537192856637@gcp-sa-pubsub.iam.gserviceaccount.com}"
# Optional override. Leave empty to use Pub/Sub's canonical push identity.
# Setting it requires the caller to hold iam.serviceAccounts.actAs on that
# service account, and the API's PUBSUB_PUSH_SERVICE_ACCOUNT must be changed
# to the same value.
PUSH_AUTH_SA="${PUSH_AUTH_SA:-}"
API_BASE_URL="${API_BASE_URL:-https://retailtwin-api-5rgtvr4gpa-uc.a.run.app}"
PUSH_ENDPOINT="${API_BASE_URL}/pubsub/agent-events"

if ! command -v gcloud >/dev/null 2>&1; then
  echo "ERROR: gcloud is not on PATH. Install the Google Cloud CLI first." >&2
  exit 1
fi

echo "=== RetailTwin — Pub/Sub push delivery (ADR 0023) ==="
echo "  Project      : ${PROJECT}"
echo "  Region       : ${REGION}"
echo "  Service      : ${SERVICE}"
echo "  Topic        : ${TOPIC}"
echo "  Subscription : ${SUBSCRIPTION}"
echo "  Push identity: ${PUSH_IDENTITY}"
if [[ -n "${PUSH_AUTH_SA}" ]]; then
  echo "  Push auth SA : ${PUSH_AUTH_SA} (explicit override)"
else
  echo "  Push auth SA : (default — Pub/Sub signs as ${PUSH_IDENTITY})"
fi
echo "  Push endpoint: ${PUSH_ENDPOINT}"

echo ""
echo "[1/4] Ensuring the topic exists..."
if ! gcloud pubsub topics describe "${TOPIC}" --project="${PROJECT}" >/dev/null 2>&1; then
  gcloud pubsub topics create "${TOPIC}" --project="${PROJECT}"
else
  echo "  topic ${TOPIC} already exists"
fi

echo ""
echo "[2/4] Ensuring the agent subscription exists..."
if ! gcloud pubsub subscriptions describe "${SUBSCRIPTION}" --project="${PROJECT}" >/dev/null 2>&1; then
  gcloud pubsub subscriptions create "${SUBSCRIPTION}" \
    --topic="${TOPIC}" \
    --project="${PROJECT}"
fi

echo ""
echo "[3/4] Granting roles/run.invoker on ${SERVICE} to the push identity..."
gcloud run services add-iam-policy-binding "${SERVICE}" \
  --region="${REGION}" \
  --project="${PROJECT}" \
  --member="serviceAccount:${PUSH_IDENTITY}" \
  --role="roles/run.invoker" \
  --quiet

echo ""
echo "[4/4] Pointing ${SUBSCRIPTION} at ${PUSH_ENDPOINT}..."
if [[ -n "${PUSH_AUTH_SA}" ]]; then
  gcloud pubsub subscriptions update "${SUBSCRIPTION}" \
    --project="${PROJECT}" \
    --push-endpoint="${PUSH_ENDPOINT}" \
    --push-auth-service-account="${PUSH_AUTH_SA}" \
    --quiet
else
  gcloud pubsub subscriptions update "${SUBSCRIPTION}" \
    --project="${PROJECT}" \
    --push-endpoint="${PUSH_ENDPOINT}" \
    --quiet
fi

echo ""
echo "=== Result ==="
gcloud pubsub subscriptions describe "${SUBSCRIPTION}" \
  --project="${PROJECT}" \
  --format="value(pushConfig)" 2>/dev/null | sed 's/^/  pushConfig: /'
gcloud run services get-iam-policy "${SERVICE}" \
  --region="${REGION}" \
  --project="${PROJECT}" \
  --format="value(bindings[].members)" 2>/dev/null \
  | tr ',' '\n' | grep -F "${PUSH_IDENTITY}" | sed 's/^/  run.invoker member: /' || true

echo ""
echo "Next: the deployed service must expose the matching OIDC contract."
echo "  APP_BASE_URL=${API_BASE_URL}"
echo "  PUBSUB_PUSH_SERVICE_ACCOUNT=${PUSH_IDENTITY}"
echo "Both are set by .github/workflows/api.yml (deploy-cloudrun env_vars)."
