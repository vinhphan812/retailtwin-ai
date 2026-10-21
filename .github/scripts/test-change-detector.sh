#!/usr/bin/env bash
# Deterministic local harness for ci.yml's detect-changes path classification.
# Keep API_PATTERNS, WEB_PATTERNS, and CONTRACT_PATHS synchronized with ci.yml.
set -euo pipefail

API_PATTERNS="apps/api services/forecasting services/simulation tests/e2e Dockerfile .github/workflows/ .github/scripts/test-change-detector.sh"
WEB_PATTERNS="apps/web firebase.json .firebaserc .github/workflows/ .github/scripts/test-change-detector.sh"
CONTRACT_PATHS="contracts/"
DOCS_PATTERNS="docs/ README.md CHANGELOG.md .github/CI_CONTRACT.md .github/PULL_REQUEST_TEMPLATE.md .gitignore .editorconfig"

classify() {
  local changed_files="$1"
  local file pattern path
  API_CHANGED="false"
  WEB_CHANGED="false"
  CONTRACTS_CHANGED="false"
  UNKNOWN_CHANGED="false"

  for file in $changed_files; do
    for pattern in $API_PATTERNS; do
      if [[ "$file" == $pattern* ]]; then
        API_CHANGED="true"
        break
      fi
    done

    for pattern in $WEB_PATTERNS; do
      if [[ "$file" == $pattern* ]]; then
        WEB_CHANGED="true"
        break
      fi
    done

    for path in $CONTRACT_PATHS; do
      if [[ "$file" == $path* ]]; then
        API_CHANGED="true"
        WEB_CHANGED="true"
        CONTRACTS_CHANGED="true"
        break
      fi
    done

    RECOGNISED="false"
    for pattern in $API_PATTERNS $WEB_PATTERNS $CONTRACT_PATHS $DOCS_PATTERNS; do
      if [[ "$file" == "$pattern"* ]]; then
        RECOGNISED="true"
        break
      fi
    done
    if [[ "$RECOGNISED" == "false" ]]; then
      UNKNOWN_CHANGED="true"
      API_CHANGED="true"
      WEB_CHANGED="true"
    fi
  done
}

run_case() {
  local name="$1"
  local files="$2"
  local expected_api="$3"
  local expected_web="$4"
  local expected_contracts="$5"
  local expected_unknown="$6"

  classify "$files"
  local actual="api=$API_CHANGED web=$WEB_CHANGED contracts=$CONTRACTS_CHANGED unknown=$UNKNOWN_CHANGED"
  local expected="api=$expected_api web=$expected_web contracts=$expected_contracts unknown=$expected_unknown"

  if [[ "$actual" != "$expected" ]]; then
    echo "FAIL $name: expected $expected; got $actual" >&2
    return 1
  fi
  echo "PASS $name: $actual"
}

run_case "API-only change" \
  "apps/api/retailtwin_api/main.py" \
  true false false false
run_case "Web-only change" \
  "apps/web/src/App.tsx" \
  false true false false
run_case "mixed API+Web change" \
  "apps/api/retailtwin_api/main.py apps/web/src/App.tsx" \
  true true false false
run_case "non-contract API/Web change" \
  "apps/api/retailtwin_api/services/orders.py apps/web/src/pages/Dashboard.tsx" \
  true true false false
run_case "docs-only change" \
  "docs/ARCHITECTURE.md README.md" \
  false false false false
run_case "workflow/infra change" \
  ".github/workflows/ci.yml" \
  true true false false
run_case "unknown change fails closed" \
  "tools/new-generator.yaml" \
  true true false true
run_case "genuine contract change" \
  "contracts/openapi/orders.yaml" \
  true true true false
run_case "contract plus both surfaces" \
  "contracts/openapi/orders.yaml apps/api/retailtwin_api/routes.py apps/web/src/api/orders.ts" \
  true true true false

echo "All change-detector cases passed."

