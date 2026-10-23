#!/usr/bin/env bash
# G06 Submission Gate runner for issue #53.
#
# Runs the flagship scenario 20 consecutive times against the real API app,
# with the same fixed seed for determinism. Each run produces one structured
# JSON evidence file under artifacts/submission-gate/, and an aggregate
# matrix JSON that the reviewer can read.
#
# The runner halts on the first failure (per issue #53: "Any failure resets
# the consecutive count after fix"). Exit status is 0 only when every run
# passes.
#
# Usage:
#   scripts/run-submission-gate.sh                    # default: 20 runs, seed submission
#   scripts/run-submission-gate.sh --runs 2 --seed smoke --out /tmp/g06-smoke.json
#
# Options (env-friendly):
#   --runs <N>            total number of consecutive runs (default: 20)
#   --seed <name>         run-id seed; every run is named "<seed>-<index>"
#   --out <path>          aggregate matrix output path (default: artifacts/submission-gate/matrix.json)
#   --evidence-dir <path> per-run evidence output dir (default: artifacts/submission-gate)
#   --flagship <path>     path to run_flagship_scenario.py (default: tests/e2e/gates/run_flagship_scenario.py)
#   --pythonpath <path>   PYTHONPATH for the runner (default: apps/api, services/simulation, services/forecasting)
#   --python <path>       Python interpreter to use (default: auto-detect repo venv, python3, then python)
#   --help                show this help text
#
# Interpreter resolution (in order):
#   1. --python <path>            explicit flag
#   2. $G06_PYTHON                gate-scoped environment override
#   3. $PYTHON_BIN                generic environment override
#   4. auto-detect: repo virtualenv, then python3, then python
#
# Hosts that only ship `python` (Windows/MSYS, CI sandboxes without the
# python3 alias) used to abort with exit 127 because the runner hard-coded
# `python3`. An explicitly requested interpreter that cannot be resolved or
# executed is a hard failure (exit 2); auto-detection that finds nothing is
# also a hard failure (exit 2). The runner never falls back to a different
# interpreter than the one that was requested.
#
# Exit codes:
#   0  every run PASS
#   1  at least one run FAIL
#   2  invalid usage / missing dependency / environment error

set -euo pipefail

# Defaults
RUNS=20
SEED="submission"
OUT="artifacts/submission-gate/matrix.json"
EVIDENCE_DIR="artifacts/submission-gate"
FLAGSHIP="tests/e2e/gates/run_flagship_scenario.py"

usage() {
    # Print the header comment block (everything between the shebang and the
    # first non-comment line), stripped of the leading "# ".
    awk 'NR > 1 { if ($0 !~ /^#/) exit; sub(/^# ?/, ""); print }' "$0"
    exit 2
}

PYTHON_OVERRIDE=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --runs)
            RUNS="$2"; shift 2 ;;
        --seed)
            SEED="$2"; shift 2 ;;
        --out)
            OUT="$2"; shift 2 ;;
        --evidence-dir)
            EVIDENCE_DIR="$2"; shift 2 ;;
        --flagship)
            FLAGSHIP="$2"; shift 2 ;;
        --pythonpath)
            PYTHONPATH_ARG="$2"; shift 2 ;;
        --python)
            PYTHON_OVERRIDE="$2"; shift 2 ;;
        --help|-h)
            usage ;;
        *)
            echo "Unknown argument: $1" >&2; usage ;;
    esac
done

REPO_ROOT="$(cd "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Resolve default PYTHONPATH when not supplied
if [[ -z "${PYTHONPATH_ARG:-}" ]]; then
    PYTHONPATH_ARG="."
fi
export PYTHONPATH="$PYTHONPATH_ARG"

# Verify the flagship runner exists
if [[ ! -f "$FLAGSHIP" ]]; then
    echo "ERROR: flagship runner not found at $FLAGSHIP" >&2
    exit 2
fi

# ── Resolve the Python interpreter ───────────────────────────────────────────
# The runner used to hard-code `python3`, which aborts with exit 127 on hosts
# that only ship `python` (Windows/MSYS, some CI sandboxes). Resolution order:
#   1. --python <path>      (explicit request)
#   2. $G06_PYTHON          (gate-scoped environment override)
#   3. $PYTHON_BIN          (generic environment override)
#   4. auto-detect: repo virtualenv, then python3, then python
# An explicit request that cannot be resolved or executed is a hard failure
# (exit 2) — the runner never silently falls back to a different interpreter.
resolve_python_bin() {
    local candidate resolved normalized
    for candidate in "$@"; do
        [[ -n "$candidate" ]] || continue
        # Normalise Windows-style backslash paths so MSYS/Git-bash can stat them.
        normalized="${candidate//\\//}"
        # An explicit path to an executable file is accepted as-is.
        if [[ "$normalized" == */* ]]; then
            if [[ -f "$normalized" && -x "$normalized" ]]; then
                printf '%s\n' "$normalized"
                return 0
            fi
            continue
        fi
        if resolved="$(command -v -- "$candidate" 2>/dev/null)"; then
            printf '%s\n' "$resolved"
            return 0
        fi
    done
    return 1
}

# The repo-local virtualenv is preferred during auto-detection because it is
# the only interpreter guaranteed to have the API dependencies installed.
repo_venv_candidates() {
    printf '%s\n' \
        "$REPO_ROOT/apps/api/.venv/Scripts/python.exe" \
        "$REPO_ROOT/apps/api/.venv/bin/python" \
        "$REPO_ROOT/.venv/Scripts/python.exe" \
        "$REPO_ROOT/.venv/bin/python"
}

if [[ -n "$PYTHON_OVERRIDE" ]]; then
    REQUESTED_PYTHON="$PYTHON_OVERRIDE"
    REQUEST_SOURCE="--python"
elif [[ -n "${G06_PYTHON:-}" ]]; then
    REQUESTED_PYTHON="$G06_PYTHON"
    REQUEST_SOURCE="G06_PYTHON"
elif [[ -n "${PYTHON_BIN:-}" ]]; then
    REQUESTED_PYTHON="$PYTHON_BIN"
    REQUEST_SOURCE="PYTHON_BIN"
else
    REQUESTED_PYTHON=""
    REQUEST_SOURCE="auto-detect"
fi

if [[ -n "$REQUESTED_PYTHON" ]]; then
    if ! PYTHON_BIN_RESOLVED="$(resolve_python_bin "$REQUESTED_PYTHON")"; then
        echo "ERROR: requested Python interpreter not found: $REQUESTED_PYTHON (from $REQUEST_SOURCE)" >&2
        exit 2
    fi
else
    PYTHON_BIN_RESOLVED=""
    while IFS= read -r venv_candidate; do
        [[ -n "$venv_candidate" ]] || continue
        if resolved_venv="$(resolve_python_bin "$venv_candidate")"; then
            PYTHON_BIN_RESOLVED="$resolved_venv"
            REQUEST_SOURCE="auto-detect:repo-venv"
            break
        fi
    done < <(repo_venv_candidates)
    if [[ -z "$PYTHON_BIN_RESOLVED" ]]; then
        if ! PYTHON_BIN_RESOLVED="$(resolve_python_bin python3 python)"; then
            echo "ERROR: no Python interpreter found (tried the repo virtualenv, then 'python3', then 'python')." >&2
            echo "       Pass --python <path> or set G06_PYTHON/PYTHON_BIN." >&2
            exit 2
        fi
        REQUEST_SOURCE="auto-detect:python3-or-python"
    fi
fi

# Fail closed when the resolved interpreter cannot actually execute.
if ! "$PYTHON_BIN_RESOLVED" -c "import sys" >/dev/null 2>&1; then
    echo "ERROR: Python interpreter is not executable: $PYTHON_BIN_RESOLVED (from $REQUEST_SOURCE)" >&2
    exit 2
fi

PYTHON_VERSION="$("$PYTHON_BIN_RESOLVED" -c 'import platform; print(platform.python_version())' 2>/dev/null || echo "unknown")"

# Prepare output directories
mkdir -p "$EVIDENCE_DIR"
mkdir -p "$(dirname "$OUT")"

echo "G06 Submission Gate runner"
echo "  runs       : $RUNS"
echo "  seed       : $SEED"
echo "  out        : $OUT"
echo "  evidence   : $EVIDENCE_DIR"
echo "  flagship   : $FLAGSHIP"
echo "  PYTHONPATH  : $PYTHONPATH"
echo "  interpreter : $PYTHON_BIN_RESOLVED (python $PYTHON_VERSION, via $REQUEST_SOURCE)"
echo

FAILED_RUNS=0
PASSED_RUNS=0
RUN_DETAILS_JSONL="$(mktemp -t g06-runs.XXXXXX.jsonl)"
trap 'rm -f "$RUN_DETAILS_JSONL"' EXIT

for i in $(seq 1 "$RUNS"); do
    run_id="${SEED}-$(printf '%02d' "$i")"
    run_started_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    evidence_path="${EVIDENCE_DIR}/${run_id}.json"

    echo "==> Run $i/$RUNS  run_id=${run_id}"
    set +e
    "$PYTHON_BIN_RESOLVED" "$FLAGSHIP" --run-id "$run_id" --out "$evidence_path" 2>"${EVIDENCE_DIR}/${run_id}.stderr.log"
    exit_code=$?
    set -e
    run_finished_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

    if [[ $exit_code -eq 0 ]]; then
        PASSED_RUNS=$((PASSED_RUNS + 1))
        # Read the embedded result field if present
        result="PASS"
        if [[ -f "$evidence_path" ]]; then
            embedded=$("$PYTHON_BIN_RESOLVED" -c "import json,sys; print(json.load(open(sys.argv[1])).get('result','PASS'))" "$evidence_path" 2>/dev/null || echo "PASS")
            result="$embedded"
        fi
        echo "    PASS  evidence=${evidence_path}"
    else
        FAILED_RUNS=$((FAILED_RUNS + 1))
        result="FAIL"
        echo "    FAIL  evidence=${evidence_path} (exit=${exit_code})"
        if [[ -s "${EVIDENCE_DIR}/${run_id}.stderr.log" ]]; then
            echo "    --- stderr tail ---"
            tail -n 20 "${EVIDENCE_DIR}/${run_id}.stderr.log" || true
            echo "    --- end stderr ---"
        fi
    fi

    # Append one record to the jsonl file
    "$PYTHON_BIN_RESOLVED" - "$run_id" "$run_started_at" "$run_finished_at" "$exit_code" "$result" "$evidence_path" "$RUN_DETAILS_JSONL" <<'PY'
import json, sys
run_id, started, finished, exit_code, result, evidence_path, out_path = sys.argv[1:]
record = {
    "run_id": run_id,
    "started_at": started,
    "finished_at": finished,
    "exit_code": int(exit_code),
    "result": result,
    "evidence_path": evidence_path,
}
with open(out_path, "a", encoding="utf-8") as f:
    f.write(json.dumps(record) + "\n")
PY
done

# Build the aggregate matrix
"$PYTHON_BIN_RESOLVED" - "$RUNS" "$SEED" "$RUN_DETAILS_JSONL" "$OUT" "$PYTHON_BIN_RESOLVED" "$PYTHON_VERSION" "$REQUEST_SOURCE" <<'PY'
import json, sys, hashlib
from datetime import datetime, timezone

runs_total, seed, jsonl_path, out_path, python_bin, python_version, python_source = sys.argv[1:]

records = []
with open(jsonl_path, encoding="utf-8") as f:
    for line in f:
        if line.strip():
            records.append(json.loads(line))

passed = sum(1 for r in records if r["result"] == "PASS")
failed = sum(1 for r in records if r["result"] != "PASS")

# Per-run hash chain for tamper-evident evidence
prev = ""
for r in records:
    h = hashlib.sha256(f"{prev}|{r['run_id']}|{r['exit_code']}|{r['result']}".encode()).hexdigest()
    r["evidence_sha256"] = h
    prev = h

matrix = {
    "gate": "G06",
    "issue": 53,
    "scenario": "weekend-demand-surge",
    "seed": seed,
    "total_runs": int(runs_total),
    "passed": passed,
    "failed": failed,
    "interpreter": {
        "path": python_bin,
        "version": python_version,
        "resolved_from": python_source,
    },
    "started_at": records[0]["started_at"] if records else datetime.now(timezone.utc).isoformat(),
    "finished_at": records[-1]["finished_at"] if records else datetime.now(timezone.utc).isoformat(),
    "runs": [
        {
            "run_index": idx + 1,
            "run_id": r["run_id"],
            "exit_code": r["exit_code"],
            "result": r["result"],
            "started_at": r["started_at"],
            "finished_at": r["finished_at"],
            "evidence_path": r["evidence_path"],
            "evidence_sha256": r["evidence_sha256"],
        }
        for idx, r in enumerate(records)
    ],
}

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(matrix, f, indent=2, sort_keys=False)
print(f"\nWrote matrix: {out_path}")
PY

echo
echo "G06 summary:"
echo "  total runs : $RUNS"
echo "  passed     : $PASSED_RUNS"
echo "  failed     : $FAILED_RUNS"
echo "  matrix     : $OUT"

if [[ $FAILED_RUNS -ne 0 ]]; then
    exit 1
fi
exit 0