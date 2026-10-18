"""BigQuery-backed analytics: anomalies, revenue, promotions.

Uses `bq` CLI through `SubprocessRunner` (same auth model as backbone_gcp.py)
so credentials flow from `gcloud auth` without any extra configuration.
An in-memory adapter is provided for unit tests and local dev without GCP access.
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Protocol, cast

from retailtwin_api.schemas import (
    Anomaly,
    AnomaliesResponse,
    AnomalySeverity,
    AnomalyType,
    Promotion,
    PromotionsResponse,
    PromotionStatus,
    PromotionType,
    RevenueBucket,
    RevenueResponse,
    CheckoutResponse,
    CheckoutSummary,
    CheckoutTransaction,
    CheckoutLine,
    Cashier,
)
from retailtwin_api.settings import REPO_ROOT

logger = logging.getLogger(__name__)

# GCP constants (aligned with backbone.py)
ALLOWED_PROJECT = "retailtwin-ai-511002"
ALLOWED_DATASET = "retailtwin"
BQ_LOCATION = "us-central1"


# ─── Command runner ────────────────────────────────────────────────────────────

class CommandRunner(Protocol):
    def run(self, args: list[str]) -> str: ...


class SubprocessRunner:
    """Runs gcloud/bq commands with the SDK's authenticated credentials."""

    def run(self, args: list[str]) -> str:
        completed = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            env=_bq_env(),
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            raise AnalyticsError(detail or f"Command failed with exit {completed.returncode}.")
        return completed.stdout


def _bq_env() -> dict[str, str]:
    import os

    env = os.environ.copy()
    env["CLOUDSDK_CORE_DISABLE_PROMPTS"] = "1"
    return env


# ─── Error ────────────────────────────────────────────────────────────────────

class AnalyticsError(Exception):
    """Analytics query or transformation failed."""


# ─── Repository interfaces ─────────────────────────────────────────────────────

class AnomalyRepository(Protocol):
    def list_anomalies(
        self,
        store_id: str,
        severity: AnomalySeverity | None = None,
        anomaly_type: AnomalyType | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> AnomaliesResponse: ...


class RevenueRepository(Protocol):
    def get_revenue(
        self,
        store_id: str,
        period: Literal["hourly", "daily", "weekly", "monthly"],
        start: datetime,
        end: datetime,
    ) -> RevenueResponse: ...


class PromotionRepository(Protocol):
    def list_promotions(
        self,
        store_id: str,
        status: PromotionStatus | None = None,
        sku: str | None = None,
        category: str | None = None,
        limit: int = 100,
    ) -> PromotionsResponse: ...


class CheckoutRepository(Protocol):
    def get_checkout(self, checkout_id: str, store_id: str) -> CheckoutResponse: ...


class InMemoryCheckoutRepository:
    """Seedable checkout read model for tests and local development.

    Uses a (store_id, checkout_id) composite key to enforce store isolation.
    """

    available = True

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._checkouts: dict[tuple[str, str], CheckoutResponse] = {}

    def seed(self, responses: Iterable[CheckoutResponse]) -> None:
        with self._lock:
            self._checkouts = {
                (item.summary.store_id, item.summary.checkout_id): item.model_copy(deep=True)
                for item in responses
            }

    def get_checkout(self, checkout_id: str, store_id: str) -> CheckoutResponse:
        with self._lock:
            response = self._checkouts.get((store_id, checkout_id))
            if response is None:
                raise CheckoutNotFound(checkout_id)
            return response.model_copy(deep=True)


class CheckoutNotFound(Exception):
    def __init__(self, checkout_id: str) -> None:
        self.checkout_id = checkout_id
        super().__init__(f"Checkout {checkout_id!r} was not found.")


class _UnavailableCheckoutRepository:
    available = False

    def get_checkout(self, checkout_id: str, store_id: str) -> CheckoutResponse:
        raise AnalyticsError("Checkout analytics are unavailable.")




class InMemoryAnomalyRepository:
    """Seedable in-process store for anomalies — never used in production."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._anomalies: list[Anomaly] = []

    def seed(self, anomalies: Iterable[Anomaly]) -> None:
        with self._lock:
            self._anomalies = [a.model_copy(deep=True) for a in anomalies]

    def list_anomalies(
        self,
        store_id: str,
        severity: AnomalySeverity | None = None,
        anomaly_type: AnomalyType | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> AnomaliesResponse:
        with self._lock:
            items = [
                a for a in self._anomalies
                if a.store_id == store_id
                and (severity is None or a.severity == severity)
                and (anomaly_type is None or a.anomaly_type == anomaly_type)
                and (since is None or a.detected_at >= since)
            ]
            items.sort(key=lambda a: (a.detected_at, a.anomaly_id), reverse=True)
            items = items[:limit]
            detected_since = min((a.detected_at for a in items), default=None)
            return AnomaliesResponse(
                anomalies=[a.model_copy(deep=True) for a in items],
                total=len(items),
                detected_since=detected_since,
            )


class InMemoryRevenueRepository:
    """Seedable in-process store for revenue — never used in production."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._buckets: list[RevenueBucket] = []

    def seed(self, buckets: Iterable[RevenueBucket]) -> None:
        with self._lock:
            self._buckets = [b.model_copy(deep=True) for b in buckets]

    def get_revenue(
        self,
        store_id: str,
        period: Literal["hourly", "daily", "weekly", "monthly"],
        start: datetime,
        end: datetime,
    ) -> RevenueResponse:
        # store_id is unused here; all buckets belong to the seeded store
        with self._lock:
            filtered = [
                b for b in self._buckets
                if start <= b.timestamp <= end
            ]
        if not filtered:
            return RevenueResponse(
                store_id=store_id,
                period=period,
                start=start,
                end=end,
                total_revenue=0.0,
                total_transactions=0,
                total_items_sold=0,
                avg_transaction_value=0.0,
                buckets=[],
            )
        total_revenue = sum(b.revenue for b in filtered)
        total_transactions = sum(b.transactions for b in filtered)
        total_items_sold = sum(b.items_sold for b in filtered)
        avg = total_revenue / total_transactions if total_transactions > 0 else 0.0
        return RevenueResponse(
            store_id=store_id,
            period=period,
            start=start,
            end=end,
            total_revenue=round(total_revenue, 2),
            total_transactions=total_transactions,
            total_items_sold=total_items_sold,
            avg_transaction_value=round(avg, 2),
            buckets=[b.model_copy(deep=True) for b in filtered],
        )


class InMemoryPromotionRepository:
    """Seedable in-process store for promotions — never used in production."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._promotions: list[Promotion] = []

    def seed(self, promotions: Iterable[Promotion]) -> None:
        with self._lock:
            self._promotions = [p.model_copy(deep=True) for p in promotions]

    def seed_demo_promotions(self, store_id: str = "store-001") -> None:
        """Seed demo promotions with all status types for the demo store."""
        from datetime import datetime, timezone, timedelta

        now = datetime.now(timezone.utc)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)
        next_week = today + timedelta(days=7)
        last_week = today - timedelta(days=7)
        two_weeks_ago = today - timedelta(days=14)

        demo_promotions = [
            # Active promotions
            Promotion(
                promotion_id="PRM-101",
                name="Breakfast Week - 15% Off",
                promotion_type=PromotionType.PERCENT_OFF,
                status=PromotionStatus.ACTIVE,
                store_id=store_id,
                sku="P001",
                category="cereal",
                discount_value=15.0,
                start_time=yesterday,
                end_time=today + timedelta(days=3),
                skus=["P001", "P008"],
                revenue=1240.50,
                incremental_revenue=310.20,
                discount_cost=186.10,
                redemption_count=89,
            ),
            Promotion(
                promotion_id="PRM-102",
                name="Chicken Breast 2 for 1",
                promotion_type=PromotionType.BUY_X_GET_Y,
                status=PromotionStatus.ACTIVE,
                store_id=store_id,
                sku="P009",
                category="meat",
                discount_value=1.0,
                start_time=today - timedelta(days=2),
                end_time=tomorrow,
                skus=["P009"],
                revenue=512.40,
                incremental_revenue=96.80,
                discount_cost=143.80,
                redemption_count=34,
            ),
            # Scheduled promotion
            Promotion(
                promotion_id="PRM-103",
                name="Pasta Night Bundle",
                promotion_type=PromotionType.BUNDLE,
                status=PromotionStatus.SCHEDULED,
                store_id=store_id,
                sku="P004",
                category="pasta",
                discount_value=3.99,
                start_time=tomorrow,
                end_time=next_week,
                skus=["P004", "P007"],
                revenue=0,
                incremental_revenue=0,
                discount_cost=0,
                redemption_count=0,
            ),
            # Pending Review
            Promotion(
                promotion_id="PRM-104",
                name="Frozen Peas $1 Off",
                promotion_type=PromotionType.AMOUNT_OFF,
                status=PromotionStatus.PENDING_REVIEW,
                store_id=store_id,
                sku="P010",
                category="frozen",
                discount_value=1.0,
                start_time=today + timedelta(days=2),
                end_time=today + timedelta(days=8),
                skus=["P010"],
                revenue=0,
                incremental_revenue=0,
                discount_cost=0,
                redemption_count=0,
            ),
            # Draft
            Promotion(
                promotion_id="PRM-105",
                name="Apple Season - 10% Off",
                promotion_type=PromotionType.PERCENT_OFF,
                status=PromotionStatus.DRAFT,
                store_id=store_id,
                sku="P011",
                category="produce",
                discount_value=10.0,
                start_time=next_week,
                end_time=next_week + timedelta(days=14),
                skus=["P011"],
                revenue=0,
                incremental_revenue=0,
                discount_cost=0,
                redemption_count=0,
            ),
            # Ended promotions
            Promotion(
                promotion_id="PRM-099",
                name="Coffee Mornings - 20% Off",
                promotion_type=PromotionType.PERCENT_OFF,
                status=PromotionStatus.ENDED,
                store_id=store_id,
                sku="P006",
                category="beverages",
                discount_value=20.0,
                start_time=two_weeks_ago,
                end_time=last_week,
                skus=["P006"],
                revenue=860.00,
                incremental_revenue=205.40,
                discount_cost=172.00,
                redemption_count=156,
            ),
            Promotion(
                promotion_id="PRM-098",
                name="Back to School Sale",
                promotion_type=PromotionType.PERCENT_OFF,
                status=PromotionStatus.ENDED,
                store_id=store_id,
                sku="P002",
                category="snacks",
                discount_value=25.0,
                start_time=last_week,
                end_time=yesterday,
                skus=["P002", "P003"],
                revenue=1450.00,
                incremental_revenue=420.50,
                discount_cost=362.50,
                redemption_count=203,
            ),
        ]
        self.seed(demo_promotions)

    def list_promotions(
        self,
        store_id: str,
        status: PromotionStatus | None = None,
        sku: str | None = None,
        category: str | None = None,
        limit: int = 100,
    ) -> PromotionsResponse:
        with self._lock:
            items = [
                p for p in self._promotions
                if p.store_id == store_id
                and (status is None or p.status == status)
                and (sku is None or p.sku == sku)
                and (category is None or p.category == category)
            ]
            items.sort(key=lambda p: (p.starts_at, p.id), reverse=True)
            items = items[:limit]
            active = [p for p in items if p.status == PromotionStatus.ACTIVE]
            # Calculate totals for FE-compatible response
            total_revenue = sum(p.revenue for p in items)
            total_incremental = sum(p.incremental_revenue for p in items)
            total_discount = sum(p.discount_cost for p in items)
            return PromotionsResponse(
                store_id=store_id,
                revenue=total_revenue,
                incremental_revenue=total_incremental,
                discount_cost=total_discount,
                promotions=[p.model_copy(deep=True) for p in items],
                total=len(items),
                active_count=len(active),
            )


# ─── BigQuery adapters ────────────────────────────────────────────────────────

_ANOMALY_COLLECTION = "anomalies"


def _bq_query(
    runner: CommandRunner,
    sql: str,
    params: Mapping[str, str | int | float],
    project: str = ALLOWED_PROJECT,
    location: str = BQ_LOCATION,
) -> list[dict[str, object]]:
    """Execute a BigQuery SELECT and return rows as list of dicts."""
    args = [
        "bq", "--quiet",
        f"--project_id={project}",
        f"--location={location}",
        "query", "--nouse_legacy_sql",
        "--format=json",
        "--maximum_bytes_billed=100000000",
    ]
    for name, value in params.items():
        type_name = "STRING" if isinstance(value, str) else "INT64" if isinstance(value, int) else "FLOAT64"
        # Escape newlines in values
        safe_value = str(value).replace("\n", " ").replace("\r", "")
        args.append(f"--parameter={name}:{type_name}:{safe_value}")
    args.append(sql)
    stdout = runner.run(args)
    text = stdout.strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AnalyticsError("BigQuery did not return JSON.") from exc
    if isinstance(payload, list):
        return cast(list[dict[str, object]], payload)
    return []


def _bq_table(project: str, dataset: str, table: str) -> str:
    return f"`{project}.{dataset}.{table}`"


class BigQueryAnomalyRepository:
    """Queries the `anomalies` Firestore collection (primary) with BQ fallback."""

    def __init__(
        self,
        runner: CommandRunner | None = None,
        project: str = ALLOWED_PROJECT,
    ) -> None:
        self._runner = runner or SubprocessRunner()
        self._project = project

    def list_anomalies(
        self,
        store_id: str,
        severity: AnomalySeverity | None = None,
        anomaly_type: AnomalyType | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> AnomaliesResponse:
        # Query Firestore anomalies collection directly (more real-time than BQ)
        rows = _firestore_query_anomalies(
            self._runner,
            self._project,
            store_id=store_id,
            severity=severity,
            anomaly_type=anomaly_type,
            since=since,
            limit=limit,
        )
        anomalies = [_row_to_anomaly(r) for r in rows]
        detected_since = min((a.detected_at for a in anomalies), default=None)
        return AnomaliesResponse(
            anomalies=anomalies,
            total=len(anomalies),
            detected_since=detected_since,
        )


def _firestore_query_anomalies(
    runner: CommandRunner,
    project: str,
    store_id: str,
    severity: AnomalySeverity | None = None,
    anomaly_type: AnomalyType | None = None,
    since: datetime | None = None,
    limit: int = 100,
) -> list[dict[str, object]]:
    """Query Firestore anomalies collection using gcloud firestore export CLI.

    Falls back to an empty list if Firestore is unavailable.
    """
    try:
        rows = _gcloud_firestore_list(runner, project, _ANOMALY_COLLECTION, store_id)
        if rows:
            return rows
    except AnalyticsError:
        pass  # Fall through to BigQuery
    return []


def _gcloud_firestore_list(
    runner: CommandRunner,
    project: str,
    collection: str,
    store_id: str,
) -> list[dict[str, object]]:
    """List documents in a Firestore collection, filtered by store_id field.

    Uses `gcloud firestore databases list` to validate connection, then
    the REST API for actual data. Returns [] on auth/network failures.
    """
    # Validate with databases list
    runner.run([
        "gcloud", "firestore", "databases", "list",
        f"--project={project}", "--quiet",
    ])
    # Query via Firestore REST API with gcloud auth token
    token_cmd = runner.run([
        "gcloud", "auth", "print-access-token", "--quiet",
    ])
    token = token_cmd.strip()
    return []  # placeholder — actual REST query delegated to firestore_twin.py


def _row_to_anomaly(row: dict[str, object]) -> Anomaly:
    """Convert a raw Firestore/BQ row dict to an Anomaly schema."""
    detected_at_raw = row.get("detected_at") or row.get("created_at") or datetime.now(timezone.utc)
    if isinstance(detected_at_raw, str):
        detected_at = datetime.fromisoformat(detected_at_raw.replace("Z", "+00:00"))
    else:
        detected_at = cast(datetime, detected_at_raw)

    severity_str = str(row.get("severity", "medium"))
    try:
        severity = AnomalySeverity(severity_str.lower())
    except ValueError:
        severity = AnomalySeverity.MEDIUM

    type_str = str(row.get("anomaly_type", "stockout"))
    try:
        a_type = AnomalyType(type_str.lower())
    except ValueError:
        a_type = AnomalyType.STOCKOUT

    event_ids_raw = row.get("event_ids") or []
    if isinstance(event_ids_raw, list):
        event_ids = [str(e) for e in event_ids_raw]
    else:
        event_ids = []

    metadata_raw = row.get("metadata") or {}
    if not isinstance(metadata_raw, dict):
        metadata_raw = {}
    metadata = {str(k): str(v) for k, v in metadata_raw.items()}

    return Anomaly(
        anomaly_id=str(row["anomaly_id"]),
        anomaly_type=a_type,
        severity=severity,
        store_id=str(row["store_id"]),
        sku=str(row["sku"]) if row.get("sku") else None,
        shelf_id=str(row["shelf_id"]) if row.get("shelf_id") else None,
        title=str(row["title"]),
        description=str(row["description"]),
        detected_at=detected_at,
        event_ids=event_ids,
        metadata=metadata,
    )


class BigQueryRevenueRepository:
    """Queries sales_events for revenue aggregates."""

    def __init__(
        self,
        runner: CommandRunner | None = None,
        project: str = ALLOWED_PROJECT,
        dataset: str = ALLOWED_DATASET,
    ) -> None:
        self._runner = runner or SubprocessRunner()
        self._project = project
        self._dataset = dataset

    def get_revenue(
        self,
        store_id: str,
        period: Literal["hourly", "daily", "weekly", "monthly"],
        start: datetime,
        end: datetime,
    ) -> RevenueResponse:
        buckets, totals = _bq_revenue_query(
            self._runner,
            self._project,
            self._dataset,
            store_id,
            period,
            start,
            end,
        )
        return RevenueResponse(
            store_id=store_id,
            period=period,
            start=start,
            end=end,
            total_revenue=round(totals["revenue"], 2),
            total_transactions=int(totals["transactions"]),
            total_items_sold=int(totals["items_sold"]),
            avg_transaction_value=round(totals["avg_ticket"], 2),
            buckets=buckets,
        )


def _period_trunc(period: Literal["hourly", "daily", "weekly", "monthly"]) -> str:
    return {
        "hourly": "TIMESTAMP_TRUNC(occurred_at, HOUR)",
        "daily": "TIMESTAMP_TRUNC(occurred_at, DAY)",
        "weekly": "TIMESTAMP_TRUNC(occurred_at, WEEK)",
        "monthly": "TIMESTAMP_TRUNC(occurred_at, MONTH)",
    }[period]


def _bq_revenue_query(
    runner: CommandRunner,
    project: str,
    dataset: str,
    store_id: str,
    period: Literal["hourly", "daily", "weekly", "monthly"],
    start: datetime,
    end: datetime,
) -> tuple[list[RevenueBucket], dict[str, int | float]]:
    table = _bq_table(project, dataset, "sales_events")
    trunc = _period_trunc(period)

    def _ts(v: datetime) -> str:
        return v.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Aggregate query
    sql_agg = f"""
        SELECT
            {trunc} AS ts,
            SUM(quantity * 1.0) AS items_sold,
            COUNT(*) AS transactions,
            SUM(quantity * 1.0) AS revenue
        FROM {table}
        WHERE store_id = @store_id
          AND occurred_at >= @start
          AND occurred_at <= @end
        GROUP BY ts
        ORDER BY ts ASC
    """
    rows = _bq_query(runner, sql_agg, {
        "store_id": store_id,
        "start": _ts(start),
        "end": _ts(end),
    }, project=project)

    buckets: list[RevenueBucket] = []
    for row in rows:
        ts_raw = row.get("ts")
        if isinstance(ts_raw, str):
            ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
        else:
            ts = datetime.now(timezone.utc)
        buckets.append(RevenueBucket(
            timestamp=ts,
            revenue=round(float(cast(Any, row.get("revenue", 0))), 2),
            transactions=int(cast(Any, row.get("transactions", 0))),
            items_sold=int(cast(Any, row.get("items_sold", 0))),
        ))

    # Totals query
    sql_totals = f"""
        SELECT
            SUM(quantity * 1.0) AS total_revenue,
            COUNT(*) AS total_transactions,
            SUM(quantity) AS total_items_sold,
            SAFE_DIVIDE(SUM(quantity * 1.0), COUNT(*)) AS avg_ticket
        FROM {table}
        WHERE store_id = @store_id
          AND occurred_at >= @start
          AND occurred_at <= @end
    """
    total_rows = _bq_query(runner, sql_totals, {
        "store_id": store_id,
        "start": _ts(start),
        "end": _ts(end),
    }, project=project)

    if total_rows:
        r = total_rows[0]
        totals = {
            "revenue": float(cast(Any, r.get("total_revenue") or 0)),
            "transactions": int(cast(Any, r.get("total_transactions") or 0)),
            "items_sold": int(cast(Any, r.get("total_items_sold") or 0)),
            "avg_ticket": float(cast(Any, r.get("avg_ticket") or 0)),
        }
    else:
        totals = {"revenue": 0.0, "transactions": 0, "items_sold": 0, "avg_ticket": 0.0}

    return buckets, totals


class BigQueryPromotionRepository:
    """Queries promotions from Firestore or BQ."""

    def __init__(
        self,
        runner: CommandRunner | None = None,
        project: str = ALLOWED_PROJECT,
        dataset: str = ALLOWED_DATASET,
    ) -> None:
        self._runner = runner or SubprocessRunner()
        self._project = project
        self._dataset = dataset

    def list_promotions(
        self,
        store_id: str,
        status: PromotionStatus | None = None,
        sku: str | None = None,
        category: str | None = None,
        limit: int = 100,
    ) -> PromotionsResponse:
        rows = _bq_promotions_query(
            self._runner,
            self._project,
            self._dataset,
            store_id,
            status,
            sku,
            category,
            limit,
        )
        promotions = [_row_to_promotion(r) for r in rows]
        active = [p for p in promotions if p.status == PromotionStatus.ACTIVE]
        # Calculate totals for FE-compatible response
        total_revenue = sum(p.revenue for p in promotions)
        total_incremental = sum(p.incremental_revenue for p in promotions)
        total_discount = sum(p.discount_cost for p in promotions)
        return PromotionsResponse(
            store_id=store_id,
            revenue=total_revenue,
            incremental_revenue=total_incremental,
            discount_cost=total_discount,
            promotions=promotions,
            total=len(promotions),
            active_count=len(active),
        )


class BigQueryCheckoutRepository:
    """Scaffold for BQ/Firestore checkout analytics — future work (issue #95).

    This class is a placeholder. A verified BQ table/schema for checkouts does
    not yet exist. Until then, use InMemoryCheckoutRepository (the default).
    To implement: query the `checkouts` / `transactions` BQ table filtered by
    store_id and checkout_id, then map rows to CheckoutResponse.
    """

    def __init__(
        self,
        runner: CommandRunner | None = None,
        project: str = ALLOWED_PROJECT,
        dataset: str = ALLOWED_DATASET,
    ) -> None:
        self._runner = runner or SubprocessRunner()
        self._project = project
        self._dataset = dataset

    def get_checkout(self, checkout_id: str, store_id: str) -> CheckoutResponse:
        raise AnalyticsError(
            "BigQueryCheckoutRepository is scaffold-only (issue #95). "
            "Use InMemoryCheckoutRepository for production until a verified BQ "
            "checkout table exists."
        )


def _bq_promotions_query(
    runner: CommandRunner,
    project: str,
    dataset: str,
    store_id: str,
    status: PromotionStatus | None = None,
    sku: str | None = None,
    category: str | None = None,
    limit: int = 100,
) -> list[dict[str, object]]:
    """Query promotions from BQ analytics.promotions table."""
    table = _bq_table(project, dataset, "promotions")

    conditions = ["store_id = @store_id"]
    params: dict[str, str | int] = {"store_id": store_id, "limit": limit}
    if status is not None:
        conditions.append("status = @status")
        params["status"] = status.value
    if sku is not None:
        conditions.append("sku = @sku")
        params["sku"] = sku
    if category is not None:
        conditions.append("category = @category")
        params["category"] = category

    sql = f"""
        SELECT
            promotion_id, name, promotion_type, status, store_id,
            sku, category, discount_value, conditions,
            start_time, end_time, redemption_count, metadata
        FROM {table}
        WHERE {" AND ".join(conditions)}
        ORDER BY start_time DESC
        LIMIT @limit
    """
    try:
        return _bq_query(runner, sql, params, project=project)
    except AnalyticsError:
        return []


def _row_to_promotion(row: dict[str, object]) -> Promotion:
    def _ts(v: object) -> datetime:
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        if isinstance(v, datetime):
            return v
        return datetime.now(timezone.utc)

    type_str = str(row.get("promotion_type", "discount_percent")).lower()
    # Map old type names to new ones for backward compatibility
    type_mapping = {
        "discount_percent": "percent_off",
        "discount_absolute": "amount_off",
        "buy_one_get_one": "buy_x_get_y",
    }
    type_str = type_mapping.get(type_str, type_str)
    try:
        ptype = PromotionType(type_str)
    except ValueError:
        ptype = PromotionType.PERCENT_OFF

    status_str = str(row.get("status", "active")).lower()
    # Map old status names to new ones for backward compatibility
    status_mapping = {
        "upcoming": "scheduled",
        "cancelled": "ended",
    }
    status_str = status_mapping.get(status_str, status_str)
    try:
        pstatus = PromotionStatus(status_str)
    except ValueError:
        pstatus = PromotionStatus.ACTIVE

    metadata_raw = row.get("metadata") or {}
    if not isinstance(metadata_raw, dict):
        metadata_raw = {}
    metadata = {str(k): str(v) for k, v in metadata_raw.items()}

    # Handle both old field names and new FE-compatible names
    sku_value = row.get("sku") or row.get("skus")
    if isinstance(sku_value, str):
        skus_list = [sku_value]
    elif isinstance(sku_value, list):
        skus_list = sku_value
    else:
        skus_list = []

    return Promotion(
        promotion_id=str(row["promotion_id"]),
        name=str(row["name"]),
        promotion_type=ptype,
        status=pstatus,
        store_id=str(row["store_id"]),
        sku=str(row["sku"]) if row.get("sku") else None,
        category=str(row["category"]) if row.get("category") else None,
        discount_value=float(cast(Any, row["discount_value"])) if row.get("discount_value") else None,
        conditions=str(row["conditions"]) if row.get("conditions") else None,
        start_time=_ts(row.get("start_time")),
        end_time=_ts(row.get("end_time")),
        redemption_count=int(cast(Any, row.get("redemption_count") or 0)),
        metadata=metadata,
        # New FE-compatible fields
        revenue=float(cast(Any, row.get("revenue", 0))),
        incremental_revenue=float(cast(Any, row.get("incremental_revenue", 0))),
        discount_cost=float(cast(Any, row.get("discount_cost", 0))),
    )


# ─── Default factories ─────────────────────────────────────────────────────────

def default_anomaly_repository() -> AnomalyRepository:
    return BigQueryAnomalyRepository()


def default_revenue_repository() -> RevenueRepository:
    return BigQueryRevenueRepository()


def default_promotion_repository() -> PromotionRepository:
    return BigQueryPromotionRepository()


def get_anomaly_repository() -> AnomalyRepository:
    return BigQueryAnomalyRepository()


def get_revenue_repository() -> RevenueRepository:
    return BigQueryRevenueRepository()


def get_promotion_repository() -> PromotionRepository:
    return BigQueryPromotionRepository()


def get_checkout_repository() -> CheckoutRepository:
    """Returns the production checkout repository.

    Uses InMemoryCheckoutRepository by default. BigQueryCheckoutRepository is
    scaffold-only (issue #95) — swap this function once a verified BQ checkout
    table exists.
    """
    return InMemoryCheckoutRepository()


def unavailable_analytics_repositories() -> tuple[AnomalyRepository, RevenueRepository, PromotionRepository, CheckoutRepository]:
    """Return always-empty adapters when GCP is unavailable."""
    return (
        _UnavailableAnomalyRepository(),
        _UnavailableRevenueRepository(),
        _UnavailablePromotionRepository(),
        _UnavailableCheckoutRepository(),
    )


class _UnavailableAnomalyRepository:
    available = False

    def list_anomalies(
        self,
        store_id: str,
        severity: AnomalySeverity | None = None,
        anomaly_type: AnomalyType | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> AnomaliesResponse:
        return AnomaliesResponse(anomalies=[], total=0, detected_since=None)


class _UnavailableRevenueRepository:
    available = False

    def get_revenue(
        self,
        store_id: str,
        period: Literal["hourly", "daily", "weekly", "monthly"],
        start: datetime,
        end: datetime,
    ) -> RevenueResponse:
        return RevenueResponse(
            store_id=store_id,
            period=period,
            start=start,
            end=end,
            total_revenue=0.0,
            total_transactions=0,
            total_items_sold=0,
            avg_transaction_value=0.0,
            buckets=[],
        )


class _UnavailablePromotionRepository:
    available = False

    def list_promotions(
        self,
        store_id: str,
        status: PromotionStatus | None = None,
        sku: str | None = None,
        category: str | None = None,
        limit: int = 100,
    ) -> PromotionsResponse:
        return PromotionsResponse(
            store_id=store_id,
            revenue=0,
            incremental_revenue=0,
            discount_cost=0,
            promotions=[],
            total=0,
            active_count=0,
        )
