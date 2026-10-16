# Day-0 Foundation Gate Runbook

> Companion to [ADR 0028](adr/0028-day-0-foundation-smoke-and-freeze.md) and
> [issue #10](https://github.com/vinhphan812/retailtwin-ai/issues/10).
> Use this runbook to **run the gate**, **interpret the evidence**, and
> **tag `day0-foundation`** on `main`.

The Day-0 Foundation Gate is the release-blocker defined by
[issue #10](https://github.com/vinhphan812/retailtwin-ai/issues/10). It
proves that the real production cloud path works end to end:

1. The web app and 3D scene build.
2. SKU `P001` is visible through a Firestore-backed API.
3. A `sale.completed` event lands in BigQuery through the Pub/Sub backbone.
4. Gemini (Vertex AI, `gemini-2.5-flash`) executes a real
   `get_inventory(P001)` tool call and the typed Live Twin document is the
   result.
5. The deployed Cloud Run service is reachable and reports the canonical
   production contract.
6. The repository has no committed secrets, no `.env` files, and no
   merge conflict markers.

The gate emits a single `day0-foundation` git tag on `main` only when all
checks pass on the same commit.

## What the gate runs

Two scripts collaborate:

- `scripts/verify-day0-gate.sh` — top-level orchestrator. Boots an
  apps/web build and delegates the cloud-facing checks to
  `scripts/day0_evidence.py`. Writes the final summary.
- `scripts/day0_evidence.py` — Python helper that talks to the deployed
  Cloud Run service, Firestore, BigQuery, and Vertex AI. Writes one JSON
  evidence file per run.

The contract tests in `apps/api/tests/test_day0_smoke.py` pin the
structure of both scripts so refactors cannot silently drop a required
check or change the evidence schema.

## Required credentials and tools

- A POSIX shell with `bash`, `gcloud`, `bq`, `node`, and `python3` on
  `PATH`.
- An authenticated `gcloud` account equal to the billing owner
  `j.dangkhoa.1108@gmail.com`. The script refuses any other account.
- Application Default Credentials configured for the canonical project
  `retailtwin-ai-511002`:

  ```bash
  gcloud auth application-default login
  gcloud auth application-default set-quota-project retailtwin-ai-511002
  ```
- `apps/api` installed in editable mode into a Python 3.11+ venv. The
  gate does not require the API to be running in advance — it boots its
  own local process on a free port.

## Running the gate

From the repository root:

```bash
./scripts/verify-day0-gate.sh
```

The script:

1. Verifies gcloud, bq, python3, and node are on `PATH` and that the
   active gcloud account is the billing owner. Refuses to continue if
   the account or project is wrong.
2. Runs `npm ci` (only if `apps/web/node_modules` is missing) and
   `npm run build` from `apps/web`. The production bundle must produce
   `dist/index.html` with exit code `0`.
3. Delegates to `scripts/day0_evidence.py`, which executes the seven
   checks against the canonical cloud project.
4. Surfaces each check as a `PASS` / `FAIL` / `SKIP` line and writes
   the JSON evidence to `artifacts/day0-foundation/<run-id>.json`.

Useful flags:

```bash
./scripts/verify-day0-gate.sh --skip-vertex          # skip the billable Gemini call
./scripts/verify-day0-gate.sh --skip-pubsub          # skip the sale.completed publish
CLOUD_RUN_URL=https://staging-...run.app \
  ./scripts/verify-day0-gate.sh                      # target a non-production revision
```

Skipped checks are recorded as `SKIP` in the evidence JSON and do not
contribute to PASS / FAIL counts. **Skipping Vertex or Pub/Sub prevents
the gate from tagging `day0-foundation`.**

## Evidence file

`artifacts/day0-foundation/<run-id>.json` (and the convenience copy
`artifacts/day0-foundation/latest.json`) records:

```json
{
  "schema_version": 1,
  "run_id": "20261016T120000Z-deadbeef",
  "started_at": "2026-10-16T12:00:00Z",
  "finished_at": "2026-10-16T12:01:30Z",
  "project": "retailtwin-ai-511002",
  "region": "us-central1",
  "vertex_model": "gemini-2.5-flash",
  "checks": [
    {
      "id": "cloud-run",
      "status": "pass",
      "message": "Deployed service ... reports production + P001",
      "details": {"p001": {...}}
    },
    ...
  ],
  "summary": {"pass": 7, "fail": 0, "skipped": 0}
}
```

`schema_version` lets future versions of the gate evolve the shape
without breaking readers. The contract test
`test_evidence_schema_matches_when_evidence_file_exists` rejects
evidence files that drop the top-level keys.

## Tagging `day0-foundation`

Once the script exits `0` for the same day, on the same commit you want
to freeze, tag it:

```bash
git tag -a day0-foundation -m "Day-0 Foundation Gate PASS on $(git rev-parse HEAD)"
```

The tag annotation must mention the evidence file path. The canonical
commit is the merge commit that lands ADR 0028; never tag a branch tip.

To verify:

```bash
git show day0-foundation
```

## Failure modes and remediation

| Failing check                | Likely cause                                              | Fix                                                                       |
| ---------------------------- | --------------------------------------------------------- | --------------------------------------------------------------------------- |
| `cloud-run`                  | Cloud Run revision is broken or rolled back               | Re-run `scripts/deploy-cloudrun.sh`, then re-run the gate                  |
| `firestore-p001`             | Firestore document missing or schema drift                | Re-run `infrastructure/gcp/bootstrap.sh` or seed/reset script             |
| `local-api-firestore`        | ADC not configured or Firestore unreachable from this IP  | Re-run `gcloud auth application-default login`                             |
| `pubsub-event-path`          | Pub/Sub topic or BigQuery dataset missing                 | Re-run `infrastructure/gcp/apply-store-events.sh`                          |
| `vertex-live-inventory`      | Vertex rate-limited, model unavailable, or quota exhausted| Wait, retry; check billing budget `retailtwin-dev-guard`                  |
| `repo-hygiene`               | A `.env` or conflict marker was committed                 | Remove the file or resolve the conflict; re-run                            |

If a check fails repeatedly, attach the evidence JSON to a comment on
issue #10 with the full `details` payload — never paste access tokens.

## Local development loop

While developing the gate itself:

```bash
# From apps/api
PYTHONPATH=apps/api python -m pytest apps/api/tests/test_day0_smoke.py -q
PYTHONPATH=apps/api python scripts/day0_evidence.py --help
bash scripts/verify-day0-gate.sh --help
```

The contract tests do not touch GCP and run in seconds. They are the
fast feedback loop; the full cloud run is the slow confirmation.

## Related documents

- ADR 0028 — [docs/adr/0028-day-0-foundation-smoke-and-freeze.md](adr/0028-day-0-foundation-smoke-and-freeze.md)
- Issue #10 — [https://github.com/vinhphan812/retailtwin-ai/issues/10](https://github.com/vinhphan812/retailtwin-ai/issues/10)
- Cloud Runtime Matrix — [docs/CLOUD_RUNTIME_MATRIX.md](CLOUD_RUNTIME_MATRIX.md)
- Cloud Preflight Verifier — [scripts/verify-cloud-preflight.sh](verify-cloud-preflight.sh)