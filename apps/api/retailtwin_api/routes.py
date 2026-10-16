"""Day-0 routes. Live Twin mutation stays behind the guard and the executor."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Literal, cast

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response

from retailtwin_api.agents.executor import CommitService
from retailtwin_api.agents.observer.consumer import ObservationError, consume_available
from retailtwin_api.backbone import SALE_COMPLETED
from retailtwin_api.analytics_repository import (
    AnalyticsError,
    AnomalyRepository,
    PromotionRepository,
    RevenueRepository,
    CheckoutRepository,
    CheckoutNotFound,
)
from retailtwin_api.contracts import DCGVerdict
from retailtwin_api.decisions import DecisionSource
from retailtwin_api.errors import ApiError
from retailtwin_api.events import EventConflict, EventLog, ReviewAuditLog
from retailtwin_api.guard.decision_context_guard import GuardAuditEvent, GuardAuditSink
from retailtwin_api.guard.decision_context_guard.authorization import SignedAuthorization
from retailtwin_api.schemas import (
    AnomaliesResponse,
    AnomalySeverity,
    AnomalyType,
    EventReceipt,
    HealthResponse,
    ProductInventory,
    PromotionStatus,
    PromotionsResponse,
    ReadyResponse,
    RevenueResponse,
    CheckoutResponse,
    StoreEvent,
    StoreResponse,
)
from retailtwin_api.simulation_repository import SimulationReadRepository
from retailtwin_api.simulation_schemas import (
    AgentEventListResponse,
    CandidateListResponse,
    CommitAuthorizationReceipt,
    CursorParameters,
    DecisionReviewReasonCode,
    DecisionReviewVerdict,
    GuardGateResult,
    PageParameters,
    SimulationCandidateResponse,
    SimulationDetail,
    SimulationFilters,
    SimulationListResponse,
    SimulationReviewRequest,
    SimulationReviewResponse,
    SimulationStatus,
)
from retailtwin_api.store import StoreReader

logger = logging.getLogger(__name__)
router = APIRouter()


def get_store(request: Request) -> StoreReader:
    return request.app.state.store


def get_events(request: Request) -> EventLog:
    return request.app.state.events


def get_simulations(request: Request) -> SimulationReadRepository:
    return request.app.state.simulations


def get_anomalies(request: Request) -> AnomalyRepository:
    return request.app.state.anomalies


def get_revenue_repo(request: Request) -> RevenueRepository:
    return request.app.state.revenue


def get_promotions(request: Request) -> PromotionRepository:
    return request.app.state.promotions


def get_checkouts(request: Request) -> CheckoutRepository:
    return request.app.state.checkouts


def get_guard_audit(request: Request) -> GuardAuditSink:
    return request.app.state.guard_audit


def get_decisions(request: Request) -> DecisionSource:
    return request.app.state.decisions


def require_simulations(repository: SimulationReadRepository) -> None:
    if not repository.available:
        raise ApiError(503, "simulations_unavailable", "Simulation read model is not available.")


def require_loaded(store: StoreReader) -> None:
    if not store.loaded:
        raise ApiError(503, "store_unavailable", "Store fixture is not available.")


def _correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", "no-correlation-id")


@router.get("/health", response_model=HealthResponse, include_in_schema=True)
def health(
    request: Request,
    store: StoreReader = Depends(get_store),
    anomalies: AnomalyRepository = Depends(get_anomalies),
    revenue: RevenueRepository = Depends(get_revenue_repo),
    promotions: PromotionRepository = Depends(get_promotions),
) -> HealthResponse:
    """Liveness probe: is the process alive?

    - status="ok"      when store is loaded AND no analytics calls raise an exception
    - status="degraded" only when store is not loaded OR when an analytics call
                       actually raises (e.g. GCP unreachable).  Empty responses
                       (a store with no anomalies today) are NOT degraded.
    """
    if not store.loaded:
        return HealthResponse(
            status="degraded",
            service="retailtwin-api",
            environment=request.app.state.settings.app_env,
            app_env=request.app.state.settings.app_env,
            store_id=store.store_id,
            fixture_loaded=False,
        )
    try:
        anomalies.list_anomalies(store_id=store.store_id, limit=1)
        revenue.get_revenue(store_id=store.store_id, period="hourly", start=datetime.now(timezone.utc), end=datetime.now(timezone.utc))
        promotions.list_promotions(store_id=store.store_id, limit=1)
    except Exception:
        return HealthResponse(
            status="degraded",
            service="retailtwin-api",
            environment=request.app.state.settings.app_env,
            app_env=request.app.state.settings.app_env,
            store_id=store.store_id,
            fixture_loaded=True,
        )
    return HealthResponse(
        status="ok",
        service="retailtwin-api",
        environment=request.app.state.settings.app_env,
        app_env=request.app.state.settings.app_env,
        store_id=store.store_id,
        fixture_loaded=True,
    )


@router.get("/ready", response_model=ReadyResponse, include_in_schema=True)
def ready(request: Request, store: StoreReader = Depends(get_store)) -> ReadyResponse:
    """Readiness probe: can the service handle traffic?

    Returns 503 when the store fixture is unavailable, causing Cloud Run
    load-balancer to drain traffic away from this instance until the
    fixture is reloaded.
    """
    if not store.loaded:
        raise ApiError(503, "store_unavailable", "Store fixture is not available.")
    return ReadyResponse(
        ready=True,
        service="retailtwin-api",
        store_id=store.store_id,
        correlation_id=_correlation_id(request),
    )


@router.get("/store", response_model=StoreResponse, include_in_schema=True)
def read_store(request: Request, store: StoreReader = Depends(get_store)) -> StoreResponse:
    require_loaded(store)
    return store.view()


@router.get("/inventory/{sku}", response_model=ProductInventory, include_in_schema=True)
def read_inventory(request: Request, sku: str, store: StoreReader = Depends(get_store)) -> ProductInventory:
    require_loaded(store)
    product = store.inventory(sku)
    if product is None:
        logger.warning(
            "sku.not_found",
            extra={"correlation_id": _correlation_id(request), "sku": sku, "store_id": store.store_id},
        )
        raise ApiError(404, "sku_not_found", f"SKU {sku!r} is not in store {store.store_id}.")
    return product


@router.post("/events", response_model=EventReceipt, include_in_schema=True)
def accept_event(
    request: Request,
    event: StoreEvent,
    response: Response,
    background: BackgroundTasks,
    store: StoreReader = Depends(get_store),
    events: EventLog = Depends(get_events),
) -> EventReceipt:
    require_loaded(store)
    cid = _correlation_id(request)
    stored_event = events.get(event.event_id)
    if stored_event is not None:
        if stored_event == event:
            response.status_code = 200
            _log_event(stored_event, duplicate=True, correlation_id=cid)
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
    _log_event(stored, duplicate=duplicate, correlation_id=cid)
    investigation_id = None
    if not duplicate:
        investigation_id = _observe(request, stored, background)
    return EventReceipt(duplicate=duplicate, event=stored, investigation_id=investigation_id)


def _observe(request: Request, event: StoreEvent, background: BackgroundTasks) -> str | None:
    """Hand a new sale to the Observer. The investigation itself runs after the response."""
    autonomy = request.app.state.autonomy
    if autonomy is None or event.event_type != SALE_COMPLETED:
        return None
    pipe = request.app.state.event_pipe
    pipe.publish(event)
    try:
        outcomes = consume_available(pipe, request.app.state.activation_ledger, autonomy, request.app.state.quarantine)
    except ObservationError:
        logger.error("observer.handoff_failed", extra={"event_id": event.event_id, "correlation_id": event.correlation_id})
        return None
    background.add_task(autonomy.drain)
    started = [o for o in outcomes if o.outcome == "started" and o.event_id == event.event_id]
    return started[0].investigation_id if started else None


def _log_event(event: StoreEvent, duplicate: bool, correlation_id: str) -> None:
    msg = f"event.accepted event_id={event.event_id} duplicate={duplicate} store_id={event.store_id} correlation_id={correlation_id}"
    logger.info(
        msg,
        extra={
            "correlation_id": correlation_id,
            "event_id": event.event_id,
            "correlation_id_header": event.correlation_id,
            "store_id": event.store_id,
            "duplicate": duplicate,
        },
    )


# ─── Analytics ─────────────────────────────────────────────────────────────────

@router.get("/anomalies", response_model=AnomaliesResponse, include_in_schema=True)
def list_anomalies(
    request: Request,
    severity: AnomalySeverity | None = Query(default=None),
    anomaly_type: AnomalyType | None = Query(default=None),
    since: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    store_id: str | None = Query(default=None, min_length=1),
    repo: AnomalyRepository = Depends(get_anomalies),
) -> AnomaliesResponse:
    """Return detected anomalies for a store, newest first.

    Degrades gracefully: if the analytics backend is unavailable, returns an empty
    list with code "analytics_unavailable" logged as a warning (not a 500 crash).
    """
    target_store = store_id or request.app.state.settings.store_id
    try:
        return repo.list_anomalies(
            store_id=target_store,
            severity=severity,
            anomaly_type=anomaly_type,
            since=since,
            limit=limit,
        )
    except AnalyticsError as exc:
        logger.warning(
            "analytics.anomalies_unavailable",
            extra={"correlation_id": _correlation_id(request), "store_id": target_store},
        )
        raise ApiError(503, "analytics_unavailable", "Anomalies analytics are currently unavailable.") from exc


@router.get("/revenue", response_model=RevenueResponse, include_in_schema=True)
def get_revenue(
    request: Request,
    period: Literal["hourly", "daily", "weekly", "monthly"] = Query(default="daily"),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    store_id: str | None = Query(default=None, min_length=1),
    repo: RevenueRepository = Depends(get_revenue_repo),
) -> RevenueResponse:
    """Return revenue aggregates for a store over the requested period.

    Degrades gracefully: if the analytics backend is unavailable, returns an empty
    revenue response with code "analytics_unavailable" logged as a warning.
    """
    target_store = store_id or request.app.state.settings.store_id
    now = datetime.now(timezone.utc)
    period_start = start or (now - timedelta(days=1))
    period_end = end or now
    if period_start > period_end:
        raise ApiError(422, "invalid_range", "start must be before end.")
    try:
        return repo.get_revenue(
            store_id=target_store,
            period=period,
            start=period_start,
            end=period_end,
        )
    except AnalyticsError as exc:
        logger.warning(
            "analytics.revenue_unavailable",
            extra={"correlation_id": _correlation_id(request), "store_id": target_store},
        )
        raise ApiError(503, "analytics_unavailable", "Revenue analytics are currently unavailable.") from exc


@router.get("/promotions", response_model=PromotionsResponse, include_in_schema=True)
def list_promotions(
    request: Request,
    status: PromotionStatus | None = Query(default=None),
    sku: str | None = Query(default=None, min_length=1),
    category: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=100, ge=1, le=500),
    store_id: str | None = Query(default=None, min_length=1),
    repo: PromotionRepository = Depends(get_promotions),
) -> PromotionsResponse:
    """Return promotions for a store, newest first.

    Degrades gracefully: if the analytics backend is unavailable, returns an empty
    list with code "analytics_unavailable" logged as a warning.
    """
    target_store = store_id or request.app.state.settings.store_id
    try:
        return repo.list_promotions(
            store_id=target_store,
            status=status,
            sku=sku,
            category=category,
            limit=limit,
        )
    except AnalyticsError as exc:
        logger.warning(
            "analytics.promotions_unavailable",
            extra={"correlation_id": _correlation_id(request), "store_id": target_store},
        )
        raise ApiError(503, "analytics_unavailable", "Promotion analytics are currently unavailable.") from exc


@router.get("/checkouts/{checkout_id}", response_model=CheckoutResponse, include_in_schema=True)
def get_checkout(
    request: Request,
    checkout_id: str,
    store_id: str | None = Query(default=None, min_length=1),
    repo: CheckoutRepository = Depends(get_checkouts),
) -> CheckoutResponse:
    """Return a demo-safe checkout summary and transactions for a checkout lane.

    Degrades gracefully: if analytics are unavailable, raises 503 analytics_unavailable.
    Unknown checkout returns 404 checkout_not_found.

    PII policy: cashier staff_id and name are never returned by this public
    endpoint. Cashier data is retained only within the repository read model.
    """
    target_store = store_id or request.app.state.settings.store_id
    try:
        response = repo.get_checkout(checkout_id=checkout_id, store_id=target_store)
        if response.summary.cashier is not None:
            response.summary.cashier = None
        response.transactions = [
            txn.model_copy(update={"cashier": None}) for txn in response.transactions
        ]
        return response
    except CheckoutNotFound as exc:
        raise ApiError(404, "checkout_not_found", f"Checkout {checkout_id!r} was not found.") from exc
    except AnalyticsError as exc:
        logger.warning(
            "analytics.checkout_unavailable",
            extra={"correlation_id": _correlation_id(request), "store_id": target_store, "checkout_id": checkout_id},
        )
        raise ApiError(503, "analytics_unavailable", "Checkout analytics are currently unavailable.") from exc


# ─── Simulations ────────────────────────────────────────────────────────────────

@router.get("/simulations", response_model=SimulationListResponse)
def list_simulations(
    status: str | None = Query(default=None, pattern="^(pending|evaluated|committed|rejected|open)$"),
    store_id: str | None = Query(default=None, min_length=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    repository: SimulationReadRepository = Depends(get_simulations),
) -> SimulationListResponse:
    require_simulations(repository)
    return repository.list_simulations(
        SimulationFilters(
            status=cast(SimulationStatus | Literal["open"] | None, status),
            store_id=store_id,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/simulations/{simulation_id}", response_model=SimulationDetail)
def read_simulation(
    request: Request,
    simulation_id: str,
    repository: SimulationReadRepository = Depends(get_simulations),
    decisions: DecisionSource = Depends(get_decisions),
    audit: GuardAuditSink = Depends(get_guard_audit),
) -> SimulationDetail:
    require_simulations(repository)
    item = repository.get_simulation(simulation_id)
    if item is None:
        raise ApiError(404, "simulation_not_found", f"Simulation {simulation_id!r} was not found.")
    return _with_guard_summary(item, decisions, audit)


@router.get("/simulations/{simulation_id}/candidates", response_model=CandidateListResponse)
def list_candidates(
    request: Request,
    simulation_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    repository: SimulationReadRepository = Depends(get_simulations),
    decisions: DecisionSource = Depends(get_decisions),
    audit: GuardAuditSink = Depends(get_guard_audit),
) -> CandidateListResponse:
    require_simulations(repository)
    result = repository.list_candidates(simulation_id, PageParameters(page=page, page_size=page_size))
    if result is None:
        raise ApiError(404, "simulation_not_found", f"Simulation {simulation_id!r} was not found.")
    summary = _guard_fields_for_simulation(simulation_id, decisions, audit)
    if summary is None:
        return result
    evaluated_candidate_id, fields = summary
    return result.model_copy(
        update={
            "candidates": [
                candidate.model_copy(update=fields)
                if candidate.candidate_id == evaluated_candidate_id
                else _not_evaluated_candidate(candidate)
                for candidate in result.candidates
            ]
        }
    )


@router.get("/agent/events", response_model=AgentEventListResponse)
def list_agent_events(
    since: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=50, ge=1, le=100),
    repository: SimulationReadRepository = Depends(get_simulations),
) -> AgentEventListResponse:
    require_simulations(repository)
    try:
        events, cursor = repository.list_agent_events(CursorParameters(since=since, limit=limit))
    except ValueError as exc:
        raise ApiError(422, "invalid_cursor", str(exc)) from exc
    return AgentEventListResponse(events=events, cursor=cursor)


# ─── Simulation review ──────────────────────────────────────────────────────────


def _guard_gates_from_checks(checks: list[dict[str, object]]) -> list[GuardGateResult]:
    """Translate the raw ``policy_result["checks"]`` rows into ``GuardGateResult``."""
    rows: list[GuardGateResult] = []
    for check in checks:
        if not isinstance(check, dict):
            continue
        gate_id = str(check.get("gate") or "")
        if not gate_id:
            continue
        passed = check.get("passed", False)
        if passed is True:
            status: Literal["passed", "failed", "not_run"] = "passed"
        elif passed is False:
            status = "failed"
        else:
            status = "not_run"
        rows.append(
            GuardGateResult(
                gate_id=gate_id,
                status=status,
                message=str(check.get("detail") or ""),
            )
        )
    return rows


def _authorization_from_token(token: SignedAuthorization | None) -> CommitAuthorizationReceipt:
    """Map a ``SignedAuthorization`` to the receipt the DCG card renders."""
    if token is None:
        return CommitAuthorizationReceipt(status="none")
    now = datetime.now(timezone.utc)
    status: Literal["none", "requested", "redeemed", "expired"] = "redeemed"
    if token.expiry < now:
        status = "expired"
    return CommitAuthorizationReceipt(
        status=status,
        issued_at=token.issued_at,
        expires_at=token.expiry,
        action_count=len(token.action_hashes),
        action_hashes=list(token.action_hashes),
        binding_id=token.context_hash,
    )


# Reason reported by candidates the guard did not evaluate. The guard runs
# exactly once per simulation, against the chosen decision; every other
# candidate is an alternative the guard never saw.
NOT_EVALUATED_REASON = "not_evaluated"


def _guard_fields_for_simulation(
    simulation_id: str,
    decisions: DecisionSource,
    audit: GuardAuditSink,
) -> tuple[str, dict[str, object]] | None:
    """Evaluated candidate id and latest guard summary fields, or None if no decision ran yet.

    The returned ``candidate_id`` matches the guard's ``decision.decision_id``;
    the candidates route uses it to bind the verdict to the one candidate the
    guard actually evaluated, leaving every other candidate at
    :data:`NOT_EVALUATED_REASON` defaults.
    """
    decision = decisions.get_for_simulation(simulation_id) if decisions.available else None
    if decision is None:
        return None
    events: list[GuardAuditEvent] = audit.events(decision.decision_id) if hasattr(audit, "events") else []
    if not events:
        return None
    latest = events[-1]
    checks = list(getattr(latest, "gate_checks", []) or [])
    now = datetime.now(timezone.utc)
    freshness_seconds = max(0, int((now - decision.context_timestamp).total_seconds()))
    # The binding id is the context hash the guard allowed. The token was
    # consumed at commit time, so the rest of the receipt stays at defaults
    # here; the approve response carries the full receipt.
    binding_id = latest.context_hash if latest.context_hash else None
    fields: dict[str, object] = {
        "guard_verdict": latest.verdict,
        "guard_reason": latest.reason_code,
        "guard_gates": _guard_gates_from_checks(checks),
        "decision_context_version": decision.context_version,
        "decision_context_timestamp": decision.context_timestamp,
        "freshness_seconds": freshness_seconds,
    }
    if binding_id is not None:
        fields["authorization"] = CommitAuthorizationReceipt(
            status="none",
            binding_id=binding_id,
        )
    return decision.decision_id, fields


def _not_evaluated_candidate(candidate: SimulationCandidateResponse) -> SimulationCandidateResponse:
    """Reset the DCG fields on a candidate the guard never saw.

    The verdict is bound only to the candidate the guard actually evaluated.
    Alternatives must read as ``verdict=None``, ``reason="not_evaluated"``,
    ``gates=[]`` and ``authorization=None`` so the FE card never paints an
    authorization on a plan that was never authorized.
    """
    return candidate.model_copy(
        update={
            "guard_verdict": None,
            "guard_reason": NOT_EVALUATED_REASON,
            "guard_gates": [],
            "decision_context_version": None,
            "decision_context_timestamp": None,
            "freshness_seconds": None,
            "authorization": None,
        }
    )


def _with_guard_summary(
    detail: SimulationDetail,
    decisions: DecisionSource,
    audit: GuardAuditSink,
) -> SimulationDetail:
    """Return ``detail`` with DCG visualization fields populated when available."""
    summary = _guard_fields_for_simulation(detail.simulation_id, decisions, audit)
    if summary is None:
        return detail
    _, fields = summary
    return detail.model_copy(update=fields)


def get_review_audit(request: Request) -> ReviewAuditLog:
    return request.app.state.review_audit


def get_live_version(request: Request) -> str:
    return request.app.state.live_context_version


def get_commits(request: Request) -> CommitService | None:
    return request.app.state.commits


# A refused approval reports the guard's verdict with one of these review reasons.
_REVIEW_REASON = {
    DCGVerdict.REFRESH_REQUIRED: DecisionReviewReasonCode.VERSION_STALE,
    DCGVerdict.DENY: DecisionReviewReasonCode.DCG_DENY,
    DCGVerdict.HUMAN_REVIEW: DecisionReviewReasonCode.DCG_HUMAN_REVIEW,
}


def _version_mismatch(
    simulation_id: str, body: SimulationReviewRequest, decision: Literal["approved", "rejected"], live_version: str
) -> SimulationReviewResponse | None:
    """Refuse a review of a proposal built on a Live state that has since moved."""
    if body.base_context_version == live_version:
        return None
    logger.warning(
        "simulation_review.version_mismatch",
        extra={
            "simulation_id": simulation_id,
            "decision": decision,
            "base_context_version": body.base_context_version,
            "live_context_version": live_version,
        },
    )
    return SimulationReviewResponse(
        simulation_id=simulation_id,
        decision=decision,
        status="pending",
        verdict=DecisionReviewVerdict.REFRESH_REQUIRED,
        reason_code=DecisionReviewReasonCode.VERSION_MISMATCH,
        live_context_version=live_version,
    )


def _open_simulation(
    simulation_id: str, decision: Literal["approved", "rejected"], simulations: SimulationReadRepository, live_version: str
) -> SimulationDetail | SimulationReviewResponse:
    item = simulations.get_simulation(simulation_id)
    if item is None:
        raise ApiError(404, "simulation_not_found", f"Simulation {simulation_id!r} was not found.")
    if item.status in ("pending", "evaluated"):
        return item
    logger.warning(
        "simulation_review.not_open",
        extra={"simulation_id": simulation_id, "decision": decision, "current_status": item.status},
    )
    return SimulationReviewResponse(
        simulation_id=simulation_id,
        decision=decision,
        status=item.status,
        verdict=DecisionReviewVerdict.DENY,
        reason_code=DecisionReviewReasonCode.SIMULATION_NOT_OPEN,
        live_context_version=live_version,
    )


def _record(
    audit: ReviewAuditLog, body: SimulationReviewRequest, response: SimulationReviewResponse
) -> SimulationReviewResponse:
    audit.record(
        simulation_id=response.simulation_id,
        decision=response.decision,
        base_context_version=body.base_context_version,
        proposal_context_version=body.proposal_context_version,
        live_context_version=response.live_context_version,
        verdict=response.verdict,
        reason_code=response.reason_code,
    )
    logger.info(
        "simulation_review.%s",
        response.decision,
        extra={
            "simulation_id": response.simulation_id,
            "verdict": response.verdict.value,
            "reason_code": response.reason_code.value,
            "detail_code": response.detail_code,
            "live_context_version": response.live_context_version,
        },
    )
    return response


@router.post(
    "/simulations/{simulation_id}/approve",
    response_model=SimulationReviewResponse,
    status_code=200,
)
def approve_simulation(
    request: Request,
    simulation_id: str,
    body: SimulationReviewRequest,
    repository: SimulationReadRepository = Depends(get_simulations),
    store: StoreReader = Depends(get_store),
    audit: ReviewAuditLog = Depends(get_review_audit),
    live_version: str = Depends(get_live_version),
    decisions: DecisionSource = Depends(get_decisions),
    commits: CommitService | None = Depends(get_commits),
) -> SimulationReviewResponse:
    """Approve a simulation: the guard decides on fresh Live reads and only ALLOW commits.

    Version precheck, then the simulation's Decision, then DCG, a signed
    single-use authorization and the guarded Executor. Live changes only on ALLOW.
    """
    require_simulations(repository)
    refused = _version_mismatch(simulation_id, body, "approved", live_version)
    if refused is not None:
        return refused
    item = _open_simulation(simulation_id, "approved", repository, live_version)
    if isinstance(item, SimulationReviewResponse):
        return item
    if commits is None or not commits.can_commit:
        raise ApiError(503, "commit_unavailable", "No Live Twin commit path is configured.")
    if not decisions.available:
        raise ApiError(503, "decisions_unavailable", "The decision store is not available.")

    decision = decisions.get_for_simulation(simulation_id)
    if decision is None or decision.simulation_id not in (None, simulation_id):
        return _record(
            audit,
            body,
            SimulationReviewResponse(
                simulation_id=simulation_id,
                decision="approved",
                status=item.status,
                verdict=DecisionReviewVerdict.DENY,
                reason_code=DecisionReviewReasonCode.DECISION_UNAVAILABLE,
                live_context_version=live_version,
            ),
        )

    outcome = commits.approve(decision)
    receipt = _authorization_from_token(outcome.token)
    if outcome.committed:
        repository.set_status(simulation_id, "committed", datetime.now(timezone.utc))
        request.app.state.live_context_version = store.view().context_version
        return _record(
            audit,
            body,
            SimulationReviewResponse(
                simulation_id=simulation_id,
                decision="approved",
                status="committed",
                verdict=DecisionReviewVerdict.ALLOW,
                reason_code=DecisionReviewReasonCode.APPROVED,
                live_context_version=request.app.state.live_context_version,
                detail_code=outcome.reason_code,
                guard=outcome.guard,
                binding_id=receipt.binding_id,
                expires_at=receipt.expires_at,
                action_hashes=receipt.action_hashes,
            ),
        )
    failed = outcome.commit is not None and outcome.commit.status == "failed"
    return _record(
        audit,
        body,
        SimulationReviewResponse(
            simulation_id=simulation_id,
            decision="approved",
            status=item.status,
            verdict=DecisionReviewVerdict(outcome.verdict.value),
            reason_code=DecisionReviewReasonCode.EXECUTION_FAILED if failed else _REVIEW_REASON[outcome.verdict],
            live_context_version=live_version,
            detail_code=outcome.reason_code,
            guard=outcome.guard,
            binding_id=receipt.binding_id,
            expires_at=receipt.expires_at,
            action_hashes=receipt.action_hashes,
        ),
    )


@router.post(
    "/simulations/{simulation_id}/reject",
    response_model=SimulationReviewResponse,
    status_code=200,
)
def reject_simulation(
    simulation_id: str,
    body: SimulationReviewRequest,
    repository: SimulationReadRepository = Depends(get_simulations),
    audit: ReviewAuditLog = Depends(get_review_audit),
    live_version: str = Depends(get_live_version),
) -> SimulationReviewResponse:
    """Reject a simulation: nothing reaches the guard or the Live Twin."""
    require_simulations(repository)
    refused = _version_mismatch(simulation_id, body, "rejected", live_version)
    if refused is not None:
        return refused
    item = _open_simulation(simulation_id, "rejected", repository, live_version)
    if isinstance(item, SimulationReviewResponse):
        return item
    repository.set_status(simulation_id, "rejected", datetime.now(timezone.utc))
    return _record(
        audit,
        body,
        SimulationReviewResponse(
            simulation_id=simulation_id,
            decision="rejected",
            status="rejected",
            verdict=DecisionReviewVerdict.ALLOW,
            reason_code=DecisionReviewReasonCode.APPROVED,
            live_context_version=live_version,
        ),
    )
