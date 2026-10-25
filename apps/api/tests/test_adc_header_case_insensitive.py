"""Regression tests for case-insensitive ADC response headers.

The compute-engine metadata transport shipped with ``google-auth`` reads
response headers case-insensitively::

    # google/auth/compute_engine/_metadata.py
    _helpers.parse_content_type(response.headers["content-type"])

The GCE metadata server answers with the canonical ``Content-Type`` casing, so
a transport that returns a plain ``dict`` of headers raises
``KeyError: 'content-type'`` and every Application Default Credentials
refresh fails with ``Application Default Credentials are not available:
KeyError``.

These tests exercise the real ``google-auth`` metadata code path against the
stdlib-``urllib`` transport used by the ADC providers, so they fail on the
unfixed code and pass on the fixed code.
"""

from __future__ import annotations

import io
import urllib.error
import urllib.request
from typing import Any

import pytest

from retailtwin_api.firestore_decisions import _UrllibAuthRequest as DecisionsAuthRequest
from retailtwin_api.firestore_twin import _UrllibAuthRequest as TwinAuthRequest
from retailtwin_api.http_headers import CaseInsensitiveHeaders

google_auth = pytest.importorskip("google.auth")
# ``google.auth.compute_engine._metadata`` imports ``requests`` at module level,
# which is only present transitively (via google-api-core). Skip cleanly when
# the extra is unavailable rather than failing the suite.
_metadata = pytest.importorskip("google.auth.compute_engine._metadata")


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeResponse(io.BytesIO):
    """A minimal stand-in for the object returned by ``urlopen``."""

    def __init__(self, status: int, headers: dict[str, str], body: bytes) -> None:
        super().__init__(body)
        self.status = status
        self.headers = headers

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def _install_fake_urlopen(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    headers: dict[str, str],
    body: bytes,
) -> None:
    def fake_urlopen(request: object, timeout: float | None = None) -> _FakeResponse:
        return _FakeResponse(status, headers, body)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)


# ---------------------------------------------------------------------------
# The header mapping layer
# ---------------------------------------------------------------------------


class TestCaseInsensitiveHeaders:
    def test_lookup_is_case_insensitive(self) -> None:
        headers = CaseInsensitiveHeaders({"Content-Type": "application/json"})

        assert headers["content-type"] == "application/json"
        assert headers["Content-Type"] == "application/json"
        assert headers["CONTENT-TYPE"] == "application/json"

    def test_get_is_case_insensitive_and_defaults_to_none(self) -> None:
        headers = CaseInsensitiveHeaders({"Metadata-Flavor": "Google"})

        assert headers.get("metadata-flavor") == "Google"
        assert headers.get("Metadata-Flavor") == "Google"
        assert headers.get("missing") is None
        assert headers.get("missing", "fallback") == "fallback"

    def test_membership_is_case_insensitive(self) -> None:
        headers = CaseInsensitiveHeaders({"Content-Type": "application/json"})

        assert "content-type" in headers
        assert "Content-Type" in headers
        assert "content-length" not in headers

    def test_missing_key_raises_key_error_with_the_requested_name(self) -> None:
        headers = CaseInsensitiveHeaders({"Content-Type": "application/json"})

        with pytest.raises(KeyError):
            headers["content-length"]

    def test_iteration_preserves_the_original_casing(self) -> None:
        headers = CaseInsensitiveHeaders({"Content-Type": "application/json"})

        assert list(headers) == ["Content-Type"]
        assert dict(headers) == {"Content-Type": "application/json"}

    def test_empty_mapping_is_falsy_but_usable(self) -> None:
        headers = CaseInsensitiveHeaders({})

        assert len(headers) == 0
        assert headers.get("content-type") is None


# ---------------------------------------------------------------------------
# The transport response objects
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("transport_cls", [DecisionsAuthRequest, TwinAuthRequest])
class TestUrllibAuthResponseHeaders:
    def test_response_headers_are_case_insensitive(
        self, transport_cls: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_fake_urlopen(
            monkeypatch,
            200,
            {"Content-Type": "application/json", "Metadata-Flavor": "Google"},
            b"{}",
        )

        response = transport_cls()("http://metadata.google.internal/computeMetadata/v1/")

        assert response.headers["content-type"] == "application/json"
        assert response.headers.get("metadata-flavor") == "Google"

    def test_error_response_headers_are_case_insensitive(
        self, transport_cls: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def denied(request: object, timeout: float | None = None) -> object:
            raise urllib.error.HTTPError(  # type: ignore[arg-type]
                "http://metadata.google.internal/",
                401,
                "unauthorised",
                {"Content-Type": "text/plain"},
                io.BytesIO(b"denied"),
            )

        monkeypatch.setattr(urllib.request, "urlopen", denied)

        response = transport_cls()("http://metadata.google.internal/")

        assert response.status == 401
        assert response.headers["content-type"] == "text/plain"


# ---------------------------------------------------------------------------
# The real google-auth metadata code path
# ---------------------------------------------------------------------------


def test_google_auth_metadata_lookup_resolves_with_canonical_casing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``google.auth`` must be able to read ``content-type`` from our transport.

    Without the fix the lookup raises ``KeyError: 'content-type'`` because the
    metadata server answers with ``Content-Type``.
    """
    _install_fake_urlopen(
        monkeypatch,
        200,
        {"Content-Type": "application/json"},
        b'{"access_token": "test-token", "expires_in": 3600, "token_type": "Bearer"}',
    )

    from google.auth.compute_engine import _metadata as metadata_module

    payload = metadata_module.get(
        DecisionsAuthRequest(),
        path="/instance/service-accounts/default/token",
        root="http://metadata.google.internal/computeMetadata/v1/",
        headers={"Metadata-Flavor": "Google"},
    )

    assert payload["access_token"] == "test-token"


def test_google_auth_metadata_lookup_fails_without_the_fix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Guard: a plain ``dict`` of headers reproduces the production KeyError.

    This is the pre-fix behaviour of the transport. It is kept as an explicit
    guard so the regression cannot silently reappear: if the metadata server
    ever answered with a lowercase ``content-type``, the plain-``dict``
    transport would work by accident and this guard would fail.
    """
    _install_fake_urlopen(
        monkeypatch,
        200,
        {"Content-Type": "application/json"},
        b'{"access_token": "test-token"}',
    )

    from google.auth.compute_engine import _metadata as metadata_module

    with pytest.raises(KeyError):
        metadata_module.get(
            _PlainDictAuthRequest(),
            path="/instance/service-accounts/default/token",
            root="http://metadata.google.internal/computeMetadata/v1/",
            headers={"Metadata-Flavor": "Google"},
        )


class _PlainDictAuthRequest:
    """The pre-fix transport: response headers as a plain, case-sensitive dict."""

    def __call__(
        self,
        url: str,
        method: str = "GET",
        body: bytes | None = None,
        headers: Any = None,
        timeout: float | None = None,
        **_: Any,
    ) -> Any:
        request = urllib.request.Request(url, data=body, method=method, headers=dict(headers or {}))
        try:
            with urllib.request.urlopen(request, timeout=timeout or 10) as response:
                return _PlainDictResponse(response.status, dict(response.headers), response.read())
        except urllib.error.HTTPError as exc:
            return _PlainDictResponse(exc.code, dict(exc.headers or {}), exc.read())


class _PlainDictResponse:
    def __init__(self, status: int, headers: dict[str, str], data: bytes) -> None:
        self.status = status
        self.headers = headers
        self.data = data
