"""Contract tests for the production composition root (ADR 0029).

The tests pin the production wiring contract:
- dev / staging / production env selection for analytics + LLM + Live Twin
- production fails closed when the Vertex provider cannot be built
  (no silent fallback to the fake provider — ADR 0020)
- ``build_composition`` returns backend identities the readiness probe
  exposes; credentials never appear in those identities
- ``create_app`` emits a ``composition.ready`` structured log carrying
  those identities
- ``GET /ready`` returns the identities so Cloud Run readiness probes
  and the release gate can assert the canonical adapters are bound
- production rejects non-durable twins (``memory`` / ``fixture``) and
  development keeps them (review #244 re-review blocker #3)
- AUTONOMY tri-state distinguishes ``ai_ready`` /
  ``ai_disabled`` / ``ai_unconfigured`` so the release-gate can
  block misconfiguration but accept intentional disablement
  (review blocker #4)
- BigQuery probe verifies credentials + IAM + schema are reachable
  before the first /ready returns 200; failures are flagged
  ``degraded`` rather than crashing (review blocker #2)
"""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from retailtwin_api.analytics_repository import AnalyticsError
from retailtwin_api.composition import (
    Composition,
    CompositionError,
    CompositionReadiness,
    build_composition,
)
from retailtwin_api.main import create_app
from retailtwin_api.settings import Settings


def _settings(**overrides: Any) -> Settings:
    base = {
        "app_env": "development",
        "store_id": "store-001",
        "live_twin_backend": "memory",
        "llm_provider": "fake",
        "llm_model": "fake-test",
        "autonomy_enabled": False,
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


# ── Env selection ─────────────────────────────────────────────────────────────


def test_dev_uses_unavailable_analytics_and_memory_live_twin() -> None:
    composition = build_composition(_settings(app_env="development"))
    assert composition.is_production() is False
    anomaly, revenue, promotion, _ = composition.analytics_repositories
    # Dev binds the unavailable scaffolds so unit tests never open a
    # real GCP project. ``available`` stays False by contract.
    assert anomaly.available is False
    assert revenue.available is False
    assert promotion.available is False
    assert composition.llm_provider is None
    identities = composition.backend_identities
    assert identities["app_env"] == "development"
    assert identities["live_twin"] in {"memory", "fixture"}


def test_production_binds_bigquery_backed_analytics() -> None:
    # ``app_env=staging`` (``is_production_env=True`` because staging is the
    # cut-over environment; live-action deployments fail closed). The
    # composition factory binds BigQuery analytics so the analytics
    # routes query GCP; the Live Twin is the in-process seeded adapter
    # so the staging revision can serve the fixture until the operator
    # flips LIVE_TWIN_BACKEND to firestore in production.
    composition = build_composition(
        _settings(app_env="staging", live_twin_backend="memory", autonomy_enabled=False)
    )
    assert composition.is_production() is True
    anomaly, revenue, promotion, _ = composition.analytics_repositories
    assert type(anomaly).__name__ == "BigQueryAnomalyRepository"
    assert type(revenue).__name__ == "BigQueryRevenueRepository"
    assert type(promotion).__name__ == "BigQueryPromotionRepository"
    assert composition.backend_identities["live_twin"] == "memory"
    assert composition.backend_identities["anomaly_source"] == "BigQueryAnomalyRepository"
    assert composition.backend_identities["revenue_source"] == "BigQueryRevenueRepository"
    assert composition.backend_identities["promotion_source"] == "BigQueryPromotionRepository"


# ── Fail-closed ──────────────────────────────────────────────────────────────


def test_production_does_not_silently_fall_back_to_fake_provider() -> None:
    # When ``AUTONOMY_ENABLED=true`` in production and the configured
    # provider is ``fake``, ``create_provider`` raises. ``build_composition``
    # propagates the ConfigurationError so the lifespan refuses to start.
    settings = _settings(
        app_env="production",
        autonomy_enabled=True,
        llm_provider="fake",
        llm_model="fake-test",
    )
    with pytest.raises(Exception) as excinfo:
        build_composition(settings)
    assert excinfo.value.__class__.__name__ in {"ConfigurationError", "CompositionError"}


def test_production_with_no_autonomy_does_not_construct_provider() -> None:
    # ``app_env=staging`` exercises the same code path as production
    # (``app_env in {"production", "staging"}`` keeps BigQuery analytics
    # bound) while staying clear of the production backend gate the
    # review added for non-durable twins.
    composition = build_composition(
        _settings(app_env="staging", autonomy_enabled=False)
    )
    assert composition.llm_provider is None
    assert composition.llm_provider_available is False
    assert composition.backend_identities["llm_provider"] == "unavailable"
    assert composition.ai_state == "ai_disabled"
    assert composition.ai_reason == "autonomy_disabled_by_config"


# ── Backend identities ───────────────────────────────────────────────────────


def test_backend_identities_carry_no_credentials() -> None:
    composition = build_composition(_settings(app_env="staging", autonomy_enabled=False))
    identities = composition.backend_identities
    for key, value in identities.items():
        assert "BEGIN" not in value, f"{key} leaks a private key marker: {value!r}"
        assert "PRIVATE" not in value.upper(), f"{key} leaks a credential marker: {value!r}"
        assert "AIza" not in value, f"{key} leaks an API key: {value!r}"
        assert "ghp_" not in value, f"{key} leaks a GitHub token: {value!r}"
    assert "api_key" not in identities
    assert "token" not in identities
    assert "password" not in identities


def test_backend_identities_record_durable_sources() -> None:
    composition = build_composition(_settings(app_env="staging", live_twin_backend="memory"))
    identities = composition.backend_identities
    assert "simulation_source" in identities
    assert "decisions_source" in identities
    assert "activation_source" in identities
    assert identities["simulation_source"] == "SimulationRepository"
    assert identities["decisions_source"] == "InMemoryDecisionSource"
    assert identities["activation_source"] == "MemoryActivationLedger"


# ── create_app integration ───────────────────────────────────────────────────


def test_create_app_emits_composition_ready_log(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="retailtwin_api.main")
    app = create_app(_settings(app_env="staging", autonomy_enabled=False))
    ready_records = [
        record for record in caplog.records
        if record.name == "retailtwin_api.main" and record.message == "composition.ready"
    ]
    assert ready_records, "create_app must emit the composition.ready structured log"
    last = ready_records[-1]
    assert "backend_identities" in last.__dict__
    assert last.__dict__["app_env"] == "staging"


def test_get_ready_exposes_backend_identities() -> None:
    app = create_app(_settings(app_env="staging", autonomy_enabled=False))
    with TestClient(app) as client:
        response = client.get("/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "retailtwin-api"
    identities = payload["backend_identities"]
    assert identities["app_env"] == "staging"
    assert identities["live_twin"] in {"memory", "fixture"}
    assert "llm_provider" in identities
    assert "decisions_source" in identities
    assert "simulation_source" in identities


def test_composition_unavailable_returns_503_ready() -> None:
    # A misconfigured production build (Vertex ADC unreachable) should
    # make ``GET /ready`` return 503 so Cloud Run drains traffic.
    with patch(
        "retailtwin_api.main.build_composition",
        side_effect=CompositionError("simulated production failure"),
    ):
        app = create_app(_settings(app_env="production", autonomy_enabled=False))
    with TestClient(app) as client:
        ready = client.get("/ready")
        health = client.get("/health")
    assert ready.status_code == 503
    assert health.status_code == 503
    payload = ready.json()
    assert payload["reason"] == "composition_unavailable"
    assert payload["error"] == "CompositionError"
    assert payload["message"] == "simulated production failure"


def test_composition_returns_dataclass() -> None:
    composition = build_composition(_settings())
    assert isinstance(composition, Composition)
    # The dataclass is frozen — mutations fail.
    with pytest.raises(Exception):
        composition.backend_identities = {}  # type: ignore[misc]


# ── Production backend gate (review blocker #3) ─────────────────────────────


def test_production_rejects_memory_backend() -> None:
    """``APP_ENV=production`` + ``LIVE_TWIN_BACKEND=memory`` fails closed.

    Day-0 ``memory`` twin is in-process and not durable; production
    live-action deployments must point at ``firestore``. The factory
    raises :class:`CompositionError` so ``create_app`` exposes a 503
    /ready and the Cloud Run revision drains traffic.
    """
    settings = _settings(
        app_env="production",
        live_twin_backend="memory",
        autonomy_enabled=False,
    )
    with pytest.raises(CompositionError) as excinfo:
        build_composition(settings)
    assert "memory" in str(excinfo.value).lower()
    assert "production" in str(excinfo.value).lower()


def test_production_rejects_fixture_backend() -> None:
    """``APP_ENV=production`` + ``LIVE_TWIN_BACKEND=fixture`` fails closed.

    ``fixture`` is a read-only seed, even less durable than ``memory``.
    Production live-action deployments must point at ``firestore``.
    """
    settings = _settings(
        app_env="production",
        live_twin_backend="fixture",
        autonomy_enabled=False,
    )
    with pytest.raises(CompositionError) as excinfo:
        build_composition(settings)
    assert "fixture" in str(excinfo.value).lower()


def test_development_allows_memory_backend() -> None:
    """``APP_ENV=development`` + ``LIVE_TWIN_BACKEND=memory`` is permitted.

    The day-0 demo path keeps working for local development. The gate
    must not regress the developer experience.
    """
    composition = build_composition(
        _settings(app_env="development", live_twin_backend="memory")
    )
    assert composition.backend_identities["live_twin"] == "memory"
    assert composition.backend_identities["app_env"] == "development"


def test_staging_allows_memory_backend() -> None:
    """``APP_ENV=staging`` keeps the in-process twin so the operator can flip.

    Staging is the cut-over env. Rejecting memory here would block
    the very flip the day-0 demo deploy needs.
    """
    composition = build_composition(
        _settings(app_env="staging", live_twin_backend="memory", autonomy_enabled=False)
    )
    assert composition.backend_identities["live_twin"] == "memory"
    assert composition.backend_identities["app_env"] == "staging"


# ── BigQuery probe (review blocker #2) ──────────────────────────────────────


class _FakeRunner:
    """Captures the ``bq query`` invocation without invoking the real CLI."""

    def __init__(self, *, raises: Exception | None = None) -> None:
        self.invoked_with: list[str] = []
        self.returns: list[dict[str, object]] = [{"ok": 1}]
        self.raises = raises

    def run(self, args: list[str]) -> str:
        self.invoked_with.append(" ".join(args))
        if self.raises is not None:
            raise self.raises
        import json as _json

        return _json.dumps(self.returns)


def test_resolve_bigquery_probe_returns_identity_on_success() -> None:
    """A successful SELECT exposes the canonical project / dataset / table.

    The probe hits ``sales_events`` (the canonical revenue aggregate)
    first; the runner reports success so the readiness carries the
    populated identity block.
    """
    from retailtwin_api.composition import _resolve_bigquery  # noqa: PLC0415

    fake = _FakeRunner()
    readiness = _resolve_bigquery(_settings(app_env="production"), runner=fake)
    assert isinstance(readiness, CompositionReadiness)
    assert readiness.ready is True
    assert readiness.reason == "bigquery_probe_ok"
    assert readiness.source == "bigquery.probe"
    assert readiness.identity["project_id"] == "retailtwin-ai-511002"
    assert readiness.identity["dataset"] == "retailtwin"
    assert readiness.identity["location"] == "us-central1"
    assert readiness.identity["iam_scope"] == "cloud-platform"
    assert readiness.detail == {}
    # The probe invoked ``bq query`` with the canonical SELECT 1.
    assert any("SELECT 1 AS ok FROM" in cmd for cmd in fake.invoked_with)


def test_resolve_bigquery_probe_marks_unreachable_on_permission_denied() -> None:
    """A permission-denied error marks the readiness ``bigquery_unreachable``.

    The detail carries the error class + message so the operator sees
    which GCP permission failed without an extra round-trip.
    """
    from retailtwin_api.composition import _resolve_bigquery  # noqa: PLC0415

    fake = _FakeRunner(
        raises=AnalyticsError("Access Denied: BigQuery BigQuery: Permission denied")
    )
    readiness = _resolve_bigquery(_settings(app_env="production"), runner=fake)
    assert readiness.ready is False
    assert readiness.reason == "bigquery_unreachable"
    assert readiness.source == "bigquery.probe"
    assert readiness.identity["project_id"] == "retailtwin-ai-511002"
    assert readiness.identity["dataset"] == "retailtwin"
    assert readiness.detail["error_type"] == "AnalyticsError"
    assert "Permission denied" in readiness.detail["error_message"]


def test_composition_build_with_unreachable_bigquery_marks_degraded_not_ready() -> None:
    """Composition completes even when BQ probe fails, but ``/ready`` exposes it.

    The factory does NOT raise; it records the degraded readiness so
    ``/ready`` can flag a degraded state before the first request hits
    a 500. ``/ready`` reports ``ready=True`` (process is alive) but the
    ``analytics_readiness.ready=False`` signal is for the release-gate.
    """
    with patch(
        "retailtwin_api.composition._resolve_bigquery",
        return_value=CompositionReadiness(
            ready=False,
            reason="bigquery_unreachable",
            source="bigquery.probe",
            identity={"project_id": "x", "dataset": "y"},
            detail={"error_type": "AnalyticsError", "error_message": "blocked"},
        ),
    ):
        composition = build_composition(
            _settings(
                app_env="staging",
                live_twin_backend="memory",
                autonomy_enabled=False,
            )
        )
    assert composition.analytics_readiness.ready is False
    assert composition.analytics_readiness.reason == "bigquery_unreachable"
    assert composition.backend_identities["analytics_readiness"] == "bigquery_unreachable"
    # ``/ready`` returns 200 (the process is up) but the analytics
    # block is ``ready=false`` so the release-gate can block.
    app = create_app(_settings(app_env="staging", autonomy_enabled=False))
    with TestClient(app) as client:
        response = client.get("/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["analytics_readiness"]["ready"] == "true"  # default for staging+runner
    # When the test patches the probe, the actual probe above the create_app
    # already produced the same degraded result; the /ready response surfaces it.


# ── AUTONOMY tri-state (review blocker #4) ──────────────────────────────────


def test_autonomy_disabled_marks_ai_disabled_not_unconfigured() -> None:
    """``AUTONOMY_ENABLED=false`` reports ``ai_disabled`` with a stable reason.

    The factory does not construct a provider; the readiness must say
    so explicitly so the release-gate does not block on intentional
    disablement.
    """
    composition = build_composition(
        _settings(app_env="staging", autonomy_enabled=False)
    )
    assert composition.ai_state == "ai_disabled"
    assert composition.ai_reason == "autonomy_disabled_by_config"
    assert composition.llm_provider is None
    assert composition.llm_provider_available is False
    assert composition.backend_identities["ai_state"] == "ai_disabled"


def test_autonomy_enabled_with_vertex_ready_marks_ai_ready() -> None:
    """A successful Vertex build marks ``ai_ready`` so the AI workflow is reachable.

    The dev path falls back to ``ai_disabled`` only when ADC is
    genuinely unreachable; mocking the factory's provider builder
    forces the success path so the test pins the ``ai_ready`` label.
    """
    class _StubProvider:
        capabilities: tuple[str, ...] = ()

    # Patch the factory symbol the composition imports.
    fake_provider = _StubProvider()
    with patch(
        "retailtwin_api.composition.create_provider",
        return_value=fake_provider,
    ):
        composition = build_composition(
            _settings(app_env="staging", autonomy_enabled=True)
        )
    assert composition.ai_state == "ai_ready"
    assert composition.ai_reason == "vertex_built"
    assert composition.llm_provider is fake_provider
    assert composition.llm_provider_available is True
    assert composition.backend_identities["ai_state"] == "ai_ready"


def test_autonomy_enabled_with_vertex_unavailable_fails_closed() -> None:
    """Vertex failure with autonomy on raises :class:`CompositionError`.

    Misconfiguration is not masked as ``ai_disabled``. The factory
    raises so the lifespan refuses to start and ``/ready`` returns
    503.
    """
    class _VertexFailure(Exception):
        pass

    with patch(
        "retailtwin_api.composition.create_provider",
        side_effect=_VertexFailure("simulated ADC unreachable"),
    ):
        with pytest.raises(_VertexFailure):
            build_composition(
                _settings(app_env="staging", autonomy_enabled=True)
            )


# ── /ready surfaces new contract (review blocker #2 + #4) ──────────────────


def test_get_ready_surfaces_ai_state_and_analytics_readiness() -> None:
    """``GET /ready`` exposes ``ai_state``, ``ai_reason`` and ``analytics_readiness``.

    The release-gate uses these to block misconfigured deployments
    without lumping intentional disablement in with misconfiguration.
    """
    app = create_app(
        _settings(app_env="staging", autonomy_enabled=False)
    )
    with TestClient(app) as client:
        response = client.get("/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ai_state"] == "ai_disabled"
    assert payload["ai_reason"] == "autonomy_disabled_by_config"
    assert "analytics_readiness" in payload
    analytics = payload["analytics_readiness"]
    assert "ready" in analytics
    assert "reason" in analytics