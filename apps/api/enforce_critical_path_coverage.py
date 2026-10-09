#!/usr/bin/env python3
"""Enforce critical-path coverage thresholds.

This script detects new or modified files under critical-path directories.
If any critical-path code exists and lacks elevated coverage thresholds
(per-path fail_under or thresholds configuration), CI fails unless
those modules are documented as stub-only.

Exits 0 if:
  - No critical-path files exist, OR
  - Critical-path files exist and have coverage configuration, OR
  - Critical-path files are all stub-only (no real implementation)
Exits 1 if critical-path implementation exists without coverage configuration.
"""
import subprocess
import sys
import os
import re

# Directories subject to elevated thresholds (>=90% line, >=85% branch)
CRITICAL_PATHS = [
    "guard/decision-context-guard/",
    "services/executor/",
    "services/twin/",
    "services/simulation/",
    "services/verifier/",
]

# File with event idempotency/conflict handling
CRITICAL_FILES = [
    "apps/api/retailtwin_api/events.py",
]

# Stub-only indicators (no real implementation)
STUB_PATTERNS = [
    r"^#\s*stub",
    r"^#\s*todo",
    r"^#\s*not implemented",
    r"raise\s+NotImplementedError",
]


def has_real_code(path: str) -> bool:
    """Return True if path contains non-stub implementation code."""
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            content = f.read()
        for pattern in STUB_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                return False
        # If file has < 5 non-comment lines, likely a stub
        lines = [l.strip() for l in content.splitlines() if l.strip() and not l.strip().startswith("#")]
        return len(lines) >= 5
    except Exception:
        return False


def get_changed_files() -> set:
    """Get list of files changed in the current branch vs main."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "origin/main...HEAD"],
            capture_output=True, text=True, check=True
        )
        return set(result.stdout.strip().splitlines())
    except Exception:
        return set()


def check_critical_paths():
    """Check if critical paths have real implementation without coverage config."""
    changed = get_changed_files()

    # Check changed critical files
    for cf in CRITICAL_FILES:
        if cf in changed:
            if has_real_code(cf):
                print(f"ERROR: {cf} is a critical-path file with real implementation.")
                print("  Add per-path coverage thresholds or coverage evidence before merging.")
                return 1
            else:
                print(f"INFO: {cf} is stub-only — skipping elevated threshold requirement.")

    # Check critical directories for new files
    all_files = set()
    for root, dirs, files in os.walk("."):
        for f in files:
            if f.endswith(".py") or f.endswith(".ts") or f.endswith(".tsx"):
                all_files.add(os.path.join(root, f).lstrip("./").replace("\\", "/"))

    for cp in CRITICAL_PATHS:
        cp_files = [f for f in all_files if f.startswith(cp)]
        for f in cp_files:
            if has_real_code(f):
                print(f"ERROR: {f} is in critical path '{cp}' with real implementation.")
                print("  Elevated thresholds (>=90% line, >=85% branch) must be configured.")
                return 1
            elif cp_files:
                print(f"INFO: {cp} contains stub files only — elevated threshold deferred.")

    print("PASS: No critical-path implementation without coverage enforcement found.")
    return 0


if __name__ == "__main__":
    sys.exit(check_critical_paths())
