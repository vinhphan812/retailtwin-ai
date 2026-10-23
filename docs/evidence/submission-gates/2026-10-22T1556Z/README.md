# Submission-gate evidence: 2026-10-22T1556Z

## Provenance

| Field | Value |
|---|---|
| Tested Git SHA | `c20fb073e4ab919fdced85b7285751e38090cbe3` (`origin/main` at execution) |
| Run window (UTC) | G03–G05: 2026-10-22T15:56:45.707355+00:00 to 2026-10-22T15:56:54.185912+00:00; G06: 2026-10-22T15:56:55Z to 2026-10-22T15:58:16Z |
| Environment | Windows 11 / Git Bash; CPython 3.14.7 from `apps/api/.venv`; deterministic `FakeLlmProvider`; in-process memory Live Twin |
| Retention | This directory retains 33 checksummed files: this README, the G03–G06 JSON/stdout/stderr artifacts retained at commit time, and all 20 G06 per-run JSON files. `SHA256SUMS.txt` intentionally excludes itself and lists only files present in this committed directory. |

These are **offline, in-process gate-harness results**, not Cloud Run deployment
acceptance. No GCP credentials, Vertex, Firestore, or deployed endpoint was used.
The deployment/CI status remains pending until the eventual final submission SHA is
both green and deployed, then independently verified.

## Canonical source of the submission-gate evidence

This directory is the **single canonical location** for the G03–G06 submission-gate
evidence. It was reconciled in coordination with the earlier duplicate submissions so
that exactly one retained artifact path backs the claim:

| Prior submission | Prior path | Disposition |
|---|---|---|
| PR #398 | `docs/submission-evidence/2026-10-22-c20fb073/` | **Superseded** — closed; its `g06-run-evidence.tar.gz` duplicates the per-run artifacts retained here, and its path is not the canonical one. |
| PR #397 (stale head `5564810`) | `docs/evidence/submission-gates/2026-10-22T1556Z/` (earlier content) | **Superseded** — closed; its `SHA256SUMS.txt` listed 52 entries of which 20 (the `g06/pr388-c20fb073-g06-NN.stderr.log` files) were never committed, so `sha256sum -c` failed with exit 1 (32 OK / 20 FAILED). |

Readers should cite **this** directory and verify it with the commands below. The
prior paths are not to be cited as evidence and their manifests are not to be
reused. No claim is made here that either prior submission was deployed or accepted.

## Integrity verification

`SHA256SUMS.txt` covers exactly the 33 files present in this directory other than
itself; there are no unlisted files and no listed-but-absent files. Verify from a
clean extraction of the committed tree:

```bash
git archive --format=tar HEAD docs/evidence/submission-gates/2026-10-22T1556Z \
  | tar -xf - -C <fresh-dir>
cd <fresh-dir>/docs/evidence/submission-gates/2026-10-22T1556Z
sha256sum -c SHA256SUMS.txt    # expected: exit 0, 33/33 OK
```

A checksum match proves the retained artifacts are **byte-identical to the ones
committed here**. It does not prove anything about the behaviour of the system on
any other machine or at any other commit.

## Repository and third-party licensing provenance

The repository's first-party code is licensed under the MIT License
(`LICENSE` at the repository root). The eleven third-party 3D asset packs under
`apps/web/public/models/` are each released under CC0 1.0 and each retain their
upstream `License.txt`; their per-asset attribution and the exact limits of that
verification are recorded in `THIRD_PARTY_NOTICES.md` at the repository root.
Third-party software dependencies are not vendored into the tree and remain under
their own upstream licenses.

## Explicit limitation: this is not deployed or final-SHA acceptance

The retained G03–G06 artifacts were produced with a **deterministic
`FakeLlmProvider` against an in-process, in-memory Live Twin at
`c20fb073e4ab919fdced85b7285751e38090cbe3`**. They are therefore **not**
deployment acceptance and **not** acceptance at the final submission SHA:

- They do **not** demonstrate that a deployed Cloud Run service, Vertex AI
  endpoint, or Firestore-backed deployment behaves correctly. No GCP credentials
  were used and no deployed endpoint was exercised.
- They are **not** CI evidence for the final submission SHA. `c20fb073` is a
  historical baseline commit, not the final submission commit; the gate run must
  be re-executed against the eventual final SHA and that SHA must be both green
  in CI and deployed.
- Gate acceptance for the submission requires all of: green CI on the exact
  final SHA, a successful deployment, and independent verification of the
  deployed revision. **None of those is established by this evidence set.**

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
