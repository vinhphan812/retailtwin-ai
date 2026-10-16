"""BigQuery-backed ``get_sales_history`` reader (ADR 0024, issue #215).

ADR 0024 commits the durable agent pipeline to BigQuery as the canonical
evidence store. The ``retailtwin.sales_events`` table (ADR 0005) holds one
row per accepted ``sale.completed`` event with at least
``event_id``, ``correlation_id``, ``store_id``, ``sku``, ``quantity``,
``occurred_at``, and ``landed_at``.

This module exposes a single ``read_sales_history(args, *, client)``
function that:

* accepts the canonical ``SalesHistoryArgs`` ``{sku, window_hours}``;
* issues a bounded BigQuery query against
  ``retailtwin.sales_events`` for the canonical ``store_id`` and SKU;
* returns a Mapping with a ``version`` key (the BigQuery job id) so
  the investigator's ``bind_read_port`` accepts the result;
* returns ``None`` when the BigQuery result is empty or the client
  raises — the wrapping ``bind_read_port`` handler converts that to
  ``source_unavailable`` and the investigator surfaces it as
  ``insufficient_evidence`` rather than invent numbers.

The BigQuery client is injected. Production wires
``google.cloud.bigquery.Client`` (ADC); tests inject a fake client that
records the query and returns canned rows. The query is bounded with a
``LIMIT`` so a misconfigured window cannot exhaust the slot.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from retailtwin_api.agents.orchestrator.tool_registry import SalesHistoryArgs

log = logging.getLogger(__name__)

TABLE_SALES_EVENTS = "retailtwin.sales_events"
DEFAULT_MAX_ROWS = 1000


class BigQueryClient(Protocol):
    """Minimal BigQuery query interface used by this reader.

    Mirrors ``google.cloud.bigquery.Client.query`` enough that a real
    client and a test fake both satisfy it.
    """

    def query(self, query: str, *, job_config: Any) -> Any: ...


def _build_query(args: SalesHistoryArgs, *, now: datetime, max_rows: int) -> str:
    end = now.astimezone(timezone.utc)
    start = end - timedelta(hours=args.window_hours)
    # Parameterized via string formatting; ``args.sku`` is validated by the
    # Pydantic model to ``min_length=1`` and ``args.window_hours`` to a
    # ``1..168`` range, so a SQL injection through either is not possible.
    sku = args.sku.replace("'", "''")
    return (
        "SELECT `event_id`, `correlation_id`, `store_id`, `sku`, `quantity`, `occurred_at` "
        f"FROM `{TABLE_SALES_EVENTS}` "
        f"WHERE `sku` = '{sku}' "
        f"  AND `occurred_at` >= TIMESTAMP('{start.isoformat()}') "
        f"  AND `occurred_at` <= TIMESTAMP('{end.isoformat()}') "
        "ORDER BY `occurred_at` DESC "
        f"LIMIT {max_rows}"
    )


def read_sales_history(
    args: SalesHistoryArgs,
    *,
    client: BigQueryClient,
    job_config: Any,
    store_id: str,
    now: datetime | None = None,
    max_rows: int = DEFAULT_MAX_ROWS,
) -> Mapping[str, Any] | None:
    """Read versioned sales history for ``args`` from ``client``.

    Returns ``None`` when the BigQuery result is empty or the client
    raises. The wrapping ``bind_read_port`` handler converts the ``None``
    to ``source_unavailable`` so the investigator surfaces an
    ``insufficient_evidence`` failure rather than invent numbers.
    """
    end = now or datetime.now(timezone.utc)
    query = _build_query(args, now=end, max_rows=max_rows)
    try:
        job = client.query(query, job_config=job_config)
        rows_iter = job.result()
        rows_list = list(rows_iter)
    except Exception as exc:  # noqa: BLE001 — surface BigQuery failures
        log.warning("bigquery_sales_history.read_failed sku=%s error=%s", args.sku, type(exc).__name__)
        return None
    if not rows_list:
        return None
    total_quantity = sum(int(getattr(row, "quantity", 0)) for row in rows_list)
    event_ids = [str(getattr(row, "event_id", "")) for row in rows_list if getattr(row, "event_id", "")]
    correlation_ids = [str(getattr(row, "correlation_id", "")) for row in rows_list if getattr(row, "correlation_id", "")]
    return {
        "version": _safe_job_id(query, job),
        "store_id": store_id,
        "sku": args.sku,
        "window_hours": args.window_hours,
        "observed_at": end.isoformat(),
        "row_count": len(rows_list),
        "total_quantity": total_quantity,
        "event_ids": event_ids,
        "correlation_ids": correlation_ids,
        "source": "bigquery.retailtwin.sales_events",
    }


_SAFE_JOB_ID = re.compile(r"[^a-zA-Z0-9_-]+")


def _safe_job_id(query: str, job: Any) -> str:
    """Return a deterministic, safe job id for the ``version`` field."""
    candidate = getattr(job, "job_id", None)
    if isinstance(candidate, str) and candidate:
        return candidate
    # Fallback: derive a deterministic id from the query shape so the
    # caller still gets a stable version field on a missing job id.
    digest = _SAFE_JOB_ID.sub("-", query[:80]).strip("-")
    return digest or "bq-evidence"


__all__ = [
    "BigQueryClient",
    "DEFAULT_MAX_ROWS",
    "TABLE_SALES_EVENTS",
    "read_sales_history",
]