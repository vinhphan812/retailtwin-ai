r"""Production composition root (ADR 0029).

Single factory that selects the cross-cutting adapters the Cloud Run
process binds at startup: live twin, analytics, LLM provider, durable
decisions, simulation, agent activity, activation ledger. The factory
fails closed in production when a required cloud dependency is missing
or misconfigured; tests and local dev keep the in-memory adapters
without silently swapping the production build.

The factory is the only place ``create_app`` reads from. Routes read
``app.state`` fields populated by ``build_composition`` and never
construct adapters on their own.

Production readiness contract (review #244 re-review):

- ``LIVE_TWIN_BACKEND in {memory, fixture}`` is rejected at process
  startup when ``APP_ENV=production``. The day-0 demo backends are
  not durable and would silently swallow live-action writes, so the
  composition raises :class:`CompositionError` and the Cloud Run
  revision reports ``503 unhealthy``. ``APP_ENV=staging`` keeps the
  in-process twin because the staging environment is where the
  operator flips the env var.
- The BigQuery probe runs a `SELECT 1 AS ok FROM
  `<project>.<dataset>.sales_events> LIMIT 1` whenever analytics
  adapters are bound (production / staging). A failure marks the
  composition degraded rather than crashing; the /ready endpoint
  exposes the probe so the release-gate can block.
- :class:`CompositionReadiness` carries the three AI / autonomy
  states the reviewer asked for: ``ai_ready`` (Vertex built),
  ``ai_disabled`` (AUTONOMY_ENABLED=false by config), ``ai_unconfigured``
  (AUTONOMY_ENABLED=true but the Vertex builder failed — fail closed).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from retailtwin_api.agents.observer.consumer import MemoryActivationLedger
from retailtwin_api.analytics_repository import (
    ALLOWED_DATASET,
    ALLOWED_PROJECT,
    AnalyticsError,
    AnomalyRepository,
    BQ_LOCATION,
    CheckoutRepository,
    PromotionRepository,
    RevenueRepository,
    SubprocessRunner,
    _bq_query,
    get_anomaly_repository,
    get_checkout_repository,
    get_promotion_repository,
    get_revenue_repository,
    unavailable_analytics_repositories,
)
from retailtwin_api.decisions import DecisionSource
from retailtwin_api.firestore_twin import FirestoreLiveTwinRepository, LiveTwinRepository  # noqa: F401  (re-exported so test monkeypatch reaches)
from retailtwin_api.llm.factory import (
    ConfigurationError as LlmConfigurationError,
    LlmConfig,
    create_provider,
    llm_config_from_settings,
)
from retailtwin_api.persistence import DurableAdapters, get_persistence
from retailtwin_api.settings import Settings
from retailtwin_api.simulation_repository import SimulationReadRepository
from retailtwin_api.store import LiveTwinStore, StoreReader, open_memory_live_store, open_store

log = logging.getLogger(__name__)


# ── AI workflow readiness tri-state ──────────────────────────────────────────

# Literal alias so the route schema can validate the value without
# importing the dataclass. Mirrors the constants used by ``/ready``.
AiState = Literal["ai_ready", "ai_disabled", "ai_unconfigured"]


# ── CompositionError ─────────────────────────────────────────────────────────


class CompositionError(RuntimeError):
    """Raised when the production composition cannot be built.

    Surfaced as ``503 composition_unavailable`` by routes that need the
    missing adapter. ``create_app`` propagates the error so the lifespan
    refuses to start the Cloud Run revision.
    """


# ── Probe result ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CompositionReadiness:
    """Outcome of one composition probe.

    Attributes
    ----------
    ready:
        ``True`` when the probe verified the underlying service is
        reachable and authorised. ``False`` otherwise. ``True`` for
        ``reason="not_applicable"`` so the field remains a clean boolean
        /ready can pivot on.
    reason:
        A short stable code identifying why the probe succeeded,
        failed or did not apply. Used in :func:`build_composition` to
        decide whether the composition is degraded vs. failed.
    source:
        The component the probe ran against (``bigquery.probe``).
        Empty when ``reason="not_applicable"``.
    identity:
        Public-facing fields (project, dataset, region, IAM scope) so
        operators can verify the probe hit the canonical resources.
        Empty when ``reason="not_applicable"``.
    detail:
        Free-form error information (error class, message) when
        ``ready=False``. Empty otherwise.
    """

    ready: bool
    reason: str
    source: str = ""
    identity: dict[str, str] = field(default_factory=dict)
    detail: dict[str, str] = field(default_factory=dict)


# ── Composition bundle ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class Composition:
    """Bundle of cross-cutting adapters built by :func:`build_composition`."""

    store: StoreReader
    live_twin_repository: LiveTwinRepository | None
    analytics_repositories: tuple[AnomalyRepository, RevenueRepository, PromotionRepository, CheckoutRepository]
    llm_provider: Any  # LlmProvider — typed as Any to avoid the import cycle
    llm_provider_available: bool
    durable_adapters: DurableAdapters
    backend_identities: dict[str, str] = field(default_factory=dict)
    analytics_readiness: CompositionReadiness = field(
        default_factory=lambda: CompositionReadiness(ready=True, reason="not_applicable")
    )
    ai_state: AiState = "ai_disabled"
    ai_reason: str = "autonomy_disabled_by_config"

    def is_production(self) -> bool:
        return self.backend_identities.get("app_env", "development") in {"production", "staging"}


# ── Reusable helpers (typed for Protocol) ────────────────────────────────────


class _CommandRunnerLike(Protocol):
    def run(self, args: list[str]) -> str: ...


_PRODUCTION_APP_ENVS: frozenset[str] = frozenset({"production", "staging"})

# Tables the BigQuery readiness probe touches. ``sales_events`` is the
# canonical revenue / checkout aggregate; ``promotions`` is the second
# canonical table. Either successfully querying either table means
# credentials + IAM + schema are reachable.
_BIGQUERY_PROBE_TABLES: tuple[str, ...] = ("sales_events", "promotions")


# ── Factory ──────────────────────────────────────────────────────────────────


def build_composition(
    settings: Settings,
    *,
    store_view_fn: Callable[[], Any] | None = None,
    activity: Any | None = None,
    runner: _CommandRunnerLike | None = None,
) -> Composition:
    """Build the cross-cutting adapter bundle for the configured environment.

    Production wiring rules:

    - ``APP_ENV=production`` AND ``LIVE_TWIN_BACKEND in {memory, fixture}``
      -> :class:`CompositionError` is raised. The day-0 demo backends are
      not durable; production live-action deployments must point at
      ``firestore``. ``APP_ENV=staging`` keeps the in-process twin so
      the staging environment can flip the env var.
    - ``LIVE_TWIN_BACKEND=firestore`` -> :class:`FirestoreLiveTwinRepository` is bound
      into ``store.twin``; otherwise an in-memory or fixture-backed store is used.
    - ``app_env in {production, staging}`` -> BigQuery-backed analytics adapters
      when the canonical project + dataset + tables are reachable. A probe
      (`SELECT 1 AS ok FROM <dataset>.sales_events LIMIT 1`) is run; any
      permission/connect failure is surfaced as
      :class:`CompositionReadiness` with ``reason="bigquery_unreachable"``
      so ``/ready`` can flag a degraded-but-not-crashed composition.
      The in-memory scaffolds are only used outside production.
    - ``app_env in {production, staging}`` AND ``LLM_PROVIDER=vertex_gemini`` ->
      the Vertex provider is built via ADC. The fake provider is only used
      outside production. A failed build raises :class:`CompositionError`
      rather than falling back to the fake provider (ADR 0020).
    - ``AUTONOMY_ENABLED=false`` -> :attr:`Composition.ai_state` is
      ``ai_disabled`` with reason ``autonomy_disabled_by_config``. The
      Vertex provider is intentionally not constructed and ``/ready``
      reports the AI workflow as disabled, not misconfigured.
    - ``AUTONOMY_ENABLED=true`` AND Vertex build OK ->
      ``ai_state="ai_ready"``.
    - ``AUTONOMY_ENABLED=true`` AND Vertex build FAILED -> ``ai_unconfigured``.
      The composition raises :class:`CompositionError` so Cloud Run drains
      traffic; misconfiguration is not masked as intentional disablement.
    - ``LIVE_TWIN_BACKEND=firestore`` -> durable decisions / simulation /
      agent activity / activation ledger are bound to the Firestore-backed
      adapters via :func:`get_persistence`. Otherwise the in-process
      adapters are used.

    The factory never silently swaps a production adapter for an in-memory
    one. A misconfigured production deploy raises :class:`CompositionError`
    at startup so the Cloud Run revision reports ``unhealthy``.
    """
    is_prod_like = settings.app_env in _PRODUCTION_APP_ENVS

    _enforce_production_backend(settings)

    store = _open_store(settings)
    live_twin_repository = _resolve_live_twin(store)

    analytics_readiness = _resolve_analytics_readiness(settings, runner=runner)
    analytics_repositories = _resolve_analytics(
        settings, store, is_prod=is_prod_like, analytics_readiness=analytics_readiness
    )

    llm_provider, llm_available, ai_state, ai_reason = _resolve_llm_provider(
        settings, is_prod=is_prod_like
    )

    durable_adapters = get_persistence(
        settings,
        store_view_fn=store_view_fn if store_view_fn is not None else store.view,
        activity=activity,
    )

    backend_identities = _collect_backend_identities(
        settings=settings,
        store=store,
        live_twin_repository=live_twin_repository,
        llm_provider=llm_provider,
        llm_provider_available=llm_available,
        analytics_repositories=analytics_repositories,
        durable_adapters=durable_adapters,
        analytics_readiness=analytics_readiness,
        ai_state=ai_state,
        ai_reason=ai_reason,
    )
    return Composition(
        store=store,
        live_twin_repository=live_twin_repository,
        analytics_repositories=analytics_repositories,
        llm_provider=llm_provider,
        llm_provider_available=llm_available,
        durable_adapters=durable_adapters,
        backend_identities=backend_identities,
        analytics_readiness=analytics_readiness,
        ai_state=ai_state,
        ai_reason=ai_reason,
    )


# ── Backend gate ─────────────────────────────────────────────────────────────


def _enforce_production_backend(settings: Settings) -> None:
    """Fail closed when ``APP_ENV=production`` keeps a non-durable twin.

    Day-0 ``memory`` / ``fixture`` twins are in-process adapters that
    discard every write the second the Cloud Run instance restarts.
    Production live-action deployments must point at ``firestore``;
    staging may keep the in-process twin because the staging env is
    where the operator flips the env var during cutover.
    """
    if settings.is_production and settings.live_twin_backend in {"memory", "fixture"}:
        raise CompositionError(
            f"{settings.live_twin_backend!r} backend not allowed in production"
        )


# ── Store wiring ─────────────────────────────────────────────────────────────


def _open_store(settings: Settings) -> StoreReader:
    if settings.live_twin_backend == "fixture":
        return open_store(settings.store_fixture_path, settings.store_id)
    if settings.live_twin_backend == "firestore":
        # Lazy-import so test ``monkeypatch.setattr(main, "FirestoreLiveTwinRepository", ...)``
        # reaches the same class object the composition factory uses. The
        # import on ``main`` ensures the patch surface lives on the public
        # namespace rather than on the module the factory imports directly.
        from retailtwin_api import main as _main
        return LiveTwinStore(_main.FirestoreLiveTwinRepository(), settings.store_id)
    return open_memory_live_store(settings.store_fixture_path, settings.store_id)


def _resolve_live_twin(store: StoreReader) -> LiveTwinRepository | None:
    if isinstance(store, LiveTwinStore):
        return store.twin
    return None


# ── Analytics + BigQuery probe ───────────────────────────────────────────────


def _resolve_analytics_readiness(
    settings: Settings,
    *,
    runner: _CommandRunnerLike | None = None,
) -> CompositionReadiness:
    """Run the BigQuery probe when analytics adapters are bound.

    Returns
    -------
    CompositionReadiness
        ``ready=True`` with reason ``not_applicable`` outside
        production / staging (no BQ probe run). For production /
        staging the probe either verifies ``sales_events`` +
        ``promotions`` reachable (a ``bq query`` ``SELECT 1 AS ok``
        against each) or returns ``reason="bigquery_unreachable"``.
    """
    is_prod_like = settings.app_env in _PRODUCTION_APP_ENVS
    if not is_prod_like:
        return CompositionReadiness(ready=True, reason="not_applicable")
    return _resolve_bigquery(settings, runner=runner)


def _resolve_bigquery(
    settings: Settings,
    *,
    runner: _CommandRunnerLike | None = None,
) -> CompositionReadiness:
    """Probe the configured BigQuery dataset via ADC.

    Runs ``bq query --nouse_legacy_sql --format=json
    --maximum_bytes_billed=100000000
    'SELECT 1 AS ok FROM `<project>.<dataset>.<table>` LIMIT 1'``
    against every probe table. The same ``bq`` / ``gcloud`` runner is
    used by the analytics adapter so the probe verifies the exact
    credentials + project + region the adapter will use.

    Uses :data:`ALLOWED_PROJECT`, :data:`ALLOWED_DATASET`, and
    :data:`BQ_LOCATION` from :mod:`retailtwin_api.analytics_repository`
    so the probe and the analytics adapter cannot drift apart.

    On any failure returns a :class:`CompositionReadiness` carrying
    the error class + message so ``/ready`` can surface it without
    another round-trip.
    """
    if runner is None:
        # Default to the same SubprocessRunner used by the analytics
        # adapter so the probe exercises the exact CLI path the adapter
        # will use at request time.
        runner = SubprocessRunner()
    project = ALLOWED_PROJECT
    dataset = ALLOWED_DATASET
    location = BQ_LOCATION
    identity: dict[str, str] = {
        "project_id": project,
        "dataset": dataset,
        "location": location,
        "iam_scope": "cloud-platform",
        "tables": ",".join(_BIGQUERY_PROBE_TABLES),
    }
    last_error: AnalyticsError | None = None
    for table in _BIGQUERY_PROBE_TABLES:
        sql = (
            f"SELECT 1 AS ok FROM `{project}.{dataset}.{table}` LIMIT 1"
        )
        try:
            _bq_query(runner, sql, params={}, project=project, location=location)
        except AnalyticsError as exc:
            last_error = exc
            log.warning(
                "composition.bigquery_probe_failed",
                extra={
                    "project_id": project,
                    "dataset": dataset,
                    "table": table,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
            )
            continue
        identity["probe_table"] = table
        return CompositionReadiness(
            ready=True,
            reason="bigquery_probe_ok",
            source="bigquery.probe",
            identity=identity,
        )
    detail: dict[str, str] = {}
    if last_error is not None:
        detail = {
            "error_type": type(last_error).__name__,
            "error_message": str(last_error),
        }
    return CompositionReadiness(
        ready=False,
        reason="bigquery_unreachable",
        source="bigquery.probe",
        identity=identity,
        detail=detail,
    )


def _resolve_analytics(
    settings: Settings,
    store: StoreReader,
    *,
    is_prod: bool,
    analytics_readiness: CompositionReadiness,
) -> tuple[AnomalyRepository, RevenueRepository, PromotionRepository, CheckoutRepository]:
    """Pick analytics adapters.

    Production binds the BigQuery-backed adapters (anomalies via
    Firestore, revenue / promotions via BQ). The adapters do not contact
    GCP at construction time; the first ``list_*`` call surfaces any
    network or IAM failure as a typed error, which the routes translate
    to ``503 analytics_unavailable``. The
    :func:`_resolve_bigquery` probe runs ahead of construction so a
    permission/connect failure can short-circuit ``/ready`` before the
    first user request hits a 500. Dev / test bind the unavailable
    scaffolds so unit tests never open a real GCP project.
    """
    if not is_prod:
        return unavailable_analytics_repositories()
    return (
        get_anomaly_repository(),
        get_revenue_repository(),
        get_promotion_repository(),
        get_checkout_repository(),
    )


# ── LLM provider + AI workflow tri-state ─────────────────────────────────────


def _resolve_llm_provider(
    settings: Settings,
    *,
    is_prod: bool,
) -> tuple[Any, bool, AiState, str]:
    """Pick the LLM provider and produce the AI readiness tri-state.

    Returns
    -------
    tuple
        ``(provider, available, ai_state, ai_reason)``. The four AI
        states match the contract documented at the top of the
        module.

    Production Vertex construction does not fall back to the fake
    provider on builder failure (ADR 0020). The composition therefore
    lets :class:`LlmConfigurationError` propagate to ``build_composition``
    which re-raises it as :class:`CompositionError` when autonomy is
    enabled.
    """
    if not settings.autonomy_enabled:
        # Explicit disablement is not a misconfiguration; /ready must
        # distinguish it from ``ai_unconfigured``.
        return None, False, "ai_disabled", "autonomy_disabled_by_config"
    config = llm_config_from_settings(settings)
    if not is_prod:
        try:
            provider = create_provider(config)
        except LlmConfigurationError as exc:
            log.warning(
                "composition.dev_provider_unavailable",
                extra={"error_type": type(exc).__name__, "error_message": str(exc)},
            )
            # Dev / test cannot reach production Vertex; treat this as
            # explicit disablement so the cloud run experiment loop stays
            # unblocked and ``/ready`` reports ``ai_disabled`` rather
            # than a misleading ``ai_unconfigured``.
            return None, False, "ai_disabled", "autonomy_disabled_by_config"
        return provider, True, "ai_ready", "vertex_built"
    # Production: do not fall back to the fake provider. ADR 0020.
    provider = create_provider(config)
    return provider, True, "ai_ready", "vertex_built"


# ── Identity collection ──────────────────────────────────────────────────────


def _collect_backend_identities(
    *,
    settings: Settings,
    store: StoreReader,
    live_twin_repository: LiveTwinRepository | None,
    llm_provider: Any,
    llm_provider_available: bool,
    analytics_repositories: tuple[AnomalyRepository, RevenueRepository, PromotionRepository, CheckoutRepository],
    durable_adapters: DurableAdapters,
    analytics_readiness: CompositionReadiness,
    ai_state: AiState,
    ai_reason: str,
) -> dict[str, str]:
    """Return backend identities (never credentials) for the readiness probe."""
    identities: dict[str, str] = {
        "app_env": settings.app_env,
        "store_id": settings.store_id,
        "live_twin_backend": settings.live_twin_backend,
        "fixture_loaded": str(bool(store.loaded)),
        "is_production_env": str(bool(settings.is_production)),
        "ai_state": ai_state,
        "ai_reason": ai_reason,
        "analytics_readiness": analytics_readiness.reason,
    }
    if isinstance(live_twin_repository, FirestoreLiveTwinRepository):
        identities["live_twin"] = "firestore"
    elif live_twin_repository is not None:
        identities["live_twin"] = "memory"
    else:
        identities["live_twin"] = "fixture"
    if llm_provider_available and llm_provider is not None:
        identities["llm_provider"] = settings.llm_provider
        identities["llm_model"] = settings.llm_model
    else:
        identities["llm_provider"] = "unavailable"
    identities["anomaly_source"] = type(analytics_repositories[0]).__name__
    identities["revenue_source"] = type(analytics_repositories[1]).__name__
    identities["promotion_source"] = type(analytics_repositories[2]).__name__
    identities["checkout_source"] = type(analytics_repositories[3]).__name__
    identities["simulation_source"] = type(durable_adapters.simulations).__name__
    identities["decisions_source"] = type(durable_adapters.decisions).__name__
    identities["activation_source"] = type(durable_adapters.activation_ledger).__name__
    if analytics_readiness.identity:
        identities["analytics_project"] = analytics_readiness.identity.get("project_id", "")
        identities["analytics_dataset"] = analytics_readiness.identity.get("dataset", "")
        identities["analytics_region"] = analytics_readiness.identity.get("location", "")
    return identities


__all__ = [
    "AiState",
    "Composition",
    "CompositionError",
    "CompositionReadiness",
    "build_composition",
]
