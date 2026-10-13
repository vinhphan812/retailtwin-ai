"""Day-0 routes. Live Twin mutation stays behind the guard and the executor."""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response

from retailtwin_api.analytics_repository import (
    AnomalyRepository,
    CheckoutRepository,
    PromotionRepository,
    RevenueRepository,
)
from retailtwin_api.errors import ApiError
from retailtwin_api.events import EventConflict, EventLog
from retailtwin_api.schemas import (
    AnomaliesResponse,
    AnomalySeverity,
    AnomalyType,
    CheckoutSummary,
    CheckoutTransaction,
    EventReceipt,
    HealthResponse,
    ProductInventory,
    PromotionsResponse,
    PromotionStatus,
    RevenueResponse,
    StoreEvent,
    StoreResponse,
)
from retailtwin_api.store import StoreRepository

logger = logging.getLogger(__name__)
router = APIRouter()


def get_store(request: Request) -> StoreRepository:
    return request.app.state.store


def get_events(request: Request) -> EventLog:
    return request.app.state.events


def get_anomalies(request: Request) -> AnomalyRepository:
    return request.app.state.anomalies


def get_revenue_repo(request: Request) -> RevenueRepository:
    return request.app.state.revenue


def get_promotions(request: Request) -> PromotionRepository:
    return request.app.state.promotions


def get_checkout_repo(request: Request) -> CheckoutRepository:
    return request.app.state.checkouts



def require_loaded(store: StoreRepository) -> None:
    if not store.loaded:
        raise ApiError(503, "store_unavailable", "Store fixture is not available.")


@router.get("/health", response_model=HealthResponse)
def health(request: Request, store: StoreRepository = Depends(get_store)) -> HealthResponse:
    return HealthResponse(
        status="ok" if store.loaded else "degraded",
        service="retailtwin-api",
        environment=request.app.state.settings.app_env,
        store_id=store.store_id,
        fixture_loaded=store.loaded,
    )


@router.get("/store", response_model=StoreResponse)
def read_store(store: StoreRepository = Depends(get_store)) -> StoreResponse:
    require_loaded(store)
    return store.view()


@router.get("/inventory/{sku}", response_model=ProductInventory)
def read_inventory(sku: str, store: StoreRepository = Depends(get_store)) -> ProductInventory:
    require_loaded(store)
    product = store.inventory(sku)
    if product is None:
        raise ApiError(404, "sku_not_found", f"SKU {sku!r} is not in store {store.store_id}.")
    return product


@router.post("/events", response_model=EventReceipt)
def accept_event(
    event: StoreEvent,
    response: Response,
    store: StoreRepository = Depends(get_store),
    events: EventLog = Depends(get_events),
) -> EventReceipt:
    require_loaded(store)
    stored_event = events.get(event.event_id)
    if stored_event is not None:
        if stored_event == event:
            response.status_code = 200
            _log_event(stored_event, duplicate=True)
            return EventReceipt(duplicate=True, event=stored_event)
        raise ApiError(
            409,
            "event_id_conflict",
            f"Event {event.event_id!r} already exists with a different payload.",
        )
    if event.store_id != store.store_id:
        raise ApiError(404, "store_not_found", f"Store {event.store_id!r} is not served by this API.")
    if store.inventory(event.sku) is None:
        raise ApiError(404, "sku_not_found", f"SKU {event.sku!r} is not in store {store.store_id}.")
    # Record only. Shelf quantity stays on the read model until an authorized executor runs.
    try:
        stored, duplicate = events.accept(event)
    except EventConflict as exc:
        raise ApiError(
            409,
            "event_id_conflict",
            f"Event {exc.event_id!r} already exists with a different payload.",
        ) from exc
    response.status_code = 200 if duplicate else 201
    _log_event(stored, duplicate)
    return EventReceipt(duplicate=duplicate, event=stored)


def _log_event(event: StoreEvent, duplicate: bool) -> None:
    logger.info(
        json.dumps(
            {
                "message": "event.accepted",
                "event_id": event.event_id,
                "correlation_id": event.correlation_id,
                "store_id": event.store_id,
                "duplicate": duplicate,
            }
        )
    )


@router.get("/anomalies", response_model=AnomaliesResponse)
def list_anomalies(
    request: Request,
    store: StoreRepository = Depends(get_store),
    anomaly_repo: AnomalyRepository = Depends(get_anomalies),
    severity: AnomalySeverity | None = Query(default=None),
    anomaly_type: AnomalyType | None = Query(default=None),
    since: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> AnomaliesResponse:
    require_loaded(store)
    try:
        return anomaly_repo.list_anomalies(
            store_id=store.store_id,
            severity=severity,
            anomaly_type=anomaly_type,
            since=since,
            limit=limit,
        )
    except Exception as exc:
        logger.warning("anomaly.query_failed", extra={"store_id": store.store_id, "error": str(exc)})
        raise ApiError(503, "analytics_unavailable", "Anomaly data source is temporarily unavailable.") from exc


@router.get("/revenue", response_model=RevenueResponse)
def get_revenue(
    request: Request,
    store: StoreRepository = Depends(get_store),
    revenue_repo: RevenueRepository = Depends(get_revenue_repo),
    period: Literal["hourly", "daily", "weekly", "monthly"] = Query(default="daily"),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
) -> RevenueResponse:
    require_loaded(store)
    now = datetime.now(timezone.utc)
    resolved_start = start if start is not None else (now - timedelta(days=30))
    resolved_end = end if end is not None else now
    if resolved_start >= resolved_end:
        raise ApiError(422, "invalid_period", "start must be before end.")
    try:
        return revenue_repo.get_revenue(
            store_id=store.store_id,
            period=period,
            start=resolved_start,
            end=resolved_end,
        )
    except Exception as exc:
        logger.warning("revenue.query_failed", extra={"store_id": store.store_id, "error": str(exc)})
        raise ApiError(503, "analytics_unavailable", "Revenue data source is temporarily unavailable.") from exc


@router.get("/promotions", response_model=PromotionsResponse)
def list_promotions(
    request: Request,
    store: StoreRepository = Depends(get_store),
    promotion_repo: PromotionRepository = Depends(get_promotions),
    status: PromotionStatus | None = Query(default=None),
    sku: str | None = Query(default=None),
    category: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> PromotionsResponse:
    require_loaded(store)
    try:
        return promotion_repo.list_promotions(
            store_id=store.store_id,
            status=status,
            sku=sku,
            category=category,
            limit=limit,
        )
    except Exception as exc:
        logger.warning("promotions.query_failed", extra={"store_id": store.store_id, "error": str(exc)})
        raise ApiError(503, "analytics_unavailable", "Promotion data source is temporarily unavailable.") from exc


@router.get("/checkouts", response_model=list[CheckoutSummary])
def list_checkouts(
    request: Request,
    store: StoreRepository = Depends(get_store),
    checkout_repo: CheckoutRepository = Depends(get_checkout_repo),
) -> list[CheckoutSummary]:
    require_loaded(store)
    try:
        return checkout_repo.list_checkouts(store_id=store.store_id)
    except Exception as exc:
        logger.warning("checkouts.query_failed", extra={"store_id": store.store_id, "error": str(exc)})
        raise ApiError(503, "analytics_unavailable", "Checkout data source is temporarily unavailable.") from exc


@router.get("/checkouts/{checkout_id}/transactions", response_model=list[CheckoutTransaction])
def list_checkout_transactions(
    checkout_id: str,
    date: str = Query(..., description="Business date YYYY-MM-DD"),
    request: Request = None,
    store: StoreRepository = Depends(get_store),
    checkout_repo: CheckoutRepository = Depends(get_checkout_repo),
) -> list[CheckoutTransaction]:
    require_loaded(store)
    try:
        return checkout_repo.list_transactions(store_id=store.store_id, checkout_id=checkout_id, date_str=date)
    except ValueError as exc:
        raise ApiError(422, "invalid_date", str(exc)) from exc
    except KeyError as exc:
        raise ApiError(404, "checkout_not_found", str(exc)) from exc
    except Exception as exc:
        logger.warning("checkout_transactions.query_failed", extra={"store_id": store.store_id, "checkout_id": checkout_id, "error": str(exc)})
        raise ApiError(503, "analytics_unavailable", "Checkout transaction data source is temporarily unavailable.") from exc

