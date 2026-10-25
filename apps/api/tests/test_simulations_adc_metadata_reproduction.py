"""End-to-end regression test for the ``GET /simulations`` HTTP 500.

The production defect (Kanban ``t_d8476d4b``) was a case-sensitivity
mismatch between the ADC transport and ``google-auth``:

* ``google-auth``'s compute-engine metadata transport reads response headers
  case-insensitively — ``response.headers["content-type"]``;
* the GCE metadata server answers with the canonical ``Content-Type`` casing;
* the stdlib-``urllib`` transport handed those headers back as a plain
  ``dict``, which is case-sensitive.

The lowercase lookup therefore raised ``KeyError: 'content-type'`` and every
Application Default Credentials refresh failed, so ``GET /simulations`` and
``GET /simulations/{id}`` returned HTTP 500.

This module reproduces the whole production chain against local emulators:

* a GCE metadata-server emulator that answers with canonical header casing;
* a Firestore REST stub that serves one simulation document;
* the real ``google.auth`` compute-engine credential, refreshed through the
  real ``firestore_decisions._UrllibAuthRequest`` transport;
* the real ``FirestoreSimulationRepository`` and the real FastAPI routes.

The test asserts both directions: the pre-fix behaviour fails (HTTP 500) and
the fixed behaviour succeeds (HTTP 200).
"""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Iterator

import pytest

from retailtwin_api import firestore_decisions, firestore_twin
from retailtwin_api.firestore_simulations import FirestoreSimulationRepository
from retailtwin_api.main import create_app
from retailtwin_api.settings import Settings

# The emulator must be reachable under a hostname the metadata client accepts.
# ``google-auth`` uses the host for the resource root and the IP for the ping,
# so both are pointed at the local server.
_SERVICE_ACCOUNT_EMAIL = "retailtwin-api@retailtwin-ai-511002.iam.gserviceaccount.com"
_PROJECT_ID = "retailtwin-ai-511002"
_ACCESS_TOKEN = "ya29.local-emulator-access-token"
_SCOPE = "https://www.googleapis.com/auth/datastore"
_SIMULATION_ID = "sim-seed-001"

_SIMULATION_PAYLOAD = {
    "simulation_id": _SIMULATION_ID,
    "store_id": "store-001",
    "base_context_version": "store-001:v1",
    "status": "evaluated",
    "created_at": "2026-10-19T09:00:00Z",
    "updated_at": "2026-10-19T09:05:00Z",
    "provenance": "simulation-service",
    "correlation_id": "corr-seed-001",
    "agent_id": "agent-001",
    "actions": [
        {
            "type": "move_product",
            "sku": "P001",
            "from_slot": "A01-S01",
            "to_slot": "A02-S01",
        }
    ],
    "state": {
        "store": {
            "store_id": "store-001",
            "context_version": "store-001:v1",
            "version": "v1",
            "products": [
                {
                    "store_id": "store-001",
                    "sku": "P001",
                    "shelf_id": "A01",
                    "slot_id": "A01-S01",
                    "facings": 3,
                    "shelf_quantity": 8,
                    "backroom_quantity": 42,
                    "version": 1,
                }
            ],
        },
        "context_version": f"{_SIMULATION_ID}:v1",
    },
}

_SIMULATION_DOCUMENT = {
    "name": (
        f"projects/{_PROJECT_ID}/databases/(default)/documents/"
        f"simulation_records/{_SIMULATION_ID}"
    ),
    "fields": {
        "simulation_id": {"stringValue": _SIMULATION_ID},
        "status": {"stringValue": "evaluated"},
        "simulation_json": {"stringValue": json.dumps(_SIMULATION_PAYLOAD)},
    },
}


# ---------------------------------------------------------------------------
# Local emulators
# ---------------------------------------------------------------------------


class _MetadataHandler(BaseHTTPRequestHandler):
    """A minimal GCE metadata server that uses canonical header casing."""

    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        return

    def _send(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        # The real metadata server uses this exact casing.
        self.send_header("Content-Type", content_type)
        self.send_header("Metadata-Flavor", "Google")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: dict[str, Any]) -> None:
        self._send(json.dumps(payload).encode("utf-8"), "application/json")

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path in ("/", "/computeMetadata/v1"):
            self._send(b"", "text/plain")
            return
        if path == "/computeMetadata/v1/project/project-id":
            self._send(_PROJECT_ID.encode("utf-8"), "text/plain")
            return
        if path == "/computeMetadata/v1/instance/service-accounts/default/":
            self._send_json(
                {
                    "email": _SERVICE_ACCOUNT_EMAIL,
                    "scopes": [_SCOPE],
                    "aliases": ["default"],
                }
            )
            return
        if path == "/computeMetadata/v1/instance/service-accounts/default/token":
            self._send_json(
                {
                    "access_token": _ACCESS_TOKEN,
                    "expires_in": 3600,
                    "token_type": "Bearer",
                }
            )
            return
        self._send_json({"error": "not found"}, status=404)


class _FirestoreHandler(BaseHTTPRequestHandler):
    """A minimal Firestore REST stub serving one simulation document."""

    protocol_version = "HTTP/1.1"

    #: The ``Authorization`` headers the stub received, in request order.
    authorization_headers: list[str] = []

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        return

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        type(self).authorization_headers.append(self.headers.get("Authorization", ""))
        path = self.path.split("?", 1)[0]
        if path.endswith(f"/simulation_records/{_SIMULATION_ID}"):
            self._send_json(_SIMULATION_DOCUMENT)
            return
        if path.endswith("/simulation_records"):
            self._send_json({"documents": [_SIMULATION_DOCUMENT]})
            return
        self._send_json({"error": {"status": "NOT_FOUND"}}, status=404)

    def do_PATCH(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        self._send_json(_SIMULATION_DOCUMENT)


class _StubTransport:
    """The production transport with only the destination host rewritten."""

    def __init__(self, base_url: str) -> None:
        self._base = base_url
        self._inner = firestore_twin.UrllibTransport()

    def request(self, method, url, payload, headers):  # noqa: ANN001, ANN201
        path = url.split("https://firestore.googleapis.com", 1)[-1]
        return self._inner.request(method, self._base + path, payload, headers)


@pytest.fixture(scope="module")
def emulators() -> Iterator[tuple[str, str]]:
    """Start both emulators and point ``google-auth`` at the metadata one."""
    metadata_server = ThreadingHTTPServer(("127.0.0.1", 0), _MetadataHandler)
    firestore_server = ThreadingHTTPServer(("127.0.0.1", 0), _FirestoreHandler)
    metadata_thread = threading.Thread(target=metadata_server.serve_forever, daemon=True)
    firestore_thread = threading.Thread(target=firestore_server.serve_forever, daemon=True)
    metadata_thread.start()
    firestore_thread.start()

    host_port = f"127.0.0.1:{metadata_server.server_address[1]}"
    firestore_base = f"http://127.0.0.1:{firestore_server.server_address[1]}"

    import google.auth.compute_engine._metadata as metadata_module

    original_host = metadata_module._GCE_METADATA_HOST
    original_ip_env = os.environ.get("GCE_METADATA_IP")
    original_host_env = os.environ.get("GCE_METADATA_HOST")
    metadata_module._GCE_METADATA_HOST = host_port
    # ``_get_metadata_ip_root`` reads the IP from the environment on every call,
    # so the ping reaches the local emulator too.
    os.environ["GCE_METADATA_IP"] = host_port
    os.environ["GCE_METADATA_HOST"] = host_port

    try:
        yield host_port, firestore_base
    finally:
        metadata_module._GCE_METADATA_HOST = original_host
        if original_ip_env is None:
            os.environ.pop("GCE_METADATA_IP", None)
        else:
            os.environ["GCE_METADATA_IP"] = original_ip_env
        if original_host_env is None:
            os.environ.pop("GCE_METADATA_HOST", None)
        else:
            os.environ["GCE_METADATA_HOST"] = original_host_env
        metadata_server.shutdown()
        firestore_server.shutdown()
        metadata_server.server_close()
        firestore_server.server_close()


@pytest.fixture
def gce_only_adc(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Force ``google.auth.default`` to use the compute-engine credential.

    On a developer machine an ambient Cloud SDK ADC file would otherwise win
    over the metadata server. Cloud Run has no such file, so the credential
    source is pinned here to match production.
    """
    import google.auth
    from google.auth import _default
    from google.auth import credentials as _credentials

    # Point the Cloud SDK lookup at an empty directory so no ambient ADC file
    # is discovered, exactly as on Cloud Run.
    empty_sdk_config = tmp_path / "gcloud-config"
    empty_sdk_config.mkdir()
    monkeypatch.setenv("CLOUDSDK_CONFIG", str(empty_sdk_config))
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)

    def _default_gce_only(scopes=None, request=None, **kwargs):  # noqa: ANN001, ANN202
        creds, project_id = _default._get_gce_credentials(request, quota_project_id=None)
        if creds is None:
            raise AssertionError("the compute-engine metadata server is not reachable")
        creds = _credentials.with_scopes_if_required(creds, scopes, default_scopes=None)
        return creds, project_id

    # ``google.auth.default`` is re-exported from ``google.auth._default``, so
    # both bindings have to be patched.
    monkeypatch.setattr(_default, "default", _default_gce_only)
    monkeypatch.setattr(google.auth, "default", _default_gce_only)


@pytest.fixture
def firestore_authorization_headers() -> list[str]:
    """The ``Authorization`` headers the Firestore stub received."""
    _FirestoreHandler.authorization_headers = []
    return _FirestoreHandler.authorization_headers


def _client(firestore_base: str):  # noqa: ANN202
    from fastapi.testclient import TestClient

    app = create_app(Settings(app_env="development", live_twin_backend="memory"))
    app.state.simulations = FirestoreSimulationRepository(
        transport=_StubTransport(firestore_base),
    )
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSimulationsEndpointWithMetadataServer:
    def test_list_and_detail_return_200(
        self, emulators, gce_only_adc, firestore_authorization_headers
    ) -> None:
        """The fixed transport refreshes the token and the routes answer 200."""
        _, firestore_base = emulators
        with _client(firestore_base) as client:
            listing = client.get("/simulations")
            detail = client.get(f"/simulations/{_SIMULATION_ID}")

        assert listing.status_code == 200, listing.text
        assert detail.status_code == 200, detail.text
        assert listing.json()["total"] == 1
        assert detail.json()["simulation_id"] == _SIMULATION_ID

        # The token really came from the metadata server, and it reached
        # Firestore as a bearer token.
        assert firestore_authorization_headers, "the Firestore stub saw no request"
        assert all(
            header == f"Bearer {_ACCESS_TOKEN}" for header in firestore_authorization_headers
        ), firestore_authorization_headers

    def test_case_sensitive_response_headers_reproduce_the_500(
        self, emulators, gce_only_adc, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The pre-fix behaviour (plain ``dict`` headers) returns HTTP 500.

        This is the exact production failure: the ADC refresh raises
        ``KeyError: 'content-type'``, the provider converts it into
        ``DecisionStoreUnavailable`` and the route answers HTTP 500.
        """

        class _CaseSensitiveResponse:
            __slots__ = ("status", "headers", "data")

            def __init__(self, status: int, headers, data: bytes) -> None:
                self.status = status
                self.headers = dict(headers)
                self.data = data

        monkeypatch.setattr(
            firestore_decisions, "_UrllibAuthResponse", _CaseSensitiveResponse
        )
        monkeypatch.setattr(firestore_twin, "_UrllibAuthResponse", _CaseSensitiveResponse)

        _, firestore_base = emulators
        with _client(firestore_base) as client:
            listing = client.get("/simulations")
            detail = client.get(f"/simulations/{_SIMULATION_ID}")

        assert listing.status_code == 500, listing.text
        assert detail.status_code == 500, detail.text
