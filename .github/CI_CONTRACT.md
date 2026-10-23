# CI Contract — Required Merge Gate for `main`

> **Issue:** [#142][issue-142] — CI Canonical Required Checks
> **Enforced on:** `main` branch (branch protection rules)
> **Last updated:** 2026-10-20  # routing + deploy-gate + release-smoke scope

---

## Required Status Checks

The following check names are required by branch protection on `main` and must
remain stable:

| Required check name | Workflow | Contract |
|---|---|---|
| `Repository Hygiene` | [`ci.yml`](workflows/ci.yml) | Always runs: conflict markers, workflow YAML validity, and secret/.env checks. |
| `API Build & Test` | [`ci.yml`](workflows/ci.yml) | Green after the API executor succeeds, or green explicit no-op when the API surface is inapplicable. |
| `API E2E Smoke` | [`ci.yml`](workflows/ci.yml) | Green after the API E2E executor succeeds, or green explicit no-op when the API surface is inapplicable. |
| `Web Build & Test` | [`ci.yml`](workflows/ci.yml) | Green after the web executor succeeds, or green explicit no-op when the web surface is inapplicable. |

The three expensive checks use a **stable gate + conditional executor** design.
The named gate is never silently absent: when a suite does not apply, it records
a successful explicit no-op. When it does apply, the gate fails unless its
executor succeeded. This avoids branch-protection deadlocks without treating a
skipped job as an implementation detail of GitHub Actions.

---

## Routing Truth Table

`ci.yml` has no top-level path filter. It derives its routing decision from the
actual diff. The same categories are reflected by the API and web workflows'
path filters.

|| Changed path category | API executor | Web executor | API deploy | Firebase deploy | Release Gate smoke evidence |
||---|:---:|:---:|:---:|:---:|:---:|
|| Docs/repository hygiene | No — explicit no-op | No — explicit no-op | No | No | Gate=no-candidate (all 12 skipped) |
|| API-only | Yes | No — explicit no-op | Yes on successful `main` push | No | Backend only (checks 1–11); frontend skipped |
|| Web-only | No — explicit no-op | Yes | No | Yes on successful `main` push | Frontend only (check 12); backend skipped |
|| Shared contract / workflow-infra | Yes | Yes | Yes on successful `main` push | Yes on successful `main` push | Both surfaces: all 12 checks run |
|| Unknown/unclassified path | Yes — fail closed | Yes — fail closed | Yes only if corresponding workflow ran | Yes only if corresponding workflow ran | Both surfaces (unknown is fail-closed) |

`workflow_dispatch` remains available to operators as an explicit force path.

### Classification rules

- `contracts_changed` is `true` **only** for `contracts/**`. It causes both
  surfaces to run.
- Workflow/infra files are deliberately shared because they can change either
  test/deploy surface.
- The documented docs/hygiene set is the only known no-op class.
- Any unknown path is fail-closed: both expensive suites run. This protects new
  source roots from being accidentally excluded until their routing is documented.
- Run the local deterministic harness after changing this policy:

  ```bash
  bash .github/scripts/test-change-detector.sh
  ```

---

## Deployment and Release-Evidence Semantics

`api.yml` and `web.yml` are independently path-filtered and deploy only for a
successful push to `main` after their respective build/test chain completes.
Each deploy job additionally verifies its workflow actually ran for the triggering
SHA (defence against manual `workflow_dispatch` without matching changes).
There is no deployment for docs-only changes.

`release-gate.yml` is **not** a deploy selector. A completed upstream workflow
becomes a release candidate only when its own matching deployment job succeeded
for the same SHA:

- `API CI` → `Deploy to Cloud Run (production)`;
- `Web CI / CD` → `Deploy to Firebase Hosting`.

API-only and web-only releases are valid, independently evidenced releases;
Release Gate does not require both workflows for every SHA. Shared contract and
workflow/infra changes can produce two scoped release-evidence runs—one for each
successful deployment. A non-deploy, failed, cancelled, or docs-only upstream
run exits the gate successfully as a **no-candidate** result, avoiding a
secondary expected failure.

**Release Gate smoke scope:** The gate tracks which upstream CI (`API CI`,
`Web CI / CD`) actually ran for the SHA. Smoke jobs are gated accordingly:

- Backend smoke (checks 1–11): runs only when `API CI` ran → `api_ci_ran=true`
- Frontend smoke (check 12): runs only when `Web CI / CD` ran → `web_ci_ran=true`

Consequences by change class:

| Change class | Gate result | Backend smoke | Frontend smoke |
|---|---|---|---|
| Docs-only | no-candidate pass | skipped | skipped |
| API-only | scoped pass | runs | skipped |
| Web-only | scoped pass | skipped | runs |
| Shared contract/infra | dual scoped pass | runs | runs |
| Manual dispatch | full pass | runs | runs |

This avoids false failures on single-surface commits while keeping the full
12-check evidence for dual-surface deployments.

---

## Repository Hygiene Checks

`Repository Hygiene` always runs and performs:

1. conflict-marker detection;
2. workflow YAML validation;
3. committed-secret-pattern scanning; and
4. committed `.env` rejection (except explicit template files).

---

## Test Suites

### API Build & Test / API E2E Smoke

- Python 3.11, `mypy`, `pytest`, coverage, forecasting and simulation checks;
- branch-coverage and critical-path policy enforcement; and
- E2E smoke using `FakeLlmProvider` (no real LLM calls).

### Web Build & Test

- Node.js 20.19, TypeScript/Vite production build, Vitest and coverage; and
- validation that `FIREBASE_API_BASE_URL` is set and not localhost.

---

## Adding or Modifying Routed Paths

1. Update the classifier in `ci.yml` and the matching API/web workflow filters.
2. Update `.github/scripts/test-change-detector.sh` with a representative case.
3. Update this truth table and explain any deployment effect.
4. Run the harness and workflow YAML validation.
5. Do **not** remove or rename the required gate jobs without an explicit branch
   protection migration.

## Troubleshooting

### "Required status check not found"

The required job names must exactly match the names in this document. The stable
gate jobs in `ci.yml` deliberately preserve them for every PR.

### "Why did both suites run for a new file path?"

The path was unknown. This is the fail-closed default; classify it explicitly
only after deciding whether it is docs-only, API-only, web-only, or shared.

### "Why did Release Gate not run smoke checks?"

The source run did not contain a successful matching deploy job. Inspect the
source workflow; the Release Gate no-candidate result is intentional and does
not mask deployment failures.

[issue-142]: https://github.com/retailtwin/retailtwin-ai/issues/142

