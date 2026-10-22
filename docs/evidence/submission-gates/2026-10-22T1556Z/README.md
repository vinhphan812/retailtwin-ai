# Submission-gate evidence: 2026-10-22T1556Z

## Provenance

| Field | Value |
|---|---|
| Tested Git SHA | `c20fb073e4ab919fdced85b7285751e38090cbe3` (`origin/main` at execution) |
| Run window (UTC) | G03–G05: 2026-10-22T15:56:45.707355+00:00 to 2026-10-22T15:56:54.185912+00:00; G06: 2026-10-22T15:56:55Z to 2026-10-22T15:58:16Z |
| Environment | Windows 11 / Git Bash; CPython 3.14.7 from `apps/api/.venv`; deterministic `FakeLlmProvider`; in-process memory Live Twin |
| Retention | This directory is committed. `SHA256SUMS.txt` contains SHA-256 digests of the retained raw outputs. |

These are **offline, in-process gate-harness results**, not Cloud Run deployment
acceptance. No GCP credentials, Vertex, Firestore, or deployed endpoint was used.
The deployment/CI status remains pending until the eventual final submission SHA is
both green and deployed, then independently verified.

## Exact commands

All commands were run from the repository root with `PYTHONPATH` containing the
repository root, `apps/api`, `services/simulation`, and `services/forecasting`.
On this Windows host, a local `python3` compatibility shim invoked
`apps/api/.venv/Scripts/python.exe`; the committed runner itself is unmodified.

```bash
python tests/e2e/gates/g03_autonomous_gate.py \
  --run-id pr388-c20fb073-g03_autonomous \
  --out docs/evidence/submission-gates/2026-10-22T1556Z/g03_autonomous.json
python tests/e2e/gates/g04_guard_gate.py \
  --run-id pr388-c20fb073-g04_guard \
  --out docs/evidence/submission-gates/2026-10-22T1556Z/g04_guard.json
python tests/e2e/gates/g05_live_commit_gate.py \
  --run-id pr388-c20fb073-g05_live_commit \
  --out docs/evidence/submission-gates/2026-10-22T1556Z/g05_live_commit.json
scripts/run-submission-gate.sh --runs 20 --seed pr388-c20fb073-g06 \
  --out docs/evidence/submission-gates/2026-10-22T1556Z/g06-matrix.json \
  --evidence-dir docs/evidence/submission-gates/2026-10-22T1556Z/g06
```

## Results

| Gate | Result | Retained raw artifact |
|---|---|---|
| G03 Autonomous (#50) | **PASS** | `g03_autonomous.json` (`result=PASS`, `git_sha=c20fb073e4ab919fdced85b7285751e38090cbe3`) |
| G04 Guard (#51) | **PASS** | `g04_guard.json` (`result=PASS`, `git_sha=c20fb073e4ab919fdced85b7285751e38090cbe3`) |
| G05 Live Commit (#52) | **PASS** | `g05_live_commit.json` (`result=PASS`, `git_sha=c20fb073e4ab919fdced85b7285751e38090cbe3`) |
| G06 Submission (#53) | **PASS: 20/20** | `g06-matrix.json` (`passed=20`, `failed=0`); all 20 per-run JSON files under `g06/` record `git_sha=c20fb073e4ab919fdced85b7285751e38090cbe3` |

## Limitations and reproduction caveat

The gate runner's documented error branches were manually probed: a missing flagship
runner exits 2 and a non-zero scenario exits 1. A separate QA probe also found that
an artificial scenario which exits 0 while writing `result=FAIL` makes the unmodified
runner exit 0 even though its matrix counts failures. That is a runtime-script defect,
not repaired by this documentation/evidence PR; it is tracked for the separately
scoped runtime repair. Therefore the G06 result here relies on the harness exit status
**and** the committed matrix's `passed=20` / `failed=0` values, not exit status alone.

To reproduce a claim, check out `c20fb073e4ab919fdced85b7285751e38090cbe3`, run the exact command, and compare the
result structure and artifacts; timestamps, correlation IDs, and checksum values will
naturally differ on a fresh run.
