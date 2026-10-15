"""Tests for the FastAPI lifespan wiring of the autonomous trigger.

These tests exercise the ``create_app`` startup and teardown paths with
the autonomous trigger and scheduled publisher enabled, so the new
lifespan code in :mod:`retailtwin_api.main` is covered end-to-end.
"""

from __future__ import annotations

import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from retailtwin_api.backbone import MemoryPipe
from retailtwin_api.demand_surge import DemandSurgeScheduler
from retailtwin_api.main import create_app
from retailtwin_api.settings import DEFAULT_FIXTURE, Settings


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "app_env": "test",
        "store_id": "store-001",
        "store_fixture_path": DEFAULT_FIXTURE,
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)  # type: ignore[arg-type]


def test_lifespan_wires_event_pipe_and_observer() -> None:
    """Default lifespan (trigger OFF) wires MemoryPipe + observer_quarantine."""

    settings = _settings()
    app = create_app(settings)
    with TestClient(app) as client:
        assert isinstance(app.state.event_pipe, MemoryPipe)
        assert app.state.activation_ledger is not None
        assert app.state.observer_quarantine is not None
        assert app.state.observer_starter is not None
        assert not hasattr(app.state, "trigger_task") or app.state.trigger_task is None
        assert not hasattr(app.state, "scheduler") or app.state.scheduler is None
        # Sanity: the app still serves traffic.
        assert client.get("/health").status_code in (200, 503)


def test_lifespan_starts_autonomous_trigger_when_enabled() -> None:
    """AUTONOMOUS_TRIGGER_ENABLED=true spawns the trigger task."""

    settings = _settings(autonomous_trigger_enabled=True, autonomous_trigger_interval_seconds=45)
    app = create_app(settings)
    with TestClient(app) as _client:
        task = getattr(app.state, "trigger_task", None)
        assert task is not None
        assert not task.done()
    # Lifespan teardown cancels the task.
    assert task.cancelled() or task.done()


def test_lifespan_starts_scheduler_when_enabled() -> None:
    """AUTONOMOUS_SCHEDULED_PUBLISHER_ENABLED=true starts the DemandSurgeScheduler."""

    settings = _settings(
        autonomous_scheduled_publisher_enabled=True,
        autonomous_trigger_interval_seconds=45,
    )
    app = create_app(settings)
    with TestClient(app) as _client:
        scheduler = getattr(app.state, "scheduler", None)
        assert isinstance(scheduler, DemandSurgeScheduler)
        assert scheduler._task is not None
        assert not scheduler._task.done()


def test_lifespan_production_uses_memory_when_project_missing() -> None:
    """A production build without a project id falls back to MemoryPipe."""

    settings = _settings(
        app_env="production",
        autonomous_pubsub_project=None,
        google_cloud_project=None,
    )
    app = create_app(settings)
    with TestClient(app) as _client:
        assert isinstance(app.state.event_pipe, MemoryPipe)


def test_lifespan_production_uses_gcp_pipe_when_project_set() -> None:
    """A production build with a project id wires the GCP pipe."""

    settings = _settings(
        app_env="production",
        autonomous_pubsub_project="retailtwin-ai-511002",
    )
    app = create_app(settings)
    with TestClient(app) as _client:
        from retailtwin_api.backbone_gcp import GcpPubSubEventPipe

        assert isinstance(app.state.event_pipe, GcpPubSubEventPipe)
        assert app.state.event_pipe.subscription_path.endswith("/store-events-agent")


def test_autonomous_trigger_loop_runs_consume_available() -> None:
    """The trigger task actually consumes from the pipe and acks the message."""

    settings = _settings(
        autonomous_trigger_enabled=True,
        autonomous_trigger_interval_seconds=45,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        # Reach into the lifespan-built pipe and publish a canonical event.
        pipe: MemoryPipe = app.state.event_pipe  # type: ignore[assignment]
        from retailtwin_api.demand_surge import build_canonical_sale_event

        event = build_canonical_sale_event()
        pipe.publish(event)

        # Wait for both the consumer to drain ``pending`` AND for the
        # ack to land. The consumer pulls the message out of ``pending``
        # before driving the flagship chain, so a check on ``pending``
        # alone races with the ``pipe.ack`` that runs after the chain.
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if not pipe.pending and pipe.acked:
                break
            time.sleep(0.05)
        assert pipe.pending == []  # consumed
        assert pipe.acked  # acked
        # Sanity: the app still serves traffic.
        assert client.get("/health").status_code in (200, 503)


def test_lifespan_teardown_is_clean_for_trigger_task() -> None:
    """Cancelling the lifespan does not leak threads or asyncio tasks."""

    settings = _settings(autonomous_trigger_enabled=True)
    app = create_app(settings)
    captured_task: asyncio.Task[None] | None = None
    with TestClient(app):
        captured_task = getattr(app.state, "trigger_task", None)
        assert captured_task is not None
    # After teardown the lifespan nulls the state slot.
    assert getattr(app.state, "trigger_task", "missing") is None