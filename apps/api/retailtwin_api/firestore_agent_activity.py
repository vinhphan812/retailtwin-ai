"""Firestore-backed ``AgentActivityLog`` (ADR 0024).

Stores one ``AgentActivityEntry`` per document under
``/agent_activity/{entry_id}``. Document fields:

- ``entry_id`` (``stringValue``) — the canonical Activity id.
- ``ts`` (``timestampValue``) — the event timestamp.
- ``stage`` (``stringValue``) — ``ControlStage`` enum value.
- ``status`` (``stringValue``) — ``started`` / ``completed`` / ``failed`` / etc.
- ``correlation_id`` (``stringValue``).
- ``run_id`` / ``decision`` / ``simulation_id`` / ``focus`` / ``summary``
  (``stringValue`` or absent when null).
- ``entry_json`` (``stringValue``) — full JSON-encoded
  ``AgentActivityEntry`` payload so a future schema bump is non-breaking.

Pagination: Uses Firestore's native cursor-based pagination with ``limit`` and
``startAfter``. The cursor encodes the last entry's ``(ts, entry_id)`` tuple
as base64, allowing efficient server-side pagination without loading all
documents. The collection is bounded by the canonical investigation id
(``inv-<event_id>``); in steady state the working set is the events
written by the current generation.

No model reasoning, prompts, or credentials are stored. Only the
canonical ``AgentActivityEntry`` Pydantic model.
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable

from retailtwin_api.agent_activity import AgentActivityLog
from retailtwin_api.contracts import ControlStage
from retailtwin_api.firestore_decisions import _ApplicationDefaultTokenProvider
from retailtwin_api.firestore_twin import (
    ALLOWED_PROJECT,
    HttpTransport,
    TwinUnavailable,
    UrllibTransport,
)
from retailtwin_api.simulation_schemas import AgentActivityEntry, CursorParameters

log = logging.getLogger(__name__)

COLLECTION_ACTIVITY = "agent_activity"
COUNT_DOC_ID = "__count__"


class AgentActivityStoreUnavailable(RuntimeError):
    """Firestore agent activity storage is unreachable or rejected the write."""


def _entry_doc(entry: AgentActivityEntry) -> dict[str, Any]:
    """Build the Firestore document body for one activity entry."""
    fields: dict[str, Any] = {
        "entry_id": {"stringValue": entry.id},
        "ts": {"timestampValue": entry.ts.isoformat()},
        "stage": {"stringValue": entry.stage.value},
        "status": {"stringValue": entry.status},
        "correlation_id": {"stringValue": entry.correlation_id},
        "entry_json": {"stringValue": entry.model_dump_json()},
    }
    for key, value in (
        ("run_id", entry.run_id),
        ("decision", entry.decision),
        ("simulation_id", entry.simulation_id),
        ("focus", entry.focus),
        ("summary", entry.summary),
    ):
        if value is not None:
            fields[key] = {"stringValue": value}
    return {"fields": fields}


def _parse_entry(doc: dict[str, Any]) -> AgentActivityEntry | None:
    fields = doc.get("fields", {})
    if not isinstance(fields, dict):
        return None
    raw = fields.get("entry_json", {})
    if not isinstance(raw, dict):
        return None
    serialized = raw.get("stringValue")
    if not isinstance(serialized, str):
        return None
    try:
        return AgentActivityEntry.model_validate_json(serialized)
    except Exception as exc:  # noqa: BLE001 — invalid stored entry
        log.warning(
            "firestore_agent_activity.invalid_entry error=%s",
            type(exc).__name__,
        )
        return None


class FirestoreAgentActivityLog(AgentActivityLog):
    """Cross-instance ``AgentActivityLog`` backed by Firestore.

    Behaves like the in-memory adapter for read paths (``page``,
    ``for_correlation``) and writes every entry as a new document. The
    counter document makes ``page`` cheap without forcing a Firestore
    compound query.
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
        self._cached_count: int | None = None

    # The in-memory base class owns ``record``. We replace it here so writes
    # go to Firestore; the inherited ``for_correlation`` works against the
    # local cache that ``page`` populates.
    def record(
        self,
        stage: ControlStage,
        status: str,
        correlation_id: str,
        *,
        run_id: str | None = None,
        decision: str | None = None,
        simulation_id: str | None = None,
        sku: str | None = None,
        shelf_id: str | None = None,
        slot_id: str | None = None,
        summary: str | None = None,
        at: datetime | None = None,
        acquired_at: datetime | None = None,
        verdict: str | None = None,
    ) -> AgentActivityEntry:
        ts = at or datetime.now(timezone.utc)
        entry = AgentActivityEntry(
            id=f"act-{self._new_id()}",
            ts=ts,
            stage=stage,
            status=status,
            correlation_id=correlation_id,
            run_id=run_id,
            decision=decision,
            simulation_id=simulation_id,
            sku=sku,
            shelf_id=shelf_id,
            slot_id=slot_id,
            focus=sku,
            summary=summary,
            acquired_at=acquired_at or ts,
            verdict=verdict,
        )
        body = _entry_doc(entry)
        response = self._call(
            "PATCH", self._doc_url(entry.id), body
        )
        if response.status not in (200, 201):
            raise AgentActivityStoreUnavailable(
                f"Firestore PATCH agent_activity/{entry.id} returned HTTP {response.status}"
            )
        # Bump the counter. Best-effort; a stale count does not affect the
        # canonical append-only history.
        self._bump_count(entry.id)
        # Mirror the entry in the local cache so ``for_correlation`` works
        # for reads on the same instance.
        with self._lock:
            self._entries.append(entry.model_copy(deep=True))
        return entry.model_copy(deep=True)

    def page(self, cursor: CursorParameters) -> tuple[list[AgentActivityEntry], str | None]:
        """Page through activity entries using server-side cursor pagination.

        Uses Firestore's structured query with startAfter for efficient
        server-side pagination. Cursors are base64-encoded JSON containing
        the (ts, entry_id) of the last seen entry.
        """
        # Build structured query body for server-side pagination
        query_body: dict[str, Any] = {
            "structuredQuery": {
                "from": [{"collectionId": COLLECTION_ACTIVITY}],
                "orderBy": [
                    {"field": {"fieldPath": "ts"}, "direction": "ASCENDING"},
                    {"field": {"fieldPath": "entry_id"}, "direction": "ASCENDING"},
                ],
                "limit": cursor.limit,
            }
        }

        # Decode cursor if provided
        if cursor.since:
            try:
                cursor_data = json.loads(base64.b64decode(cursor.since).decode())
                # Use startAt for cursor-based pagination
                query_body["structuredQuery"]["startAt"] = {
                    "values": [
                        {"timestampValue": cursor_data["ts"]},
                        {"stringValue": cursor_data["entry_id"]},
                    ],
                    "before": False,  # startAfter (exclusive)
                }
            except (ValueError, KeyError, json.JSONDecodeError) as exc:
                raise ValueError(
                    f"Invalid cursor value {cursor.since!r}: must be base64-encoded JSON with ts and entry_id."
                ) from exc

        # Execute structured query via POST to runQuery
        url = (
            f"https://firestore.googleapis.com/v1/projects/{self._project}"
            f"/databases/(default)/documents:runQuery"
        )

        body_bytes = json.dumps(query_body).encode("utf-8")
        headers = {"Content-Type": "application/json"}

        # Add auth header
        try:
            token = self._tokens()
            headers["Authorization"] = f"Bearer {token}"
        except Exception as exc:
            raise AgentActivityStoreUnavailable(
                f"Agent-activity access token unavailable: {type(exc).__name__}"
            ) from exc

        try:
            response = self._transport.request("POST", url, body_bytes, headers)
        except TwinUnavailable:
            raise AgentActivityStoreUnavailable(
                "Firestore agent activity store is unreachable."
            ) from None
        except Exception as exc:
            raise AgentActivityStoreUnavailable(
                f"Firestore agent activity store transport failed: {exc}"
            ) from exc

        if response.status != 200:
            raise AgentActivityStoreUnavailable(
                f"Firestore runQuery agent_activity returned HTTP {response.status}"
            )

        try:
            payload = json.loads(response.body)
        except json.JSONDecodeError as exc:
            raise AgentActivityStoreUnavailable(
                "Firestore runQuery response was not JSON."
            ) from exc

        # Parse results - each result is a document
        documents = payload if isinstance(payload, list) else []
        entries: list[AgentActivityEntry] = []
        last_entry = None

        for result in documents:
            if not isinstance(result, dict):
                continue
            doc = result.get("document")
            if doc is None:
                continue
            parsed = _parse_entry(doc)
            if parsed is not None:
                entries.append(parsed)
                last_entry = parsed

        # Build next cursor from last entry
        next_cursor = None
        if last_entry is not None and len(entries) == cursor.limit:
            cursor_data = {
                "ts": last_entry.ts.isoformat(),
                "entry_id": last_entry.id,
            }
            next_cursor = base64.b64encode(json.dumps(cursor_data).encode()).decode()

        # Replace local cache with the freshly-fetched list
        with self._lock:
            self._entries = entries
        return [item.model_copy(deep=True) for item in entries], next_cursor

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _doc_url(self, entry_id: str) -> str:
        return (
            f"https://firestore.googleapis.com/v1/projects/{self._project}"
            f"/databases/(default)/documents/{COLLECTION_ACTIVITY}/{entry_id}"
        )

    def _collection_url(self) -> str:
        return (
            f"https://firestore.googleapis.com/v1/projects/{self._project}"
            f"/databases/(default)/documents/{COLLECTION_ACTIVITY}"
        )

    def _call(self, method: str, url: str, payload: dict[str, Any] | None):
        body_bytes = None if payload is None else json.dumps(payload).encode("utf-8")
        try:
            token = self._tokens()
        except AgentActivityStoreUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 — surface any token failure
            raise AgentActivityStoreUnavailable(
                f"Agent-activity access token unavailable: {type(exc).__name__}"
            ) from exc
        if not token or any(c in token for c in "\n\r\t "):
            raise AgentActivityStoreUnavailable("Agent-activity access token is malformed.")
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        try:
            return self._transport.request(method, url, body_bytes, headers)
        except TwinUnavailable:
            raise AgentActivityStoreUnavailable(
                "Firestore agent activity store is unreachable."
            ) from None
        except Exception as exc:  # noqa: BLE001 — surface any transport failure
            raise AgentActivityStoreUnavailable(
                f"Firestore agent activity store transport failed: {exc}"
            ) from exc

    def _new_id(self) -> str:
        import uuid

        return uuid.uuid4().hex[:12]

    def _bump_count(self, _entry_id: str) -> None:
        """Best-effort counter bump. Failures are logged, never raised."""
        try:
            current = self._cached_count
            body: dict[str, Any] = {"fields": {"count": {"integerValue": str((current or 0) + 1)}}}
            response = self._call("PATCH", self._doc_url(COUNT_DOC_ID), body)
            if response.status in (200, 201):
                self._cached_count = (current or 0) + 1
        except AgentActivityStoreUnavailable as exc:
            log.warning("firestore_agent_activity.count_bump_failed error=%s", exc)


__all__ = [
    "COLLECTION_ACTIVITY",
    "FirestoreAgentActivityLog",
    "AgentActivityStoreUnavailable",
]