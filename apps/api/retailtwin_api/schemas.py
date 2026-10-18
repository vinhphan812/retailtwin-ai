"""Public request and response models for the day-0 API."""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: Literal["retailtwin-api"]
    environment: str
    app_env: str
    store_id: str
    fixture_loaded: bool
    # ADR 0025: the process reports the canonical SemVer plus the build commit.
    # The git SHA is informational build metadata; the SemVer drives compatibility.
    version: str
    git_sha: str


class ReadyResponse(BaseModel):
    """Readiness probe response — used by Cloud Run load-balancer routing decisions."""

    ready: Literal[True]
    service: Literal["retailtwin-api"]
    store_id: str
    correlation_id: str


class VersionResponse(BaseModel):
    """``GET /version`` payload — the canonical SemVer plus build metadata."""

    version: str
    git_sha: str
    build_time: str
    service: Literal["retailtwin-api"]
    full_version: str


class ProductInventory(BaseModel):
    store_id: str
    sku: str
    shelf_id: str
    slot_id: str
    facings: int
    shelf_quantity: int
    backroom_quantity: int
    version: int


class StoreResponse(BaseModel):
    store_id: str
    context_version: str
    version: str
    products: list[ProductInventory]


class FixtureProduct(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sku: str = Field(min_length=1)
    shelf_id: str = Field(min_length=1)
    slot_id: str = Field(min_length=1)
    facings: int = Field(ge=0)
    shelf_quantity: int = Field(ge=0)
    backroom_quantity: int = Field(ge=0)


class FixtureFile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    store_id: str = Field(min_length=1)
    version: str
    products: list[FixtureProduct]


class StoreEvent(BaseModel):
    """Minimum normalized store event from the domain model."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    store_id: str = Field(min_length=1)
    sku: str = Field(min_length=1)
    quantity: int = Field(ge=1)
    occurred_at: AwareDatetime
    source: str = Field(min_length=1)

    @field_validator(
        "event_id",
        "correlation_id",
        "event_type",
        "store_id",
        "sku",
        "source",
        mode="before",
    )
    @classmethod
    def strip_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class EventReceipt(BaseModel):
    accepted: Literal[True] = True
    duplicate: bool
    event: StoreEvent
    # Set when this event started an autonomous investigation (AUTONOMY_ENABLED).
    investigation_id: str | None = None


# ─── Anomaly schemas ──────────────────────────────────────────────────────────

class AnomalyType(StrEnum):
    STOCKOUT = "stockout"
    DEMAND_SURGE = "demand_surge"
    SLOW_MOVING = "slow_moving"
    EXCESS_INVENTORY = "excess_inventory"
    PRICE_ANOMALY = "price_anomaly"
    SHELF_VIOLATION = "shelf_violation"


class AnomalySeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Anomaly(BaseModel):
    anomaly_id: str = Field(min_length=1)
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    store_id: str = Field(min_length=1)
    sku: str | None = None
    shelf_id: str | None = None
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    detected_at: datetime
    event_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class AnomaliesResponse(BaseModel):
    anomalies: list[Anomaly]
    total: int
    detected_since: datetime | None = None


# ─── Checkout analytics schemas ────────────────────────────────────────────────

class Cashier(BaseModel):
    staff_id: str
    name: str


class CheckoutLine(BaseModel):
    sku: str
    quantity: int = Field(ge=1)
    unit_price: float = Field(ge=0)
    line_total: float = Field(ge=0)


class CheckoutTransaction(BaseModel):
    transaction_id: str
    checkout_id: str
    store_id: str
    completed_at: datetime
    cashier: Cashier | None = None
    items: int = Field(ge=0)
    total: float = Field(ge=0)
    payment_method: Literal["cash", "card", "mobile"]
    lines: list[CheckoutLine] = Field(default_factory=list)


class CheckoutSummary(BaseModel):
    checkout_id: str
    store_id: str
    status: Literal["open", "paused", "closed"]
    cashier: Cashier | None = None
    shift_started_at: datetime | None = None
    business_date: str
    revenue_today: float = Field(ge=0)
    transactions_today: int = Field(ge=0)
    items_scanned_today: int = Field(ge=0)
    queue_length: int = Field(ge=0)
    last_transaction_at: datetime | None = None


class CheckoutResponse(BaseModel):
    summary: CheckoutSummary
    transactions: list[CheckoutTransaction] = Field(default_factory=list)


# ─── Revenue schemas ──────────────────────────────────────────────────────────

class RevenueBucket(BaseModel):
    timestamp: datetime
    revenue: float
    transactions: int
    items_sold: int


class RevenueResponse(BaseModel):
    store_id: str = Field(min_length=1)
    period: Literal["hourly", "daily", "weekly", "monthly"]
    start: datetime
    end: datetime
    total_revenue: float
    total_transactions: int
    total_items_sold: int
    avg_transaction_value: float
    currency: Literal["USD"] = "USD"
    buckets: list[RevenueBucket] = Field(default_factory=list)


# ─── Promotion schemas ────────────────────────────────────────────────────────

class PromotionStatus(StrEnum):
    ACTIVE = "active"
    SCHEDULED = "scheduled"
    PENDING_REVIEW = "pending_review"
    DRAFT = "draft"
    ENDED = "ended"


class PromotionType(StrEnum):
    PERCENT_OFF = "percent_off"
    AMOUNT_OFF = "amount_off"
    BUY_X_GET_Y = "buy_x_get_y"
    BUNDLE = "bundle"


class Promotion(BaseModel):
    """Promotion schema aligned with FE Promotion type."""
    model_config = ConfigDict(populate_by_name=True, alias_names={"promotion_id": "id", "promotion_type": "kind", "discount_value": "value", "start_time": "starts_at", "end_time": "ends_at"})

    # FE-compatible field names - use serialization_alias to allow both old and new names
    id: str = Field(serialization_alias="id", validation_alias="promotion_id", min_length=1)
    name: str
    kind: PromotionType = Field(serialization_alias="kind", validation_alias="promotion_type")
    status: PromotionStatus
    store_id: str
    sku: str | None = None
    category: str | None = None
    value: float | None = Field(default=None, serialization_alias="value", validation_alias="discount_value")
    conditions: str | None = None
    starts_at: datetime = Field(serialization_alias="starts_at", validation_alias="start_time")
    ends_at: datetime = Field(serialization_alias="ends_at", validation_alias="end_time")
    skus: list[str] = Field(default_factory=list)
    revenue: float = 0
    incremental_revenue: float = 0
    discount_cost: float = 0
    redemption_count: int = 0
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("skus", mode="before")
    @classmethod
    def compute_skus(cls, v: list[str] | str | None) -> list[str]:
        """Convert single SKU to list for FE compatibility."""
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return v


class PromotionsResponse(BaseModel):
    """Response aligned with FE PromotionsSummary type."""
    store_id: str
    revenue: float = 0
    incremental_revenue: float = 0
    discount_cost: float = 0
    promotions: list[Promotion]
    total: int
    active_count: int
