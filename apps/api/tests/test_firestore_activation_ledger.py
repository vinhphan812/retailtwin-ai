"""Tests for the Firestore-backed ``MemoryActivationLedger`` (ADR 0024).

Same hand-rolled ``FakeHttpTransport`` pattern as the other Firestore
adapter tests. Covers reserve (owner/duplicate/conflict), commit,
abort, get, and the typed failure on transport errors.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

import pytest

from retailtwin_api.agents.observer.consumer import (
    Activation,
    MemoryActivationLedger,
    ObservationError,
)
from retailtwin_api.firestore_activation_ledger import (
    COLLECTION_ACTIVATIONS,
    ActivationLedgerUnavailable,
    FirestoreActivationLedger,
)
from retailtwin_api.firestore_twin import HttpResponse
from retailtwin_api.schemas import StoreEvent


class FakeHttpTransport:
    """Records calls and stores documents by event id.

    Mirrors Firestore's REST contract for the activation ledger: GET,
    DELETE, and the atomic ``:commit`` endpoint used by the durable
    pipeline. The fake evaluates ``currentDocument.exists`` /
    ``currentDocument.updateTime`` preconditions on the server side.
    """

    def __init__(self) -> None:
        self._docs: dict[str, dict[str, Any]] = {}
        self._versions: dict[str, int] = {}
        self.calls: list[tuple[str, str, bytes | None]] = []

    def request(
        self,
        method: str,
        url: str,
        payload: bytes | None,
        headers: Mapping[str, str],
    ) -> HttpResponse:
        self.calls.append((method, url, payload))
        if method == "GET" and "/documents/" in url:
            for event_id, doc in self._docs.items():
                if event_id in url:
                    return HttpResponse(
                        200,
                        json.dumps({**doc, "updateTime": f"v{self._versions[event_id]}"}),
                    )
            return HttpResponse(
                404, json.dumps({"error": {"status": "NOT_FOUND"}})
            )
        if method == "DELETE" and "/documents/" in url:
            for event_id in list(self._docs.keys()):
                if event_id in url:
                    del self._docs[event_id]
                    self._versions.pop(event_id, None)
                    return HttpResponse(200, json.dumps({"writeResults": [{"delete": {}}]}))
            return HttpResponse(
                404, json.dumps({"error": {"status": "NOT_FOUND"}})
            )
        if method == "POST" and url.endswith(":commit"):
            return self._commit(payload)
        if method == "PATCH" and "/documents/" in url:
            if payload is None:
                return HttpResponse(
                    400, json.dumps({"error": {"status": "INVALID_ARGUMENT"}})
                )
            decoded = json.loads(payload.decode())
            event_id = url.rsplit("/", 1)[-1]
            existing = self._docs.get(event_id, {})
            merged = {**existing, **decoded}
            self._docs[event_id] = merged
            self._versions[event_id] = self._versions.get(event_id, 0) + 1
            return HttpResponse(200, json.dumps(merged))
        return HttpResponse(200, json.dumps({}))

    def _commit(self, payload: bytes | None) -> HttpResponse:
        body = json.loads((payload or b"{}").decode())
        writes = body.get("writes") or []
        if not isinstance(writes, list) or len(writes) != 1:
            return HttpResponse(
                400, json.dumps({"error": {"status": "INVALID_ARGUMENT"}})
            )
        write = writes[0]
        if "update" not in write:
            return HttpResponse(
                400, json.dumps({"error": {"status": "INVALID_ARGUMENT"}})
            )
        update = write["update"]
        doc_name = update.get("name", "") if isinstance(update, dict) else ""
        event_id = doc_name.rsplit("/", 1)[-1]
        existing = self._docs.get(event_id)
        precondition = write.get("currentDocument", {})
        if isinstance(precondition, dict):
            if "exists" in precondition:
                if precondition.get("exists") is False and existing is not None:
                    return HttpResponse(
                        409,
                        json.dumps({
                            "error": {
                                "status": "ALREADY_EXISTS",
                                "message": "Document already exists",
                            }
                        }),
                    )
                if precondition.get("exists") is True and existing is None:
                    return HttpResponse(
                        409,
                        json.dumps({
                            "error": {
                                "status": "NOT_FOUND",
                                "message": "Document does not exist",
                            }
                        }),
                    )
            if "updateTime" in precondition:
                expected = precondition.get("updateTime")
                if existing is None:
                    return HttpResponse(
                        409,
                        json.dumps({
                            "error": {
                                "status": "FAILED_PRECONDITION",
                                "message": f"Document updateTime mismatch (expected {expected})",
                            }
                        }),
                    )
                current_version = self._versions.get(event_id, 0)
                actual = f"v{current_version}"
                if expected != actual:
                    return HttpResponse(
                        409,
                        json.dumps({
                            "error": {
                                "status": "FAILED_PRECONDITION",
                                "message": f"Document updateTime mismatch (expected {expected}, actual {actual})",
                            }
                        }),
                    )
        # Apply the write.
        self._docs[event_id] = update
        self._versions[event_id] = self._versions.get(event_id, 0) + 1
        return HttpResponse(
            200,
            json.dumps({
                "writeResults": [{
                    "updateTime": f"v{self._versions[event_id]}",
                }]
            }),
        )


class _FakeToken:
    def __call__(self) -> str:
        return "fake-token"


def _event(event_id: str = "evt-1") -> StoreEvent:
    return StoreEvent(
        event_id=event_id,
        correlation_id=f"corr-{event_id}",
        event_type="sale.completed",
        store_id="store-001",
        sku="P001",
        quantity=1,
        occurred_at=datetime(2026, 10, 16, 12, 0, 0, tzinfo=timezone.utc),
        source="synthetic-pos",
    )


class TestFirestoreActivationLedgerReserve:
    def test_first_reserve_is_owner(self) -> None:
        ledger = FirestoreActivationLedger(
            transport=FakeHttpTransport(), token_provider=_FakeToken()
        )
        reservation = ledger.reserve(_event("evt-1"))
        assert reservation.kind == "owner"
        assert reservation.investigation_id == "inv-evt-1"

    def test_second_reserve_with_same_event_is_duplicate(self) -> None:
        ledger = FirestoreActivationLedger(
            transport=FakeHttpTransport(), token_provider=_FakeToken()
        )
        event = _event("evt-1")
        first = ledger.reserve(event)
        assert first.kind == "owner"

        ledger.commit("evt-1")  # advance status to "started"
        second = ledger.reserve(event)
        assert second.kind == "duplicate"

    def test_reserve_with_different_payload_is_conflict(self) -> None:
        ledger = FirestoreActivationLedger(
            transport=FakeHttpTransport(), token_provider=_FakeToken()
        )
        ledger.reserve(_event("evt-1"))

        different = StoreEvent(
            event_id="evt-1",
            correlation_id="corr-evt-1",
            event_type="sale.completed",
            store_id="store-002",  # different store
            sku="P001",
            quantity=1,
            occurred_at=datetime(2026, 10, 16, 12, 0, 0, tzinfo=timezone.utc),
            source="synthetic-pos",
        )
        reservation = ledger.reserve(different)
        assert reservation.kind == "conflict"


class TestFirestoreActivationLedgerCommit:
    def test_commit_advances_status_to_started(self) -> None:
        ledger = FirestoreActivationLedger(
            transport=FakeHttpTransport(), token_provider=_FakeToken()
        )
        ledger.reserve(_event("evt-1"))
        ledger.commit("evt-1")
        activated = ledger.get("evt-1")
        assert activated is not None
        assert activated.status == "started"

    def test_commit_raises_observation_error_when_no_reservation(self) -> None:
        ledger = FirestoreActivationLedger(
            transport=FakeHttpTransport(), token_provider=_FakeToken()
        )
        with pytest.raises(ObservationError):
            ledger.commit("evt-missing")


class TestFirestoreActivationLedgerAbort:
    def test_abort_removes_reservation(self) -> None:
        ledger = FirestoreActivationLedger(
            transport=FakeHttpTransport(), token_provider=_FakeToken()
        )
        ledger.reserve(_event("evt-1"))
        ledger.abort("evt-1")
        assert ledger.get("evt-1") is None

    def test_abort_on_missing_event_id_is_noop(self) -> None:
        ledger = FirestoreActivationLedger(
            transport=FakeHttpTransport(), token_provider=_FakeToken()
        )
        # Should not raise even though the doc is absent.
        ledger.abort("evt-missing")


class TestFirestoreActivationLedgerFailureClosed:
    def test_reserve_raises_on_token_failure(self) -> None:
        def broken_token() -> str:
            raise RuntimeError("ADC missing")

        ledger = FirestoreActivationLedger(
            transport=FakeHttpTransport(), token_provider=broken_token
        )
        with pytest.raises(ActivationLedgerUnavailable):
            ledger.reserve(_event("evt-1"))

    def test_uses_correct_collection_path(self) -> None:
        transport = FakeHttpTransport()
        ledger = FirestoreActivationLedger(
            transport=transport, token_provider=_FakeToken()
        )
        ledger.reserve(_event("evt-path"))
        method, url, _ = transport.calls[0]
        assert f"/{COLLECTION_ACTIVATIONS}/evt-path" in url
        assert "retailtwin-ai-511002" in url


class TestFirestoreActivationLedgerAtomicReservation:
    """Lock down the cross-instance race condition reported in the
    CHANGES_REQUESTED review of PR #231. ``reserve`` must not allow two
    instances to both become owner for the same ``event_id``.
    """

    def test_reserve_uses_atomic_create_with_exists_false(self) -> None:
        transport = FakeHttpTransport()
        ledger = FirestoreActivationLedger(
            transport=transport, token_provider=_FakeToken()
        )
        ledger.reserve(_event("evt-atomic"))
        # The first call must use the POST :commit endpoint with
        # currentDocument.exists=false — not a bare PATCH.
        write_calls = [
            (method, url, payload)
            for method, url, payload in transport.calls
            if method == "POST" and url.endswith(":commit")
        ]
        assert len(write_calls) == 1, write_calls
        body = json.loads(write_calls[0][2].decode())  # type: ignore[arg-type]
        writes = body.get("writes")
        assert isinstance(writes, list) and len(writes) == 1
        write = writes[0]
        assert write.get("currentDocument") == {"exists": False}
        assert "/activation_records/evt-atomic" in write.get("update", {}).get("name", "")

    def test_concurrent_create_loses_precondition_and_reclassifies(self) -> None:
        """When the create precondition is lost, ``reserve`` must NOT
        write the document a second time. It re-reads, finds the
        existing record, and classifies as ``duplicate``.
        """
        transport = FakeHttpTransport()
        # Pre-seed an existing record so the create precondition fails.
        transport._docs["evt-2"] = {
            "fields": {
                "event_id": {"stringValue": "evt-2"},
                "investigation_id": {"stringValue": "inv-evt-2"},
                "status": {"stringValue": "started"},
                "event_json": {"stringValue": _event("evt-2").model_dump_json()},
            }
        }
        transport._versions["evt-2"] = 1
        ledger = FirestoreActivationLedger(
            transport=transport, token_provider=_FakeToken()
        )
        reservation = ledger.reserve(_event("evt-2"))
        assert reservation.kind == "duplicate"
        # The pre-seeded investigation_id is preserved; the second
        # reserve did not overwrite it.
        assert reservation.investigation_id == "inv-evt-2"

    def test_concurrent_create_with_different_payload_is_conflict(self) -> None:
        transport = FakeHttpTransport()
        transport._docs["evt-3"] = {
            "fields": {
                "event_id": {"stringValue": "evt-3"},
                "investigation_id": {"stringValue": "inv-evt-3"},
                "status": {"stringValue": "pending"},
                "event_json": {"stringValue": _event("evt-3").model_dump_json()},
            }
        }
        transport._versions["evt-3"] = 1
        ledger = FirestoreActivationLedger(
            transport=transport, token_provider=_FakeToken()
        )
        different = StoreEvent(
            event_id="evt-3",
            correlation_id="corr-evt-3",
            event_type="sale.completed",
            store_id="store-002",
            sku="P001",
            quantity=1,
            occurred_at=datetime(2026, 10, 16, 12, 0, 0, tzinfo=timezone.utc),
            source="synthetic-pos",
        )
        reservation = ledger.reserve(different)
        assert reservation.kind == "conflict"

    def test_commit_uses_update_time_precondition(self) -> None:
        transport = FakeHttpTransport()
        ledger = FirestoreActivationLedger(
            transport=transport, token_provider=_FakeToken()
        )
        ledger.reserve(_event("evt-4"))
        ledger.commit("evt-4")
        commit_calls = [
            (method, url, payload)
            for method, url, payload in transport.calls
            if method == "POST" and url.endswith(":commit")
        ]
        assert len(commit_calls) == 2, commit_calls
        body = json.loads(commit_calls[1][2].decode())  # type: ignore[arg-type]
        write = body["writes"][0]
        assert "updateTime" in write.get("currentDocument", {})
        assert write["currentDocument"]["updateTime"] == "v1"