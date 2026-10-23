"""Contract tests for the fail-closed G06 shell gate runner."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE = REPO_ROOT / "scripts" / "run-submission-gate.sh"

IS_WINDOWS = os.name == "nt"


def _bash_executable() -> str:
    """Return a usable bash (Git Bash on Windows, system bash elsewhere)."""
    override = os.environ.get("G06_TEST_BASH")
    if override:
        return override
    if IS_WINDOWS:
        for candidate in (
            r"C:\Program Files\Git\bin\bash.exe",
            r"C:\Program Files\Git\usr\bin\bash.exe",
        ):
            if Path(candidate).exists():
                return candidate
    found = shutil.which("bash")
    if found:
        return found
    pytest.skip("no bash executable available to run the G06 gate script")


def _bash_path(path: Path) -> str:
    """Convert a native path into a path the bash process can resolve."""
    if not IS_WINDOWS:
        return str(path)
    converted = subprocess.run(
        ["cygpath", "-u", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    return converted.stdout.strip() if converted.returncode == 0 else str(path)


def _fake_flagship(tmp_path: Path, body: str) -> Path:
    runner = tmp_path / "fake_flagship.py"
    runner.write_text(body, encoding="utf-8")
    return runner


def _run_gate(tmp_path: Path, flagship: Path, runs: int = 2, **env: str) -> subprocess.CompletedProcess[str]:
    evidence_dir = tmp_path / "evidence"
    matrix = tmp_path / "matrix.json"
    process_env = os.environ | env
    if "PYTHON_BIN" not in env:
        process_env["PYTHON_BIN"] = sys.executable
    return subprocess.run(
        [
            _bash_executable(),
            _bash_path(GATE),
            "--runs",
            str(runs),
            "--seed",
            "test",
            "--flagship",
            _bash_path(flagship),
            "--evidence-dir",
            _bash_path(evidence_dir),
            "--out",
            _bash_path(matrix),
        ],
        cwd=str(REPO_ROOT),
        env=process_env,
        text=True,
        capture_output=True,
        check=False,
    )


def _matrix(tmp_path: Path) -> dict:
    return json.loads((tmp_path / "matrix.json").read_text(encoding="utf-8"))


def test_gate_halts_after_nonzero_scenario_failure(tmp_path: Path) -> None:
    count_file = tmp_path / "count.txt"
    flagship = _fake_flagship(
        tmp_path,
        """import os
from pathlib import Path
Path(os.environ['COUNT_FILE']).write_text('called')
raise SystemExit(17)
""",
    )

    result = _run_gate(tmp_path, flagship, runs=3, COUNT_FILE=str(count_file))

    assert result.returncode == 1
    assert count_file.read_text(encoding="utf-8") == "called"
    matrix = _matrix(tmp_path)
    assert matrix["failed"] == 1
    assert matrix["executed_runs"] == 1
    assert matrix["halted_on_failure"] is True
    assert matrix["runs"][0]["exit_code"] == 17


def test_gate_rejects_fail_evidence_even_when_runner_exits_zero(tmp_path: Path) -> None:
    flagship = _fake_flagship(
        tmp_path,
        """import argparse, json
from pathlib import Path
p = argparse.ArgumentParser(); p.add_argument('--run-id'); p.add_argument('--out')
a = p.parse_args()
Path(a.out).write_text(json.dumps({'result': 'FAIL'}), encoding='utf-8')
""",
    )

    result = _run_gate(tmp_path, flagship)

    assert result.returncode == 1
    matrix = _matrix(tmp_path)
    assert matrix["failed"] == 1
    assert matrix["executed_runs"] == 1
    assert matrix["runs"][0]["result"] == "FAIL"
    assert matrix["runs"][0]["evidence_sha256"]


def test_gate_writes_reproducible_provenance_for_green_run(tmp_path: Path) -> None:
    flagship = _fake_flagship(
        tmp_path,
        """import argparse, json
from pathlib import Path
p = argparse.ArgumentParser(); p.add_argument('--run-id'); p.add_argument('--out')
a = p.parse_args()
Path(a.out).write_text(json.dumps({'result': 'PASS', 'run_id': a.run_id}), encoding='utf-8')
""",
    )

    result = _run_gate(tmp_path, flagship, PYTHONPATH="")

    assert result.returncode == 0, result.stderr
    matrix = _matrix(tmp_path)
    assert matrix["passed"] == 2
    assert matrix["failed"] == 0
    assert matrix["executed_runs"] == 2
    assert matrix["provenance"]["tested_git_sha"]
    assert matrix["provenance"]["command"]
    assert matrix["provenance"]["started_at"].endswith("Z")
    assert matrix["provenance"]["finished_at"].endswith("Z")
    assert matrix["provenance"]["runner_sha256"]
    assert matrix["provenance"]["flagship_sha256"]
    assert "apps/api" in matrix["provenance"]["pythonpath"].replace("\\", "/")
    assert all(run["evidence_sha256"] for run in matrix["runs"])
    assert all(run["evidence_file_sha256"] for run in matrix["runs"])


def test_gate_records_explicit_pythonpath_verbatim(tmp_path: Path) -> None:
    flagship = _fake_flagship(
        tmp_path,
        """import argparse, json
from pathlib import Path
p = argparse.ArgumentParser(); p.add_argument('--run-id'); p.add_argument('--out')
a = p.parse_args()
Path(a.out).write_text(json.dumps({'result': 'PASS'}), encoding='utf-8')
""",
    )

    result = _run_gate(tmp_path, flagship, runs=1, PYTHONPATH="sentinel-pythonpath")

    assert result.returncode == 0, result.stderr
    assert _matrix(tmp_path)["provenance"]["pythonpath"] == "sentinel-pythonpath"


def test_gate_fails_closed_when_configured_interpreter_is_missing(tmp_path: Path) -> None:
    result = _run_gate(tmp_path, tmp_path / "does-not-matter.py", PYTHON_BIN="definitely-not-installed")

    assert result.returncode == 2
    assert "ERROR: Python interpreter not found" in result.stderr


def test_gate_fails_closed_when_flagship_runner_is_missing(tmp_path: Path) -> None:
    result = _run_gate(tmp_path, tmp_path / "missing-flagship.py")

    assert result.returncode == 2
    assert "ERROR: flagship runner not found" in result.stderr
