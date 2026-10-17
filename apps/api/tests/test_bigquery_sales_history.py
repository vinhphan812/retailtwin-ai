"""Tests for the BigQuery-backed ``get_sales_history`` reader (ADR 0024).

Uses an in-memory ``FakeBigQueryClient`` that records the issued query and
returns canned rows. Covers the bounded query shape, the
empty/error → ``None`` contract, and the version field.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from retailtwin_api.agents.orchestrator.tool_registry import SalesHistoryArgs
from retailtwin_api.bigquery_sales_history import (
    DEFAULT_MAX_ROWS,
    TABLE_SALES_EVENTS,
    read_sales_history,
)


class _FakeRow(SimpleNamespace):
    """A BigQuery row with the canonical fields."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)


class FakeBigQueryClient:
    """Records every ``query`` call and returns canned rows.

    ``row_factory`` is a callable: ``(query) -> list[_FakeRow]``. ``raise_on_query``
    raises a specific exception when set.
    """

    def __init__(
        self,
        *,
        row_factory: Any = None,
        raise_on_query: type[BaseException] | None = None,
    ) -> None:
        self.calls: list[str] = []
        self._row_factory = row_factory
        self._raise_on_query = raise_on_query

    def query(self, query: str, *, job_config: Any) -> Any:
        self.calls.append(query)
        if self._raise_on_query is not None:
            raise self._raise_on_query("bq-error")
        rows = self._row_factory(query) if self._row_factory else []
        job_id = "bq-job-test"

        class _Job:
            def result(self_inner: Any) -> Any:
                return iter(rows)

        return SimpleNamespace(job_id=job_id, result=_Job().result)


def _args(sku: str = "P017", window_hours: int = 4) -> SalesHistoryArgs:
    return SalesHistoryArgs(sku=sku, window_hours=window_hours)


def _now() -> datetime:
    return datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)


class TestReadSalesHistoryShape:
    def test_query_targets_canonical_table(self) -> None:
        client = FakeBigQueryClient(row_factory=lambda q: [])
        read_sales_history(
            _args(), client=client, job_config=None, store_id="store-001", now=_now()
        )
        assert TABLE_SALES_EVENTS in client.calls[0]
        assert "P017" in client.calls[0]

    def test_query_binds_window(self) -> None:
        client = FakeBigQueryClient(row_factory=lambda q: [])
        read_sales_history(
            _args(window_hours=24), client=client, job_config=None, store_id="store-001", now=_now()
        )
        assert "TIMESTAMP(" in client.calls[0]
        assert "AND " in client.calls[0]
        assert "ORDER BY" in client.calls[0]

    def test_query_is_bounded_with_limit(self) -> None:
        client = FakeBigQueryClient(row_factory=lambda q: [])
        read_sales_history(
            _args(),
            client=client,
            job_config=None,
            store_id="store-001",
            now=_now(),
            max_rows=DEFAULT_MAX_ROWS,
        )
        assert f"LIMIT {DEFAULT_MAX_ROWS}" in client.calls[0]


class TestReadSalesHistoryReturn:
    def test_returns_versioned_mapping_when_rows_present(self) -> None:
        rows = [
            _FakeRow(event_id=f"evt-{i}", correlation_id=f"corr-{i}", sku="P017", quantity=3, occurred_at=_now())
            for i in range(13)
        ]
        client = FakeBigQueryClient(row_factory=lambda q: rows)
        result = read_sales_history(
            _args(), client=client, job_config=None, store_id="store-001", now=_now()
        )
        assert result is not None
        assert result["version"] == "bq-job-test"
        assert result["row_count"] == 13
        assert result["total_quantity"] == 39
        assert result["sku"] == "P017"
        assert result["window_hours"] == 4

    def test_returns_none_when_no_rows(self) -> None:
        client = FakeBigQueryClient(row_factory=lambda q: [])
        assert read_sales_history(
            _args(), client=client, job_config=None, store_id="store-001", now=_now()
        ) is None

    def test_returns_none_on_client_error(self) -> None:
        client = FakeBigQueryClient(raise_on_query=RuntimeError)
        assert read_sales_history(
            _args(), client=client, job_config=None, store_id="store-001", now=_now()
        ) is None


class TestReadSalesHistoryP017Canonical:
    """The canonical weekend-surge fixture used by issue #30 / #32 / #33.

    Verifies the reader returns the versioned payload that downstream
    code consumes when investigating the P017 surge scenario.
    """

    def test_p017_saturday_surge_total_matches_canonical_numbers(self) -> None:
        saturday_rows = [
            _FakeRow(
                event_id=f"evt-saturday-{i}",
                correlation_id="run-weekend-demand-surge-1",
                sku="P017",
                quantity=4,
                occurred_at=_now(),
            )
            for i in range(20)
        ]
        client = FakeBigQueryClient(row_factory=lambda q: saturday_rows)
        result = read_sales_history(
            _args(window_hours=4),
            client=client,
            job_config=None,
            store_id="store-001",
            now=_now(),
        )
        assert result is not None
        # 20 rows × 4 units = 80 units sold in the canonical 4h window.
        assert result["total_quantity"] == 80
        assert result["row_count"] == 20
        assert result["correlation_ids"] == ["run-weekend-demand-surge-1"] * 20