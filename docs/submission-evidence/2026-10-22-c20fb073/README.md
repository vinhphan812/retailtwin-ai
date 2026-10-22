# Issue #367 — G03–G06 local execution evidence

## Scope and provenance

This directory retains the reproducible **local / in-memory** execution evidence gathered for Issue #367.

- **Tested commit:** `c20fb073e4ab919fdced85b7285751e38090cbe3` (`origin/main` at execution time)
- **Execution date (UTC):** 2026-10-22
- **Runtime:** CPython 3.14.3, editable `apps/api[dev]` environment
- **Harness configuration:** `FakeLlmProvider`, `LIVE_TWIN_BACKEND=memory`, `APP_ENV=e2e-smoke`
- **Not production proof:** this run neither invokes deployed Vertex Gemini nor verifies Cloud Run. It must not be used to mark Cloud Run/deployment rows green.

The tested commit predates this documentation/evidence commit; it remains an auditable baseline, **not the final submission SHA**. Re-run the commands below after the final SHA is merged and deployed.

## Results

| Gate | Result | Run identifier | Retained artifact |
|---|---|---|---|
| G03 Autonomous | PASS | `issue367-c20fb073-g03` | `g03-autonomous.json` |
| G04 Guard | PASS | `issue367-c20fb073-g04` | `g04-guard.json` |
| G05 Live Commit | PASS | `issue367-c20fb073-g05` | `g05-live-commit.json` |
| G06 Submission | PASS, 20 / 20 | `issue367-c20fb073-01` … `-20` | `g06-matrix.json`; `g06-run-evidence.tar.gz` (20 per-run JSON files) |

G06 started at `2026-10-22T15:54:47Z` and finished at `2026-10-22T15:56:28Z`; the matrix records 20 passed, 0 failed, and a per-run hash chain.

## Exact commands

Run from the repository root with the API development dependencies installed. On standard CI/Linux environments `python3` is the project’s documented interpreter.

```bash
PYTHONPATH="apps/api:services/simulation:services/forecasting" \
  python3 tests/e2e/gates/g03_autonomous_gate.py \
  --run-id issue367-c20fb073-g03 \
  --out docs/submission-evidence/2026-10-22-c20fb073/g03-autonomous.json

PYTHONPATH="apps/api:services/simulation:services/forecasting" \
  python3 tests/e2e/gates/g04_guard_gate.py \
  --run-id issue367-c20fb073-g04 \
  --out docs/submission-evidence/2026-10-22-c20fb073/g04-guard.json

PYTHONPATH="apps/api:services/simulation:services/forecasting" \
  python3 tests/e2e/gates/g05_live_commit_gate.py \
  --run-id issue367-c20fb073-g05 \
  --out docs/submission-evidence/2026-10-22-c20fb073/g05-live-commit.json

bash scripts/run-submission-gate.sh \
  --runs 20 --seed issue367-c20fb073 \
  --out docs/submission-evidence/2026-10-22-c20fb073/g06-matrix.json \
  --evidence-dir docs/submission-evidence/2026-10-22-c20fb073/g06-runs
```

## Integrity hashes (SHA-256)

```text
829263936ba9092900b2a7205651f63e70692c430f498dd22b24da9f2331fd61  g03-autonomous.json
461cd3b32b1708df691606a7f04c398140c8009f43a35907f416e9a48dfb80a5  g04-guard.json
ce5919024b7697a85a68d8c5acbcf1e515c1cfeefbe9723b2e615e18f8287fb3  g05-live-commit.json
555e6bff84858ebb8ad48eb4dbf1bda2ca4313a5c83424ae01408dfa42d81a27  g06-matrix.json
ce38081e26815f5ba00f27521e28cacb550e9ff7a6d3db9711160331391fc823  g06-run-evidence.tar.gz
```

`g06-run-evidence.tar.gz` contains the 20 raw `g06-runs/*.json` outputs and deliberately excludes verbose stderr logs. Extract with `tar -xzf g06-run-evidence.tar.gz`.

## Remaining release blockers

1. `origin/main` API CI run [#39746990404](https://github.com/vinhphan812/retailtwin-ai/actions/runs/39746990404) for `c20fb073` failed: `test_pubsub_route_in_production_with_unset_service_account_returns_503` expected 503 but received 401. Its downstream Release Gate [#39748018847](https://github.com/vinhphan812/retailtwin-ai/actions/runs/39748018847) consequently failed.
2. Cloud Run currently serves revision `retailtwin-api-00049-2h8`, created 2026-10-19, with image tag `79a06ad`. That short tag is not resolvable in the GitHub repository, and `/health` reports `git_sha: "unknown"`; it is not accepted as a submission-SHA deployment.
3. No published demo-video URL was found in the repository. `docs/DEMO_VIDEO.md` is a production runbook, not a delivered video.
