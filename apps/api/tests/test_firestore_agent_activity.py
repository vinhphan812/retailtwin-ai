"""Tests for the Firestore-backed ``AgentActivityLog`` (ADR 0024).

Uses the same hand-rolled ``FakeHttpTransport`` pattern as the other
Firestore adapter tests. Covers round-trip, page pagination, error
typed failure, and the local-cache mirror that ``for_correlation``
relies on.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pytest

from retailtwin_api.contracts import ControlStage
from retailtwin_api.firestore_agent_activity import (
    COLLECTION_ACTIVITY,
    AgentActivityStoreUnavailable,
    FirestoreAgentActivityLog,
)
from retailtwin_api.firestore_twin import HttpResponse
from retailtwin_api.simulation_schemas import CursorParameters


class FakeHttpTransport:
    """Records calls and stores documents by entry id."""

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
        if method == "GET" and url.endswith(COLLECTION_ACTIVITY):
            documents = list(self._docs.values())
            return HttpResponse(200, json.dumps({"documents": documents}))
        if method == "PATCH" and "/documents/" in url:
            if payload is None:
                return HttpResponse(
                    400, json.dumps({"error": {"status": "INVALID_ARGUMENT"}})
                )
            decoded = json.loads(payload.decode())
            entry_id = url.rsplit("/", 1)[-1]
            existing = self._docs.get(entry_id, {})
            merged = {**existing, **decoded}
            self._docs[entry_id] = merged
            return HttpResponse(200, json.dumps(merged))
        return HttpResponse(200, json.dumps({}))


class _FakeToken:
    def __call__(self) -> str:
        return "fake-token"


class TestFirestoreAgentActivityLogRecord:
    def test_record_persists_entry(self) -> None:
        transport = FakeHttpTransport()
        log = FirestoreAgentActivityLog(
            transport=transport, token_provider=_FakeToken()
        )

        entry = log.record(
            ControlStage.OBSERVE,
            "started",
            "corr-1",
            run_id="inv-1",
            sku="P001",
            summary="test",
        )

        assert entry.id.startswith("act-")
        assert entry.stage == ControlStage.OBSERVE
        assert entry.status == "started"
        # PATCH on the canonical URL.
        assert any(
            f"agent_activity/{entry.id}" in url for _, url, _ in transport.calls
        )

    def test_record_serializes_entry_as_string_value(self) -> None:
        transport = FakeHttpTransport()
        log = FirestoreAgentActivityLog(
            transport=transport, token_provider=_FakeToken()
        )

        entry = log.record(ControlStage.INVESTIGATE, "completed", "corr-2")

        method, url, payload = transport.calls[0]
        assert method == "PATCH"
        assert url.endswith(f"/agent_activity/{entry.id}")
        decoded = json.loads(payload.decode())
        assert decoded["fields"]["entry_id"] == {"stringValue": entry.id}
        assert decoded["fields"]["status"] == {"stringValue": "completed"}
        json_payload = decoded["fields"]["entry_json"]["stringValue"]
        from retailtwin_api.simulation_schemas import AgentActivityEntry
        re_decoded = AgentActivityEntry.model_validate_json(json_payload)
        assert re_decoded == entry

    def test_record_raises_on_unexpected_status(self) -> None:
        class _Fail(FakeHttpTransport):
            def request(self, method, url, payload, headers):
                if method == "PATCH" and "agent_activity" in url and "__count__" not in url:
                    return HttpResponse(
                        500, json.dumps({"error": {"status": "INTERNAL"}})
                    )
                return super().request(method, url, payload, headers)

        log = FirestoreAgentActivityLog(
            transport=_Fail(), token_provider=_FakeToken()
        )
        with pytest.raises(AgentActivityStoreUnavailable):
            log.record(ControlStage.OBSERVE, "started", "corr-fail")

    def test_record_raises_on_token_failure(self) -> None:
        def broken_token() -> str:
            raise RuntimeError("ADC missing")

        log = FirestoreAgentActivityLog(
            transport=FakeHttpTransport(), token_provider=broken_token
        )
        with pytest.raises(AgentActivityStoreUnavailable):
            log.record(ControlStage.OBSERVE, "started", "corr-no-token")


class TestFirestoreAgentActivityLogPage:
    def test_page_returns_recorded_entries_in_ts_order(self) -> None:
        transport = FakeHttpTransport()
        log = FirestoreAgentActivityLog(
            transport=transport, token_provider=_FakeToken()
        )
        log.record(ControlStage.OBSERVE, "started", "corr-1")
        log.record(ControlStage.INVESTIGATE, "completed", "corr-1")

        transport.calls.clear()
        entries, cursor = log.page(CursorParameters(limit=10))

        assert len(entries) == 2
        assert entries[0].stage == ControlStage.OBSERVE
        assert entries[1].stage == ControlStage.INVESTIGATE
        assert cursor is None

    def test_page_applies_offset_cursor(self) -> None:
        transport = FakeHttpTransport()
        log = FirestoreAgentActivityLog(
            transport=transport, token_provider=_FakeToken()
        )
        log.record(ControlStage.OBSERVE, "started", "corr-1")
        log.record(ControlStage.INVESTIGATE, "completed", "corr-1")
        log.record(ControlStage.PLAN, "completed", "corr-1")

        transport.calls.clear()
        entries, cursor = log.page(CursorParameters(since="1", limit=2))

        assert [entry.stage for entry in entries] == [
            ControlStage.INVESTIGATE,
            ControlStage.PLAN,
        ]
        assert cursor is None  # 3 entries, since=1, limit=2 → consumed all

    def test_page_raises_on_bad_cursor(self) -> None:
        transport = FakeHttpTransport()
        log = FirestoreAgentActivityLog(
            transport=transport, token_provider=_FakeToken()
        )
        with pytest.raises(ValueError):
            log.page(CursorParameters(since="not-a-number", limit=10))


class TestFirestoreAgentActivityLogForCorrelation:
    def test_for_correlation_filters_local_cache(self) -> None:
        transport = FakeHttpTransport()
        log = FirestoreAgentActivityLog(
            transport=transport, token_provider=_FakeToken()
        )
        log.record(ControlStage.OBSERVE, "started", "corr-1")
        log.record(ControlStage.OBSERVE, "started", "corr-2")

        entries = log.for_correlation("corr-1")
        assert len(entries) == 1
        assert entries[0].correlation_id == "corr-1"