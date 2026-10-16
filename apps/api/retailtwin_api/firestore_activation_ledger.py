"""Firestore-backed ``MemoryActivationLedger`` (ADR 0024).

Cross-instance replacement for the in-memory activation record. The
ledger is the canonical idempotency boundary for the observer: a
duplicate event id must not start a second investigation, and a
different payload for the same event id is a conflict that the consumer
treats as a non-terminal outcome.

Storage is one document per event id under
``/activation_records/{event_id}``. The document carries:

- ``event_id`` (``stringValue``).
- ``investigation_id`` (``stringValue``).
- ``status`` (``stringValue``) — ``pending`` or ``started``.
- ``event_json`` (``stringValue``) — JSON-encoded ``StoreEvent`` so a
  duplicate-payload check is round-trippable across instances.

Writes are best-effort within the observer's reservation flow: a write
failure raises ``ActivationLedgerUnavailable`` and the observer leaves the
Pub/Sub message unacked for the next delivery. A successful write
advances the reservation to ``pending`` (or ``started`` for commit); a
duplicate write is detected on read.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Literal

from retailtwin_api.agents.observer.consumer import (
    Activation,
    MemoryActivationLedger,
)
from retailtwin_api.firestore_decisions import _ApplicationDefaultTokenProvider
from retailtwin_api.firestore_twin import (
    ALLOWED_PROJECT,
    HttpTransport,
    TwinUnavailable,
    UrllibTransport,
)
from retailtwin_api.schemas import StoreEvent

log = logging.getLogger(__name__)

COLLECTION_ACTIVATIONS = "activation_records"


class ActivationLedgerUnavailable(RuntimeError):
    """Firestore activation storage is unreachable or rejected the write."""


class _CreateConflict(Exception):
    """Internal-only signal that an atomic create lost the precondition.

    The public ``reserve`` flow catches this, re-reads, and classifies
    the outcome as ``duplicate`` or ``conflict`` based on the existing
    record. The exception never escapes to callers.
    """


def _is_precondition_conflict(status: int, body: str) -> bool:
    """Return True when the Firestore response indicates a precondition loss.

    HTTP 409 is the canonical precondition-failure status; 400 with a
    FAILED_PRECONDITION / ALREADY_EXISTS error payload is also a loss.
    """
    if status == 409:
        return True
    if status != 400:
        return False
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return False
    if not isinstance(payload, dict):
        return False
    error = payload.get("error")
    if not isinstance(error, dict):
        return False
    status_typed = error.get("status")
    message = error.get("message")
    if status_typed in {"FAILED_PRECONDITION", "ALREADY_EXISTS"}:
        return True
    if isinstance(message, str) and (
        "precondition" in message.lower() or "already exists" in message.lower()
    ):
        return True
    return False


def _activation_doc(
    event_id: str,
    activation: Activation,
    *,
    doc_name: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "fields": {
            "event_id": {"stringValue": event_id},
            "investigation_id": {"stringValue": activation.investigation_id},
            "status": {"stringValue": activation.status},
            "event_json": {"stringValue": activation.event.model_dump_json()},
        }
    }
    if doc_name is not None:
        payload["name"] = doc_name
    return payload


def _doc_name(project: str, event_id: str) -> str:
    return (
        f"projects/{project}/databases/(default)/documents"
        f"/{COLLECTION_ACTIVATIONS}/{event_id}"
    )


def _parse_activation(doc: dict[str, Any]) -> Activation | None:
    fields = doc.get("fields", {})
    if not isinstance(fields, dict):
        return None
    raw = fields.get("event_json", {})
    if not isinstance(raw, dict):
        return None
    serialized = raw.get("stringValue")
    if not isinstance(serialized, str):
        return None
    investigation_id = ""
    status_field = fields.get("status", {})
    status_typed: Literal["pending", "started"] | None = None
    if isinstance(status_field, dict):
        candidate = status_field.get("stringValue")
        if isinstance(candidate, str) and candidate in ("pending", "started"):
            status_typed = candidate  # type: ignore[assignment]
    if status_typed is None:
        return None
    id_field = fields.get("investigation_id", {})
    if isinstance(id_field, dict):
        id_candidate = id_field.get("stringValue")
        if isinstance(id_candidate, str):
            investigation_id = id_candidate
    try:
        event = StoreEvent.model_validate_json(serialized)
    except Exception as exc:  # noqa: BLE001 — invalid stored event
        log.warning(
            "firestore_activation.invalid_event error=%s", type(exc).__name__
        )
        return None
    return Activation(investigation_id, event, status_typed)


class FirestoreActivationLedger(MemoryActivationLedger):
    """Cross-instance replacement for :class:`MemoryActivationLedger`.

    Mirrors the in-memory record on every successful write so that
    ``get`` keeps working between calls on the same instance. The
    Firestore document is the canonical store.
    """

    def __init__(
        self,
        project: str = ALLOWED_PROJECT,
        transport: HttpTransport | None = None,
        token_provider: Callable[[], str] | None = None,
    ) -> None:
        super().__init__()
        self._project = project
        self._transport = transport if transport is not None else UrllibTransport()
        self._tokens = token_provider if token_provider is not None else _ApplicationDefaultTokenProvider()

    def reserve(self, event: StoreEvent) -> Any:
        """Atomically claim the event for investigation.

        Two Cloud Run instances racing the same ``event_id`` would both
        observe a 404 on the read and both PATCH the document, leaving
        them as joint owners. ``_create_atomic`` uses Firestore's
        ``currentDocument.exists=false`` precondition so the second
        instance fails the precondition, re-reads, and classifies the
        outcome as ``duplicate`` or ``conflict``.
        """
        existing = self._read(event.event_id)
        if existing is not None:
            if existing.event != event:
                return self._build_reservation("conflict", existing)
            if existing.status == "started":
                return self._build_reservation("duplicate", existing)
            return self._build_reservation("owner", existing)

        # First reservation. Atomic create with `currentDocument.exists=false`.
        investigation_id = f"inv-{event.event_id}"
        activation = Activation(investigation_id, event, "pending")
        try:
            self._create_atomic(event.event_id, activation)
        except _CreateConflict:
            # A concurrent instance won the race. Re-read and classify.
            existing = self._read(event.event_id)
            if existing is None:
                # The winning instance raced the entire reservation, then
                # aborted. Retry once; if it still fails, surface as
                # unavailable so the Pub/Sub message is re-delivered.
                self._create_atomic(event.event_id, activation)
                return self._build_reservation("owner", activation)
            if existing.event != event:
                return self._build_reservation("conflict", existing)
            if existing.status == "started":
                return self._build_reservation("duplicate", existing)
            return self._build_reservation("owner", existing)
        return self._build_reservation("owner", activation)

    def commit(self, event_id: str) -> None:
        """Atomically transition ``pending`` to ``started``.

        The ``pending → started`` transition uses a Firestore
        ``currentDocument.updateTime`` precondition so a concurrent
        commit or abort on another instance surfaces as
        ``ActivationLedgerUnavailable`` rather than corrupting state.
        """
        from retailtwin_api.agents.observer.consumer import ObservationError

        existing, update_time = self._read_with_time(event_id)
        if existing is None or existing.status != "pending":
            raise ObservationError(event_id)
        if update_time is None:
            raise ActivationLedgerUnavailable(
                f"activation_records/{event_id} has no updateTime; cannot CAS-write."
            )
        committed = Activation(
            existing.investigation_id,
            existing.event,
            "started",
        )
        self._write_atomic(event_id, committed, expected_update_time=update_time)

    def abort(self, event_id: str) -> None:
        # The in-memory adapter silently no-ops when the event is missing
        # or already started. We mirror that: a delete on the doc id with
        # a 404 is fine.
        response = self._call("DELETE", self._doc_url(event_id), None)
        if response.status not in (200, 404):
            raise ActivationLedgerUnavailable(
                f"Firestore DELETE activation_records/{event_id} returned HTTP {response.status}"
            )

    def get(self, event_id: str) -> Activation | None:
        return self._read(event_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _doc_url(self, event_id: str) -> str:
        return (
            f"https://firestore.googleapis.com/v1/projects/{self._project}"
            f"/databases/(default)/documents/{COLLECTION_ACTIVATIONS}/{event_id}"
        )

    def _database_root(self) -> str:
        return (
            f"https://firestore.googleapis.com/v1/projects/{self._project}"
            "/databases/(default)/documents"
        )

    def _read_with_time(self, event_id: str) -> tuple[Activation | None, str | None]:
        """Return ``(activation, updateTime)`` so callers can issue a CAS write.

        ``updateTime`` is None when the document is absent.
        """
        response = self._call("GET", self._doc_url(event_id), None)
        if response.status == 404:
            return None, None
        if response.status != 200:
            raise ActivationLedgerUnavailable(
                f"Firestore GET activation_records/{event_id} returned HTTP {response.status}"
            )
        try:
            payload = json.loads(response.body)
        except json.JSONDecodeError as exc:
            raise ActivationLedgerUnavailable(
                "Firestore activation response was not JSON."
            ) from exc
        if not isinstance(payload, dict):
            return None, None
        update_time = payload.get("updateTime")
        if not isinstance(update_time, str):
            update_time = None
        return _parse_activation(payload), update_time

    def _read_update_time(self, event_id: str) -> str:
        """Return the current ``updateTime`` for the document or raise."""
        _, update_time = self._read_with_time(event_id)
        if update_time is None:
            raise ActivationLedgerUnavailable(
                f"activation_records/{event_id} has no updateTime; cannot CAS-write."
            )
        return update_time

    def _read(self, event_id: str) -> Activation | None:
        activation, _ = self._read_with_time(event_id)
        return activation

    def _create_atomic(self, event_id: str, activation: Activation) -> None:
        """Create-or-fail with ``currentDocument.exists=false``.

        Uses a Firestore ``:commit`` request so the precondition runs on
        the server. A second instance that races the read observes
        ALREADY_EXISTS / FAILED_PRECONDITION, which the caller converts
        to a re-read + classification.
        """
        body = {
            "writes": [
                {
                    "update": _activation_doc(
                        event_id, activation, doc_name=_doc_name(self._project, event_id)
                    ),
                    "currentDocument": {"exists": False},
                }
            ]
        }
        response = self._call("POST", f"{self._database_root()}:commit", body)
        if response.status == 200:
            with self._lock:
                self._records[event_id] = Activation(
                    activation.investigation_id,
                    activation.event.model_copy(deep=True),
                    activation.status,
                )
            return
        if _is_precondition_conflict(response.status, response.body):
            raise _CreateConflict(
                f"activation_records/{event_id} already exists (race)"
            )
        raise ActivationLedgerUnavailable(
            f"Firestore atomic create activation_records/{event_id} "
            f"returned HTTP {response.status}: {response.body[:200]}"
        )

    def _write_atomic(
        self,
        event_id: str,
        activation: Activation,
        *,
        expected_update_time: str,
    ) -> None:
        """CAS-write using ``currentDocument.updateTime``."""
        body = {
            "writes": [
                {
                    "update": _activation_doc(
                        event_id, activation, doc_name=_doc_name(self._project, event_id)
                    ),
                    "currentDocument": {"updateTime": expected_update_time},
                }
            ]
        }
        response = self._call("POST", f"{self._database_root()}:commit", body)
        if response.status == 200:
            with self._lock:
                self._records[event_id] = Activation(
                    activation.investigation_id,
                    activation.event.model_copy(deep=True),
                    activation.status,
                )
            return
        if _is_precondition_conflict(response.status, response.body):
            raise ActivationLedgerUnavailable(
                f"Firestore CAS write activation_records/{event_id} "
                f"lost the precondition (updateTime changed concurrently)"
            )
        raise ActivationLedgerUnavailable(
            f"Firestore CAS write activation_records/{event_id} "
            f"returned HTTP {response.status}: {response.body[:200]}"
        )

    def _write(self, event_id: str, activation: Activation) -> None:
        body = _activation_doc(event_id, activation)
        response = self._call("PATCH", self._doc_url(event_id), body)
        if response.status not in (200, 201):
            raise ActivationLedgerUnavailable(
                f"Firestore PATCH activation_records/{event_id} returned HTTP {response.status}"
            )
        # Mirror in the in-memory cache so ``get`` works between calls on
        # the same instance.
        with self._lock:
            stored = Activation(
                activation.investigation_id,
                activation.event.model_copy(deep=True),
                activation.status,
            )
            self._records[event_id] = stored

    def _call(self, method: str, url: str, payload: dict[str, Any] | None):
        body_bytes = None if payload is None else json.dumps(payload).encode("utf-8")
        try:
            token = self._tokens()
        except ActivationLedgerUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 — surface any token failure
            raise ActivationLedgerUnavailable(
                f"Activation-ledger access token unavailable: {type(exc).__name__}"
            ) from exc
        if not token or any(c in token for c in "\n\r\t "):
            raise ActivationLedgerUnavailable("Activation-ledger access token is malformed.")
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        try:
            return self._transport.request(method, url, body_bytes, headers)
        except TwinUnavailable:
            raise ActivationLedgerUnavailable(
                "Firestore activation ledger is unreachable."
            ) from None
        except Exception as exc:  # noqa: BLE001 — surface any transport failure
            raise ActivationLedgerUnavailable(
                f"Firestore activation ledger transport failed: {exc}"
            ) from exc

    @staticmethod
    def _build_reservation(kind: str, activation: Activation) -> Any:
        # Importing here avoids a circular import; the consumer module owns
        # the ``_Reservation`` dataclass.
        from retailtwin_api.agents.observer.consumer import _Reservation

        kind_typed: Literal["owner", "duplicate", "conflict"]
        if kind == "owner":
            kind_typed = "owner"
        elif kind == "duplicate":
            kind_typed = "duplicate"
        else:
            kind_typed = "conflict"
        return _Reservation(
            kind_typed,
            activation.investigation_id,
            activation.event.model_copy(deep=True),
        )


__all__ = [
    "ActivationLedgerUnavailable",
    "COLLECTION_ACTIVATIONS",
    "FirestoreActivationLedger",
]