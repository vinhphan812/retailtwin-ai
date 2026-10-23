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
#   --help                show this help text
#
# Exit codes:
#   0  every run PASS
#   1  at least one run FAIL
#   2  invalid usage / missing dependency / environment error

set -euo pipefail

RUNS=20
SEED="submission"
OUT="artifacts/submission-gate/matrix.json"
EVIDENCE_DIR="artifacts/submission-gate"
FLAGSHIP="tests/e2e/gates/run_flagship_scenario.py"
PYTHON_BIN="${PYTHON_BIN:-python3}"

usage() {
    sed -n '2,30p' "$0"
    exit 2
}

utc_now() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}

normalize_python_bin() {
    # Accept a bare command name, a POSIX path, or a native Windows path
    # (e.g. a sys.executable handed over by a Windows pytest runner).
    if command -v "$1" >/dev/null 2>&1; then
        printf '%s' "$1"
        return 0
    fi
    if command -v cygpath >/dev/null 2>&1; then
        local windows_path="${1//\\//}"
        if [[ -f "$windows_path" ]]; then
            printf '%s' "$(cygpath -u "$windows_path")"
            return 0
        fi
    fi
    printf '%s' "$1"
}

sha256_file() {
    # sha256sum handles MSYS paths correctly on Windows and avoids passing a
    # POSIX path to native Windows Python.
    sha256sum "$1" | awk '{print $1}'
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --runs)
            [[ $# -ge 2 ]] || usage
            RUNS="$2"; shift 2 ;;
        --seed)
            [[ $# -ge 2 ]] || usage
            SEED="$2"; shift 2 ;;
        --out)
            [[ $# -ge 2 ]] || usage
            OUT="$2"; shift 2 ;;
        --evidence-dir)
            [[ $# -ge 2 ]] || usage
            EVIDENCE_DIR="$2"; shift 2 ;;
        --flagship)
            [[ $# -ge 2 ]] || usage
            FLAGSHIP="$2"; shift 2 ;;
        --pythonpath)
            [[ $# -ge 2 ]] || usage
            PYTHONPATH_ARG="$2"; shift 2 ;;
        --help|-h)
            usage ;;
        *)
            echo "Unknown argument: $1" >&2; usage ;;
    esac
done

if ! [[ "$RUNS" =~ ^[1-9][0-9]*$ ]]; then
    echo "ERROR: --runs must be a positive integer" >&2
    exit 2
fi

# Absolute path of this runner, resolved before any cd so the runner checksum
# in the evidence matrix is always computed against the executed file.
SCRIPT_PATH="$(cd "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/$(basename -- "${BASH_SOURCE[0]}")"

REPO_ROOT="$(cd "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    if ! NORMALIZED_PYTHON_BIN="$(normalize_python_bin "$PYTHON_BIN")" || [[ ! -f "$NORMALIZED_PYTHON_BIN" ]]; then
        echo "ERROR: Python interpreter not found: $PYTHON_BIN" >&2
        exit 2
    fi
    PYTHON_BIN="$NORMALIZED_PYTHON_BIN"
fi

if [[ -z "${PYTHONPATH_ARG:-}" ]]; then
    # The flagship imports API and service modules. Prefer an explicitly
    # exported PYTHONPATH; otherwise compose the source roots the preflight
    # needs so a plain checkout can run the gate without extra setup.
    if [[ -n "${PYTHONPATH:-}" ]]; then
        PYTHONPATH_ARG="$PYTHONPATH"
    elif [[ "${OSTYPE:-}" == msys* || "${OSTYPE:-}" == cygwin* ]]; then
        PYTHONPATH_ARG="$(cygpath -w "$REPO_ROOT");$(cygpath -w "$REPO_ROOT/apps/api");$(cygpath -w "$REPO_ROOT/services/simulation");$(cygpath -w "$REPO_ROOT/services/forecasting")"
    else
        PYTHONPATH_ARG="${REPO_ROOT}:${REPO_ROOT}/apps/api:${REPO_ROOT}/services/simulation:${REPO_ROOT}/services/forecasting"
    fi
fi
export PYTHONPATH="$PYTHONPATH_ARG"

if [[ ! -f "$FLAGSHIP" ]]; then
    echo "ERROR: flagship runner not found at $FLAGSHIP" >&2
    exit 2
fi

mkdir -p "$EVIDENCE_DIR"
mkdir -p "$(dirname "$OUT")"

TESTED_GIT_SHA="$(git rev-parse HEAD 2>/dev/null || true)"
if [[ -z "$TESTED_GIT_SHA" ]]; then
    echo "ERROR: cannot resolve tested git SHA" >&2
    exit 2
fi
RUNNER_SHA256="$(sha256_file "$SCRIPT_PATH")"
FLAGSHIP_SHA256="$(sha256_file "$FLAGSHIP")"
COMMAND="$(printf '%q ' "$0" --runs "$RUNS" --seed "$SEED" --out "$OUT" --evidence-dir "$EVIDENCE_DIR" --flagship "$FLAGSHIP" --pythonpath "$PYTHONPATH_ARG")"
GATE_STARTED_AT="$(utc_now)"

printf '%s\n' "G06 Submission Gate runner (in-memory preflight; no deployment performed)"
printf '  runs       : %s\n' "$RUNS"
printf '  seed       : %s\n' "$SEED"
printf '  git SHA    : %s\n' "$TESTED_GIT_SHA"
printf '  command    : %s\n' "$COMMAND"
printf '  out        : %s\n' "$OUT"
printf '  evidence   : %s\n' "$EVIDENCE_DIR"
printf '  flagship   : %s\n' "$FLAGSHIP"
printf '  python     : %s\n\n' "$PYTHON_BIN"

PASSED_RUNS=0
FAILED_RUNS=0
HALTED_ON_FAILURE=false
RUN_DETAILS_JSONL="${EVIDENCE_DIR}/.g06-runs.$$.jsonl"
: > "$RUN_DETAILS_JSONL"
trap 'rm -f "$RUN_DETAILS_JSONL"' EXIT

for i in $(seq 1 "$RUNS"); do
    run_id="${SEED}-$(printf '%02d' "$i")"
    run_started_at="$(utc_now)"
    evidence_path="${EVIDENCE_DIR}/${run_id}.json"
    stderr_path="${EVIDENCE_DIR}/${run_id}.stderr.log"

    printf '==> Run %s/%s  run_id=%s\n' "$i" "$RUNS" "$run_id"
    set +e
    runner_native_path="$(cygpath -w "$FLAGSHIP" 2>/dev/null || printf '%s' "$FLAGSHIP")"
    evidence_native_path="$(cygpath -w "$evidence_path" 2>/dev/null || printf '%s' "$evidence_path")"
    "$PYTHON_BIN" "$runner_native_path" --run-id "$run_id" --out "$evidence_native_path" 2>"$stderr_path"
    exit_code=$?
    set -e
    run_finished_at="$(utc_now)"
    result="FAIL"
    failure_reason=""

    if [[ $exit_code -ne 0 ]]; then
        failure_reason="runner exited with status $exit_code"
    elif [[ ! -f "$evidence_path" ]]; then
        failure_reason="runner exited successfully without evidence"
    else
        set +e
        result="$("$PYTHON_BIN" - "$(cygpath -w "$evidence_path" 2>/dev/null || printf '%s' "$evidence_path")" <<'PY'
import json
from pathlib import Path
import sys

try:
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as exc:
    print(f"INVALID:{exc}")
    raise SystemExit(1)
value = data.get("result")
if not isinstance(value, str):
    print("INVALID:missing result")
    raise SystemExit(1)
print(value)
PY
)"
        evidence_read_exit=$?
        set -e
        if [[ $evidence_read_exit -ne 0 ]]; then
            result="FAIL"
            failure_reason="evidence is unreadable or missing result"
        elif [[ "$result" != "PASS" ]]; then
            failure_reason="evidence result is $result"
        fi
    fi

    evidence_sha256=""
    if [[ -f "$evidence_path" ]]; then
        evidence_sha256="$(sha256_file "$evidence_path")"
    fi

    if [[ -z "$failure_reason" ]]; then
        PASSED_RUNS=$((PASSED_RUNS + 1))
        printf '    PASS  evidence=%s sha256=%s\n' "$evidence_path" "$evidence_sha256"
    else
        FAILED_RUNS=$((FAILED_RUNS + 1))
        HALTED_ON_FAILURE=true
        result="FAIL"
        printf '    FAIL  evidence=%s reason=%s\n' "$evidence_path" "$failure_reason"
        if [[ -s "$stderr_path" ]]; then
            echo "    --- stderr tail ---"
            tail -n 20 "$stderr_path" || true
            echo "    --- end stderr ---"
        fi
    fi

    "$PYTHON_BIN" - "$run_id" "$run_started_at" "$run_finished_at" "$exit_code" "$result" "$evidence_path" "$evidence_sha256" "$failure_reason" "$(cygpath -w "$RUN_DETAILS_JSONL" 2>/dev/null || printf '%s' "$RUN_DETAILS_JSONL")" <<'PY'
import json
import sys

run_id, started, finished, exit_code, result, evidence_path, evidence_sha256, failure_reason, output = sys.argv[1:]
with open(output, "a", encoding="utf-8") as stream:
    stream.write(json.dumps({
        "run_id": run_id,
        "started_at": started,
        "finished_at": finished,
        "exit_code": int(exit_code),
        "result": result,
        "evidence_path": evidence_path,
        "evidence_file_sha256": evidence_sha256 or None,
        "failure_reason": failure_reason or None,
    }, sort_keys=True) + "\n")
PY

    if [[ "$HALTED_ON_FAILURE" == true ]]; then
        echo "    Halting after first failed scenario."
        break
    fi
done

GATE_FINISHED_AT="$(utc_now)"
"$PYTHON_BIN" - "$RUNS" "$SEED" "$(cygpath -w "$RUN_DETAILS_JSONL" 2>/dev/null || printf '%s' "$RUN_DETAILS_JSONL")" "$(cygpath -w "$OUT" 2>/dev/null || printf '%s' "$OUT")" "$TESTED_GIT_SHA" "$COMMAND" "$GATE_STARTED_AT" "$GATE_FINISHED_AT" "$RUNNER_SHA256" "$FLAGSHIP_SHA256" "$PYTHONPATH_ARG" "$HALTED_ON_FAILURE" <<'PY'
import hashlib
import json
import sys

(
    requested_runs, seed, jsonl_path, out_path, tested_git_sha, command,
    started_at, finished_at, runner_sha256, flagship_sha256, pythonpath, halted_on_failure,
) = sys.argv[1:]

with open(jsonl_path, encoding="utf-8") as stream:
    records = [json.loads(line) for line in stream if line.strip()]

passed = sum(record["result"] == "PASS" for record in records)
failed = len(records) - passed

# Tamper-evident hash chain over (prev_hash, run_id, exit_code, result).
# ``evidence_file_sha256`` is the SHA-256 of the evidence file itself.
prev = ""
for record in records:
    chain = hashlib.sha256(
        f"{prev}|{record['run_id']}|{record['exit_code']}|{record['result']}".encode()
    ).hexdigest()
    record["chain_sha256"] = chain
    prev = chain

matrix = {
    "gate": "G06",
    "issue": 53,
    "scenario": "weekend-demand-surge",
    "execution_mode": "in-memory preflight",
    "deployment_performed": False,
    "seed": seed,
    "total_runs": int(requested_runs),
    "requested_runs": int(requested_runs),
    "executed_runs": len(records),
    "passed": passed,
    "failed": failed,
    "halted_on_failure": halted_on_failure == "true",
    "started_at": started_at,
    "finished_at": finished_at,
    "provenance": {
        "tested_git_sha": tested_git_sha,
        "command": command,
        "started_at": started_at,
        "finished_at": finished_at,
        "runner_sha256": runner_sha256,
        "flagship_sha256": flagship_sha256,
        "pythonpath": pythonpath,
    },
    "runs": [
        {
            "run_index": index + 1,
            "run_id": record["run_id"],
            "exit_code": record["exit_code"],
            "result": record["result"],
            "started_at": record["started_at"],
            "finished_at": record["finished_at"],
            "evidence_path": record["evidence_path"],
            "evidence_sha256": record["chain_sha256"],
            "evidence_file_sha256": record["evidence_file_sha256"],
            "failure_reason": record["failure_reason"],
        }
        for index, record in enumerate(records)
    ],
}
with open(out_path, "w", encoding="utf-8") as stream:
    json.dump(matrix, stream, indent=2, sort_keys=True)
    stream.write("\n")
print(f"\nWrote matrix: {out_path}")
PY

printf '\nG06 summary:\n'
printf '  requested : %s\n' "$RUNS"
printf '  executed  : %s\n' "$((PASSED_RUNS + FAILED_RUNS))"
printf '  passed    : %s\n' "$PASSED_RUNS"
printf '  failed    : %s\n' "$FAILED_RUNS"
printf '  matrix    : %s\n' "$OUT"

if [[ $FAILED_RUNS -ne 0 ]]; then
    exit 1
fi
exit 0
