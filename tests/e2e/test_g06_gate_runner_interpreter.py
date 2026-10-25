"""Contract tests for the G06 submission-gate shell runner (``#53``).

These tests exercise ``scripts/run-submission-gate.sh`` as a black box. The
runner is a shell script, so the tests drive it through ``bash`` with a fake
flagship harness; no network, no cloud calls and no credentials are used.

What is pinned here
-------------------
* **Interpreter resolution** — the runner used to hard-code ``python3``, which
  aborts with exit 127 on hosts that only ship ``python`` (Windows/MSYS and
  some CI sandboxes). The runner must now honour an explicitly configured
  interpreter (``--python`` / ``G06_PYTHON`` / ``PYTHON_BIN``) and fall back
  to auto-detection (``python3`` then ``python``) only when nothing is
  configured.
* **Fail-closed exit status** — a missing or unusable interpreter is a hard
  error (exit 2), and a failing scenario must never be reported as a passing
  run (non-zero exit).
* **Matrix evidence** — the aggregate ``matrix.json`` must be produced and
  must record the interpreter that actually executed the scenario, so the
  evidence is reproducible on the reader's host.

The tests are skipped when no POSIX ``bash`` is available (e.g. a native
Windows shell without Git-bash/MSYS).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER = REPO_ROOT / "scripts" / "run-submission-gate.sh"

BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(
    BASH is None or not RUNNER.exists(),
    reason="requires POSIX bash and scripts/run-submission-gate.sh",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# A fake flagship harness. It records the interpreter that actually executed
# it (``sys.executable``) into the evidence JSON, so the test can assert that
# the runner used the *configured* interpreter and not a different one.
FAKE_FLAGSHIP = '''\
import argparse
import json
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--run-id")
parser.add_argument("--out")
args = parser.parse_args()

payload = {
    "result": "PASS",
    "run_id": args.run_id,
    "python_executable": sys.executable,
}
if args.out:
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
sys.exit(0)
'''

# A fake flagship that always fails (non-zero exit).
FAILING_FLAGSHIP = '''\
import sys
sys.stderr.write("synthetic scenario failure\\n")
sys.exit(3)
'''


def _write_script(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def _run_runner(
    tmp_path: Path,
    *,
    flagship: Path,
    runs: int = 2,
    extra_args: list[str] | None = None,
    env: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess, Path, Path]:
    """Invoke the gate runner with an isolated evidence directory."""
    evidence_dir = tmp_path / "evidence"
    matrix_path = tmp_path / "matrix.json"

    args = [
        BASH or "bash",
        str(RUNNER),
        "--runs",
        str(runs),
        "--seed",
        "unit",
        "--flagship",
        str(flagship),
        "--evidence-dir",
        str(evidence_dir),
        "--out",
        str(matrix_path),
    ]
    if extra_args:
        args.extend(extra_args)

    run_env = dict(os.environ)
    # Keep the child environment hermetic: no inherited interpreter override
    # unless the caller explicitly asks for one.
    run_env.pop("G06_PYTHON", None)
    run_env.pop("PYTHON_BIN", None)
    if env:
        run_env.update(env)

    completed = subprocess.run(
        args,
        cwd=str(REPO_ROOT),
        env=run_env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    return completed, matrix_path, evidence_dir


def _matrix(matrix_path: Path) -> dict:
    return json.loads(matrix_path.read_text(encoding="utf-8"))


def _python_path() -> str:
    """An interpreter path that is guaranteed to work on this host."""
    return sys.executable


def _norm(path: str) -> str:
    """Normalise a filesystem path for comparison across shell/Python views.

    Git-bash on Windows reports ``C:/Users/...`` while Python reports
    ``C:\\Users\\...``; the runner normalises to forward slashes.
    """
    return path.replace("\\", "/").rstrip("/").lower()


# ---------------------------------------------------------------------------
# Interpreter resolution
# ---------------------------------------------------------------------------


def test_runner_uses_explicit_python_flag(tmp_path: Path) -> None:
    """``--python`` selects the interpreter and is recorded in the matrix."""
    flagship = _write_script(tmp_path / "fake_flagship.py", FAKE_FLAGSHIP)
    python = _python_path()

    completed, matrix_path, evidence_dir = _run_runner(
        tmp_path,
        flagship=flagship,
        extra_args=["--python", python],
    )

    assert completed.returncode == 0, completed.stderr
    matrix = _matrix(matrix_path)
    assert _norm(matrix["interpreter"]["path"]) == _norm(python)
    assert matrix["interpreter"]["resolved_from"] == "--python"
    assert matrix["interpreter"]["version"] != "unknown"

    # The evidence file itself proves which interpreter executed the scenario.
    evidence_files = sorted(evidence_dir.glob("*.json"))
    assert evidence_files, "no per-run evidence was produced"
    evidence = json.loads(evidence_files[0].read_text(encoding="utf-8"))
    assert _norm(evidence["python_executable"]) == _norm(python)


def test_runner_honours_g06_python_env_override(tmp_path: Path) -> None:
    """``G06_PYTHON`` is a gate-scoped override and is recorded as such."""
    flagship = _write_script(tmp_path / "fake_flagship.py", FAKE_FLAGSHIP)
    python = _python_path()

    completed, matrix_path, _ = _run_runner(
        tmp_path,
        flagship=flagship,
        env={"G06_PYTHON": python},
    )

    assert completed.returncode == 0, completed.stderr
    matrix = _matrix(matrix_path)
    assert _norm(matrix["interpreter"]["path"]) == _norm(python)
    assert matrix["interpreter"]["resolved_from"] == "G06_PYTHON"


def test_runner_honours_python_bin_env_override(tmp_path: Path) -> None:
    """``PYTHON_BIN`` is the generic override and is recorded as such."""
    flagship = _write_script(tmp_path / "fake_flagship.py", FAKE_FLAGSHIP)
    python = _python_path()

    completed, matrix_path, _ = _run_runner(
        tmp_path,
        flagship=flagship,
        env={"PYTHON_BIN": python},
    )

    assert completed.returncode == 0, completed.stderr
    matrix = _matrix(matrix_path)
    assert _norm(matrix["interpreter"]["path"]) == _norm(python)
    assert matrix["interpreter"]["resolved_from"] == "PYTHON_BIN"


def test_runner_auto_detects_interpreter_when_unconfigured(tmp_path: Path) -> None:
    """With no override the runner auto-detects an interpreter itself."""
    flagship = _write_script(tmp_path / "fake_flagship.py", FAKE_FLAGSHIP)

    completed, matrix_path, _ = _run_runner(tmp_path, flagship=flagship)

    assert completed.returncode == 0, completed.stderr
    matrix = _matrix(matrix_path)
    interpreter = matrix["interpreter"]
    assert interpreter["resolved_from"].startswith("auto-detect")
    assert interpreter["path"]
    assert Path(interpreter["path"]).name.lower().startswith("python")


# ---------------------------------------------------------------------------
# Fail-closed behaviour
# ---------------------------------------------------------------------------


def test_runner_fails_closed_on_missing_interpreter(tmp_path: Path) -> None:
    """A configured-but-absent interpreter is a hard error, not a false PASS."""
    flagship = _write_script(tmp_path / "fake_flagship.py", FAKE_FLAGSHIP)
    missing = tmp_path / "definitely-not-a-python"

    completed, matrix_path, _ = _run_runner(
        tmp_path,
        flagship=flagship,
        extra_args=["--python", str(missing)],
    )

    # Exit 2 == "invalid usage / missing dependency / environment error".
    assert completed.returncode == 2, completed.stdout + completed.stderr
    assert "interpreter" in (completed.stdout + completed.stderr).lower()
    # No matrix may be produced: a missing dependency is not evidence.
    assert not matrix_path.exists()


def test_runner_fails_closed_on_non_executable_interpreter(tmp_path: Path) -> None:
    """An interpreter that exists but cannot run is also a hard error."""
    flagship = _write_script(tmp_path / "fake_flagship.py", FAKE_FLAGSHIP)
    broken = tmp_path / "broken-python"
    broken.write_text("not a real interpreter\n", encoding="utf-8")
    broken.chmod(0o644)

    completed, matrix_path, _ = _run_runner(
        tmp_path,
        flagship=flagship,
        extra_args=["--python", str(broken)],
    )

    assert completed.returncode == 2, completed.stdout + completed.stderr
    assert not matrix_path.exists()


def test_runner_preserves_fail_closed_exit_status_on_failing_scenario(
    tmp_path: Path,
) -> None:
    """A failing scenario must not be reported as a passing gate run."""
    flagship = _write_script(tmp_path / "failing_flagship.py", FAILING_FLAGSHIP)

    completed, matrix_path, _ = _run_runner(
        tmp_path,
        flagship=flagship,
        runs=2,
        extra_args=["--python", _python_path()],
    )

    assert completed.returncode != 0, completed.stdout + completed.stderr
    matrix = _matrix(matrix_path)
    assert matrix["failed"] >= 1
    assert matrix["passed"] == 0
    assert matrix["interpreter"]["resolved_from"] == "--python"


# ---------------------------------------------------------------------------
# Matrix evidence
# ---------------------------------------------------------------------------


def test_matrix_records_passing_runs_with_interpreter_provenance(
    tmp_path: Path,
) -> None:
    """A green run produces a complete, interpreter-annotated matrix."""
    flagship = _write_script(tmp_path / "fake_flagship.py", FAKE_FLAGSHIP)

    completed, matrix_path, evidence_dir = _run_runner(
        tmp_path,
        flagship=flagship,
        runs=2,
        extra_args=["--python", _python_path()],
    )

    assert completed.returncode == 0, completed.stderr
    matrix = _matrix(matrix_path)
    assert matrix["gate"] == "G06"
    assert matrix["total_runs"] == 2
    assert matrix["passed"] == 2
    assert matrix["failed"] == 0
    assert len(matrix["runs"]) == 2
    for run in matrix["runs"]:
        assert run["exit_code"] == 0
        assert run["result"] == "PASS"
        assert run["evidence_sha256"]
    # Every run has its own evidence file on disk.
    assert len(sorted(evidence_dir.glob("*.json"))) == 2


def test_runner_rejects_unknown_flag_with_usage_exit_two(tmp_path: Path) -> None:
    """Unknown arguments stay fail-closed (exit 2) with the usage text."""
    completed = subprocess.run(
        [BASH or "bash", str(RUNNER), "--definitely-not-a-flag"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 2
    assert "--python" in completed.stdout
