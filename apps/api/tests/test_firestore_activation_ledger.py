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
    """Records calls and stores documents by event id."""

    def __init__(self) -> None:
        self._docs: dict[str, dict[str, Any]] = {}
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
                    return HttpResponse(200, json.dumps(doc))
            return HttpResponse(
                404, json.dumps({"error": {"status": "NOT_FOUND"}})
            )
        if method == "DELETE" and "/documents/" in url:
            for event_id in list(self._docs.keys()):
                if event_id in url:
                    del self._docs[event_id]
                    return HttpResponse(200, json.dumps({"writeResults": [{"delete": {}}]}))
            return HttpResponse(
                404, json.dumps({"error": {"status": "NOT_FOUND"}})
            )
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
            return HttpResponse(200, json.dumps(merged))
        return HttpResponse(200, json.dumps({}))


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