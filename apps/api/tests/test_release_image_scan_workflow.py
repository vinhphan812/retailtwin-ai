#!/usr/bin/env python3
"""Static contract checks for the fail-closed production image scan."""
from __future__ import annotations

from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[3] / ".github/workflows/api.yml"


def section(text: str, start: str, end: str) -> str:
    """Return the workflow slice starting at ``start`` and ending before ``end``."""
    return text[text.index(start) : text.index(end, text.index(start))]


def test_release_image_scan_uses_wif_token_not_gcloud_credential_helper() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    scan = section(workflow, "      - name: Scan pushed release image", "      - name: Deploy to Cloud Run")

    assert "id: google-auth" in workflow
    assert "token_format: access_token" in workflow
    assert "TRIVY_USERNAME: oauth2accesstoken" in scan
    assert "TRIVY_PASSWORD: ${{ steps.google-auth.outputs.access_token }}" in scan
    assert "-e TRIVY_USERNAME" in scan
    assert "-e TRIVY_PASSWORD" in scan
    assert "docker-credential-gcloud" not in scan
    assert "$HOME/.docker" not in scan


def test_release_image_is_pushed_verified_scanned_then_deployed() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    build = workflow.index("      - name: Build and push container image")
    verify = workflow.index("      - name: Verify pushed release image exists")
    scan = workflow.index("      - name: Scan pushed release image")
    deploy = workflow.index("      - name: Deploy to Cloud Run")

    assert build < verify < scan < deploy
    assert "push: true" in workflow[build:verify]
    assert 'gcloud container images describe \\' in workflow[verify:scan]
    assert "--ignore-unfixed --severity HIGH,CRITICAL --exit-code 1" in workflow[scan:deploy]
    assert "set -euo pipefail" in workflow[verify:scan]
    assert "set -euo pipefail" in workflow[scan:deploy]
    assert "test -n \"$TRIVY_PASSWORD\"" in workflow[scan:deploy]
