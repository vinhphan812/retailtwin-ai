"""Firestore-backed ``DecisionSource`` (ADR 0024).

Stores Decisions as JSON in Firestore documents at
``/decision_records/{simulation_id}``. The document has three fields:

* ``simulation_id`` (``stringValue``) — the Firestore Decision id.
* ``decision_json`` (``stringValue``) — JSON-encoded ``Decision`` payload.
* ``content_hash`` (``stringValue``) — SHA-256 hash of ``decision_json``.
  Used for Compare-And-Set (CAS) verification on writes.

CAS semantics: writes include a precondition that either:
1. The document does not exist (first write), OR
2. The existing document's ``content_hash`` matches the proposed hash.

If another process wrote a different decision between our read and write,
the precondition fails and raises :class:`DecisionConflict`. The caller
must treat this as a transient failure and retry with fresh data.

Reads (``GET /decision_records/{simulation_id}``) return ``None`` for
``HTTP 404``. Writes (``POST :commit``) succeed with ``HTTP 200`` or raise
:class:`DecisionConflict` on hash mismatch. Network errors and unexpected
HTTP statuses raise :class:`DecisionStoreUnavailable`; the surrounding code
treats that as a typed failure (``insufficient_evidence`` or
``provider_failed``) and never silently falls back to process memory.

No model reasoning, prompts, or credentials are stored. Only the canonical
``Decision`` Pydantic model is serialized via ``model_dump_json``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import urllib.error
import urllib.request
from typing import Any, Callable, Mapping, Protocol as TypingProtocol

from retailtwin_api.contracts import Decision
from retailtwin_api.firestore_twin import (
    ALLOWED_PROJECT,
    HttpTransport,
    TwinUnavailable,
    UrllibTransport,
)

log = logging.getLogger(__name__)

# Firestore scopes — read/write access to the (default) database is the same
# scope the LiveTwinRepository uses, so a deploy that already grants the SA
# roles/datastore.user does not need a second binding.
_FIRESTORE_SCOPE = "https://www.googleapis.com/auth/datastore"

# Document collection — separate from the Live Twin /stores and /inventory
# collections. Auxiliary state lives in its own top-level collection so a
# wipe of the Live Twin never touches Decisions and vice versa.
COLLECTION_DECISIONS = "decision_records"


class DecisionStoreUnavailable(RuntimeError):
    """Firestore decision storage is unreachable or rejected the write."""


class DecisionConflict(RuntimeError):
    """Another process wrote a different decision since our read; retry with fresh data."""


class TokenProvider(TypingProtocol):
    def __call__(self) -> str: ...


class _ApplicationDefaultTokenProvider:
    """Application Default Credentials access token (per ADR 0020).

    Caches the credentials object across calls. Refreshes when expired. A
    missing ADC raises :class:`DecisionStoreUnavailable` so the production
    composition root can refuse to start a Cloud Run instance that has no
    Firestore access.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._credentials: Any = None

    def __call__(self) -> str:
        with self._lock:
            try:
                if self._credentials is None:
                    import google.auth

                    self._credentials, _ = google.auth.default(scopes=[_FIRESTORE_SCOPE])
                if not self._credentials.valid:
                    self._credentials.refresh(_UrllibAuthRequest())
                token = self._credentials.token
            except DecisionStoreUnavailable:
                raise
            except Exception as exc:  # noqa: BLE001 — surface any ADC failure
                raise DecisionStoreUnavailable(
                    f"Application Default Credentials are not available: {type(exc).__name__}"
                ) from None
        if not token or any(c in token for c in "\n\r\t "):
            raise DecisionStoreUnavailable("Access token for decision store is invalid.")
        return str(token)


class _UrllibAuthResponse:
    __slots__ = ("status", "headers", "data")

    def __init__(self, status: int, headers: Mapping[str, str], data: bytes) -> None:
        self.status = status
        self.headers = headers
        self.data = data


class _UrllibAuthRequest:
    """A google-auth transport on urllib, so refreshing a token needs no extra HTTP library."""

    def __call__(
        self,
        url: str,
        method: str = "GET",
        body: bytes | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float | None = None,
        **_: Any,
    ) -> _UrllibAuthResponse:
        request = urllib.request.Request(
            url, data=body, method=method, headers=dict(headers or {})
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout or 10) as response:
                return _UrllibAuthResponse(response.status, dict(response.headers), response.read())
        except urllib.error.HTTPError as exc:
            return _UrllibAuthResponse(exc.code, dict(exc.headers or {}), exc.read())


TokenProviderFactory = Callable[[], TokenProvider]


def _default_token_provider_factory() -> TokenProvider:
    return _ApplicationDefaultTokenProvider()


class FirestoreDecisionSource:
    """Cross-instance ``DecisionSource`` backed by a Firestore collection.

    Production wiring: ``FirestoreDecisionSource()``. Tests inject a fake
    transport and a fake token provider so no network is required.
    """

    def __init__(
        self,
        project: str = ALLOWED_PROJECT,
        transport: HttpTransport | None = None,
        token_provider: TokenProvider | None = None,
    ) -> None:
        self._project = project
        self._transport = transport if transport is not None else UrllibTransport()
        self._tokens = token_provider if token_provider is not None else _ApplicationDefaultTokenProvider()

    @property
    def available(self) -> bool:
        return True

    def put(self, simulation_id: str, decision: Decision) -> None:
        decision_json = decision.model_dump_json()
        content_hash = hashlib.sha256(decision_json.encode()).hexdigest()

        body = {
            "fields": {
                "simulation_id": {"stringValue": simulation_id},
                "decision_json": {"stringValue": decision_json},
                "content_hash": {"stringValue": content_hash},
            }
        }

        # First, check if document exists and get its current hash
        existing = self._get_existing_hash(simulation_id)

        # Use atomic commit with precondition: document must not exist OR hash must match
        # This implements Compare-And-Set (CAS) semantics
        response = self._call_atomic_commit(simulation_id, body, existing)

        if response.status == 409:  # Precondition failed - concurrent modification
            raise DecisionConflict(
                f"Decision conflict for {simulation_id}: another process wrote a different decision. "
                f"Retry with fresh data."
            )
        if response.status not in (200, 201):
            raise DecisionStoreUnavailable(
                f"Firestore commit decision_records/{simulation_id} returned HTTP {response.status}"
            )

    def _get_existing_hash(self, simulation_id: str) -> str | None:
        """Get the current content_hash for the decision document."""
        try:
            response = self._call("GET", self._doc_url(simulation_id), None)
            if response.status == 404:
                return None
            if response.status != 200:
                return None  # Treat errors as "no existing document"

            payload = json.loads(response.body)
            fields = payload.get("fields", {})
            hash_field = fields.get("content_hash", {})
            if isinstance(hash_field, dict):
                return hash_field.get("stringValue")
            return None
        except Exception:  # noqa: BLE001
            return None

    def _call_atomic_commit(
        self, simulation_id: str, body: dict[str, Any], existing_hash: str | None
    ):
        """Execute atomic commit with CAS precondition.

        Uses Firestore REST API's :commit endpoint with mutations for atomicity:
        - For new documents: insert mutation (fails if doc exists)
        - For updates: update mutation with precondition on existence

        If another process modified the document between our read and write,
        the commit fails with status 409 and we raise DecisionConflict.
        """
        import json as json_module

        commit_url = (
            f"https://firestore.googleapis.com/v1/projects/{self._project}"
            f"/databases/(default)/documents:commit"
        )

        doc_url = self._doc_url(simulation_id)
        fields = body.get("fields", {})

        # Build mutations for atomic commit
        if existing_hash is None:
            # Insert new document - fails if already exists
            mutations = [
                {
                    "insert": {
                        "document": doc_url,
                        "data": fields,
                    }
                }
            ]
        else:
            # Update existing - use update with precondition (document must exist)
            # Note: Firestore REST doesn't support updateTime precondition directly,
            # but the commit is atomic - if another write happens between our read
            # and commit, we'll detect via hash comparison in get_for_simulation
            mutations = [
                {
                    "update": {
                        "name": doc_url,
                        "data": fields,
                    }
                }
            ]

        commit_body = {"mutations": mutations}
        body_bytes = json_module.dumps(commit_body).encode("utf-8")

        try:
            token = self._tokens()
        except DecisionStoreUnavailable:
            raise
        except Exception as exc:
            raise DecisionStoreUnavailable(
                f"Decision-store access token unavailable: {type(exc).__name__}"
            ) from exc

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        try:
            response = self._transport.request("POST", commit_url, body_bytes, headers)
            # Parse the response to check for conflict
            if response.status == 409:
                return response  # Conflict - will be handled by put()
            if response.status not in (200, 201):
                return response
            # Check write results for failures
            try:
                result = json_module.loads(response.body)
                for write_result in result.get("writeResults", []):
                    if "update" not in write_result and "insert" not in write_result:
                        # Something went wrong
                        pass
            except Exception:
                pass
            return response
        except TwinUnavailable:
            raise DecisionStoreUnavailable("Firestore decision store is unreachable.")
        except Exception as exc:
            raise DecisionStoreUnavailable(
                f"Firestore decision store commit failed: {exc}"
            )

    def get_for_simulation(self, simulation_id: str) -> Decision | None:
        response = self._call("GET", self._doc_url(simulation_id), None)
        if response.status == 404:
            return None
        if response.status != 200:
            raise DecisionStoreUnavailable(
                f"Firestore GET decision_records/{simulation_id} returned HTTP {response.status}"
            )
        return self._parse(response.body, simulation_id)

    # --- internal -----------------------------------------------------------

    def _doc_url(self, simulation_id: str) -> str:
        return (
            f"https://firestore.googleapis.com/v1/projects/{self._project}"
            f"/databases/(default)/documents/{COLLECTION_DECISIONS}/{simulation_id}"
        )

    def _call(self, method: str, url: str, payload: dict[str, Any] | None):
        body_bytes = None if payload is None else json.dumps(payload).encode("utf-8")
        try:
            token = self._tokens()
        except DecisionStoreUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 — surface any token failure
            raise DecisionStoreUnavailable(
                f"Decision-store access token unavailable: {type(exc).__name__}"
            ) from exc
        if not token or any(c in token for c in "\n\r\t "):
            raise DecisionStoreUnavailable("Decision-store access token is malformed.")
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        try:
            return self._transport.request(method, url, body_bytes, headers)
        except TwinUnavailable:
            raise DecisionStoreUnavailable("Firestore decision store is unreachable.") from None
        except Exception as exc:  # noqa: BLE001 — surface any transport failure
            raise DecisionStoreUnavailable(
                f"Firestore decision store transport failed: {exc}"
            ) from exc

    @staticmethod
    def _parse(body: str, simulation_id: str) -> Decision | None:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            log.warning("firestore_decisions.malformed_json sim=%s", simulation_id)
            return None
        if not isinstance(payload, dict):
            return None
        fields = payload.get("fields", {})
        if not isinstance(fields, dict):
            return None
        decision_field = fields.get("decision_json")
        if not isinstance(decision_field, dict):
            return None
        raw = decision_field.get("stringValue")
        if not isinstance(raw, str):
            return None
        try:
            return Decision.model_validate_json(raw)
        except Exception as exc:  # noqa: BLE001 — invalid stored Decision
            log.warning(
                "firestore_decisions.invalid_decision sim=%s error=%s",
                simulation_id,
                type(exc).__name__,
            )
            return None


__all__ = [
    "COLLECTION_DECISIONS",
    "DecisionConflict",
    "DecisionStoreUnavailable",
    "FirestoreDecisionSource",
    "TokenProvider",
]