#!/usr/bin/env python3
"""CI gate for licence and notice material (distribution obligation).

Run from the repository root. Exits non-zero when the repository's legal
material is missing, inconsistent, or not wired into the artefacts that are
actually distributed.

Checks:
  1. ``LICENSE`` exists at the repository root and carries the MIT notice.
  2. ``THIRD_PARTY_NOTICES.md`` exists at the repository root.
  3. The README's ``## License`` section references the licence file.
  4. Every bundled model pack under ``apps/web/public/models/`` retains its
     upstream ``License.txt`` notice, and every nested asset directory is
     covered by the notice of the pack that contains it.
  5. The published web copies (``apps/web/public/LICENSE`` and
     ``apps/web/public/THIRD_PARTY_NOTICES.md``) are byte-identical to the
     repository-root files.
  6. The container build ships the legal material: the Dockerfile copies
     ``LICENSE`` and ``THIRD_PARTY_NOTICES.md`` into the image and
     ``.dockerignore`` does not exclude them from the build context.

Designed to run on a self-hosted runner without third-party dependencies
(standard library only).
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

LICENSE_FILE = REPO_ROOT / "LICENSE"
NOTICES_FILE = REPO_ROOT / "THIRD_PARTY_NOTICES.md"
README_FILE = REPO_ROOT / "README.md"
DOCKERFILE = REPO_ROOT / "Dockerfile"
DOCKERIGNORE = REPO_ROOT / ".dockerignore"

WEB_PUBLIC = REPO_ROOT / "apps" / "web" / "public"
MODELS_DIR = WEB_PUBLIC / "models"

LICENSE_MARKERS = ("MIT License", "Permission is hereby granted, free of charge")

# Files that must be excluded from the container build context for the
# "ship the notice with the image" obligation to be satisfiable.
LEGAL_FILES = ("LICENSE", "THIRD_PARTY_NOTICES.md")


class GateError(Exception):
    """Raised when one of the licence-material checks fails."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_or_none(path: Path) -> str | None:
    """SHA-256 of ``path``, or ``None`` when the file does not exist."""
    if not path.is_file():
        return None
    return _sha256(path)


def _check_root_license() -> dict[str, object]:
    if not LICENSE_FILE.is_file():
        raise GateError(
            f"Root LICENSE file not found at {LICENSE_FILE}. The MIT licence "
            "must be present in the repository root and must ship with every "
            "distributed artefact."
        )
    text = LICENSE_FILE.read_text(encoding="utf-8")
    missing = [m for m in LICENSE_MARKERS if m not in text]
    if missing:
        raise GateError(
            f"Root LICENSE does not contain the expected MIT notice text "
            f"(missing: {', '.join(missing)})."
        )
    return {
        "check": "root_license",
        "path": "LICENSE",
        "bytes": LICENSE_FILE.stat().st_size,
        "sha256": _sha256(LICENSE_FILE),
        "ok": True,
    }


def _check_root_notices() -> dict[str, object]:
    if not NOTICES_FILE.is_file():
        raise GateError(
            f"Root THIRD_PARTY_NOTICES.md not found at {NOTICES_FILE}. The "
            "third-party attribution notice must be present in the "
            "repository root and must ship with every distributed artefact."
        )
    text = NOTICES_FILE.read_text(encoding="utf-8")
    if not text.strip():
        raise GateError("Root THIRD_PARTY_NOTICES.md is empty.")
    return {
        "check": "root_notices",
        "path": "THIRD_PARTY_NOTICES.md",
        "bytes": NOTICES_FILE.stat().st_size,
        "sha256": _sha256(NOTICES_FILE),
        "ok": True,
    }


def _readme_license_section() -> str:
    """Return the text of the README's ``## License`` section."""
    if not README_FILE.is_file():
        raise GateError(f"README.md not found at {README_FILE}.")
    text = README_FILE.read_text(encoding="utf-8")
    match = re.search(
        r"^##\s+License\s*$(.*?)(?=^##\s|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        raise GateError(
            "README.md has no '## License' section. The section must state "
            "which licence applies and must reference the licence file."
        )
    return match.group(1)


def _check_readme_references_license() -> dict[str, object]:
    section = _readme_license_section()
    if "LICENSE" not in section:
        raise GateError(
            "README.md '## License' section does not reference the LICENSE "
            f"file. Section text: {section.strip()[:200]!r}"
        )
    return {
        "check": "readme_license_reference",
        "section_excerpt": " ".join(section.split())[:200],
        "ok": True,
    }


def _model_packs() -> list[Path]:
    if not MODELS_DIR.is_dir():
        raise GateError(f"Model asset directory not found at {MODELS_DIR}.")
    return sorted(p for p in MODELS_DIR.iterdir() if p.is_dir())


def _check_model_license_notices() -> dict[str, object]:
    packs = _model_packs()
    if not packs:
        raise GateError(
            f"No bundled model packs found under {MODELS_DIR}. The licence "
            "gate expects at least one pack with a License.txt notice."
        )
    missing: list[str] = []
    covered: list[str] = []
    for pack in packs:
        notice = pack / "License.txt"
        if not notice.is_file():
            missing.append(f"{pack.relative_to(REPO_ROOT).as_posix()}/License.txt")
            continue
        # Every nested asset directory must sit under a pack that ships a
        # notice, so the third-party attribution travels with the asset.
        for nested in sorted(p for p in pack.rglob("*") if p.is_dir()):
            covered.append(nested.relative_to(REPO_ROOT).as_posix())
    if missing:
        raise GateError(
            "Model pack(s) without an upstream License.txt notice: "
            + ", ".join(missing)
        )
    return {
        "check": "model_license_notices",
        "packs": [p.relative_to(REPO_ROOT).as_posix() for p in packs],
        "covered_asset_dirs": covered,
        "ok": True,
    }


def _check_web_copies() -> dict[str, object]:
    results: list[dict[str, object]] = []
    for name in LEGAL_FILES:
        source = REPO_ROOT / name
        published = WEB_PUBLIC / name
        if not published.is_file():
            raise GateError(
                f"Published web copy missing: {published.relative_to(REPO_ROOT).as_posix()}. "
                "Vite copies apps/web/public/ into the hosted bundle, so the "
                "legal material must be present there."
            )
        source_digest = _sha256_or_none(source)
        if source_digest is None:
            raise GateError(
                f"Repository-root {name} is missing, so the published web copy "
                f"{published.relative_to(REPO_ROOT).as_posix()} cannot be "
                "verified against it."
            )
        if source_digest != _sha256(published):
            raise GateError(
                f"Published web copy {published.relative_to(REPO_ROOT).as_posix()} "
                f"is not byte-identical to {name}. Re-copy the file so the "
                "hosted bundle serves the same text as the repository."
            )
        results.append(
            {
                "path": published.relative_to(REPO_ROOT).as_posix(),
                "sha256": _sha256(published),
                "ok": True,
            }
        )
    return {"check": "web_published_copies", "files": results, "ok": True}


def _dockerignore_excludes(name: str) -> bool:
    """True when ``.dockerignore`` excludes ``name`` from the build context.

    Docker ignore rules are last-match-wins: the last rule that matches a
    path decides, and a ``!pattern`` rule re-includes it.

    The path model below was derived empirically against real ``docker build``
    runs (see the differential test in the PR body), and reproduces Docker's
    observed behaviour for the rule shapes this repository uses:

    * Matching is **anchored** at the context root. ``*.md`` excludes the
      root-level ``top.md`` but does **not** exclude ``sub/mid.md``; a bare
      name such as ``mid.md`` likewise does not match ``sub/mid.md``.
    * A pattern may match a **leading directory** of the path, in which case
      everything below that directory is excluded. ``sub`` and ``sub/`` both
      exclude ``sub/deep/low.md``.
    * ``**`` matches zero or more path components, so ``**/*.md`` matches the
      root-level ``top.md`` as well as ``sub/deep/low.md``.
    * Within one path component, ``*`` matches any run of characters other
      than ``/``, ``?`` matches exactly one, and ``[...]`` is a character
      class.
    * A trailing ``/`` restricts the rule to directories.
    * ``!`` re-includes; the last matching rule wins.
    """
    if not DOCKERIGNORE.is_file():
        raise GateError(f".dockerignore not found at {DOCKERIGNORE}.")
    excluded = False
    for raw in DOCKERIGNORE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        negated = line.startswith("!")
        if negated:
            line = line[1:].strip()
            if not line:
                continue
        if _dockerignore_pattern_matches(line, name):
            excluded = not negated
    return excluded


def _dockerignore_pattern_matches(pattern: str, name: str) -> bool:
    """Match ``name`` against one ``.dockerignore`` pattern.

    ``name`` is a context-relative POSIX path (e.g. ``THIRD_PARTY_NOTICES.md``
    or ``apps/web/public/LICENSE``).
    """
    pattern = pattern.replace("\\", "/")
    dir_only = pattern.endswith("/")
    pattern = pattern.strip("/")
    if not pattern:
        return False

    pat_parts = [p for p in pattern.split("/") if p not in (".", "")]
    path_parts = [p for p in name.replace("\\", "/").split("/") if p not in (".", "")]
    if not pat_parts or not path_parts:
        return False

    matched_prefix_len = _dockerignore_match_components(pat_parts, path_parts)
    if matched_prefix_len is None:
        return False
    if dir_only:
        # A directory-only rule matches only when it matches a leading
        # directory of the path, never the path itself.
        return matched_prefix_len < len(path_parts)
    return True


def _dockerignore_match_components(
    pat_parts: list[str], path_parts: list[str]
) -> int | None:
    """Match pattern components against path components.

    Returns the number of path components consumed when the pattern matches
    (which may be fewer than ``len(path_parts)`` when the pattern matches a
    leading directory), or ``None`` when it does not match.
    """
    if not pat_parts:
        return 0
    if not path_parts:
        return None
    head, rest = pat_parts[0], pat_parts[1:]
    if head == "**":
        # `**` matches zero or more path components.
        for skip in range(len(path_parts) + 1):
            consumed = _dockerignore_match_components(rest, path_parts[skip:])
            if consumed is not None:
                return skip + consumed
        return None
    if not _dockerignore_component_matches(head, path_parts[0]):
        return None
    consumed = _dockerignore_match_components(rest, path_parts[1:])
    if consumed is None:
        return None
    return 1 + consumed


def _dockerignore_component_matches(pattern: str, component: str) -> bool:
    """Match a single path component against a glob pattern."""
    return re.fullmatch(_dockerignore_glob_to_regex(pattern), component) is not None


def _dockerignore_glob_to_regex(pattern: str) -> str:
    """Translate one Docker glob component into an anchored regular expression."""
    out: list[str] = []
    i = 0
    length = len(pattern)
    while i < length:
        char = pattern[i]
        if char == "*":
            out.append("[^/]*")
        elif char == "?":
            out.append("[^/]")
        elif char == "[":
            # Character class: copy it verbatim, honouring a leading '!' or '^'.
            end = i + 1
            if end < length and pattern[end] in ("!", "^"):
                end += 1
            if end < length and pattern[end] == "]":
                end += 1
            while end < length and pattern[end] != "]":
                end += 1
            if end >= length:
                # Unterminated class: treat '[' literally.
                out.append(re.escape("["))
            else:
                body = pattern[i + 1 : end]
                if body.startswith("!"):
                    body = "^" + body[1:]
                out.append("[" + body.replace("\\", "\\\\") + "]")
                i = end
        else:
            out.append(re.escape(char))
        i += 1
    return "".join(out)


def _check_container_ships_legal_material() -> dict[str, object]:
    if not DOCKERFILE.is_file():
        raise GateError(f"Dockerfile not found at {DOCKERFILE}.")
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    missing_copies: list[str] = []
    for name in LEGAL_FILES:
        if not re.search(rf"^\s*COPY\s+[^\n]*\b{re.escape(name)}\b", dockerfile, re.MULTILINE):
            missing_copies.append(name)
    if missing_copies:
        raise GateError(
            "Dockerfile does not copy the legal material into the image: "
            + ", ".join(missing_copies)
            + ". The MIT notice must accompany every copy of the software."
        )
    excluded = [name for name in LEGAL_FILES if _dockerignore_excludes(name)]
    if excluded:
        raise GateError(
            ".dockerignore excludes the legal material from the build "
            "context: " + ", ".join(excluded)
        )
    return {
        "check": "container_ships_legal_material",
        "copied": list(LEGAL_FILES),
        "ok": True,
    }


def main() -> int:
    checks = (
        ("root_license", _check_root_license),
        ("root_notices", _check_root_notices),
        ("readme_license_reference", _check_readme_references_license),
        ("model_license_notices", _check_model_license_notices),
        ("web_published_copies", _check_web_copies),
        ("container_ships_legal_material", _check_container_ships_legal_material),
    )
    results: list[dict[str, object]] = []
    for name, fn in checks:
        try:
            results.append(fn())
        except GateError as exc:
            results.append({"check": name, "ok": False, "error": str(exc)})

    print(json.dumps({"results": results}, indent=2))
    failed = [r for r in results if not r.get("ok")]
    if failed:
        print("\nLicence material gate FAILED:", file=sys.stderr)
        for r in failed:
            print(f"  - {r.get('check')}: {r.get('error')}", file=sys.stderr)
        return 1
    print("\nLicence material gate PASSED.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
