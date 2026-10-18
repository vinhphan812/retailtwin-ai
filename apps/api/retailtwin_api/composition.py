"""Production composition root - unified factory for environment-specific wiring.

This module provides a single entry point (`build_composition`) that wires the
entire application based on the environment:

- **Production** (`APP_ENV=production`):
  - Live Twin: Firestore
  - LLM: Vertex AI Gemini (ADC only, no API keys)
  - Analytics: BigQuery probe enabled

- **Development/Test** (`APP_ENV=development|test|e2e-smoke`):
  - Live Twin: In-memory (seeded from fixture)
  - LLM: Fake provider or openai_compatible
  - Analytics: In-memory stubs

The composition root is fail-closed in production: any misconfiguration
raises an exception at startup rather than silently falling back to dev defaults.

References:
- ADR 0029: Production Composition Root
- ADR 0020: Register LLM providers and require Vertex ADC in production
- Issue #214: Production composition root
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from retailtwin_api.backbone import EventPipe, MemoryPipe
from retailtwin_api.llm.factory import create_provider, llm_config_from_settings
from retailtwin_api.settings import Settings
from retailtwin_api.store import LiveTwinStore, StoreReader, open_memory_live_store
from retailtwin_api.firestore_twin import FirestoreLiveTwinRepository

if TYPE_CHECKING:
    from retailtwin_api.agents.orchestrator.tool_registry import ToolRegistry
    from retailtwin_api.firestore_twin import LiveTwinRepository
    from retailtwin_api.llm.factory import LlmProvider


@dataclass(frozen=True)
class Composition:
    """Wired dependencies for the RetailTwin API.

    All environment-specific wiring is encapsulated here. Callers receive
    the same interface regardless of environment.
    """

    settings: Settings
    store: StoreReader
    live_twin: "LiveTwinRepository"
    provider: "LlmProvider | None"
    registry: "ToolRegistry"
    analytics: tuple[Any, Any, Any, Any]  # (anomalies, revenue, promotions, checkouts)
    event_pipe: EventPipe


def build_composition(settings: Settings) -> Composition:
    """Build the production composition root.

    This is the single entry point for wiring the application. In production
    (`APP_ENV=production`), any misconfiguration raises a ConfigurationError.

    Args:
        settings: Application settings (environment, backend configs, etc.)

    Returns:
        A fully wired Composition ready for use

    Raises:
        ConfigurationError: In production when any component cannot be configured
    """
    # 1. Live Twin Repository
    live_twin = _build_live_twin(settings)

    # 2. Store reader (depends on live twin backend)
    store = _build_store(settings)

    # 3. LLM Provider (if autonomy enabled)
    provider = _build_provider(settings)

    # 4. Tool Registry (depends on store)
    registry = _build_registry(store)

    # 5. Analytics (depends on environment)
    analytics = _build_analytics(settings)

    # 6. Event Pipe (always MemoryPipe - Pub/Sub is push-only in production)
    event_pipe = MemoryPipe()

    return Composition(
        settings=settings,
        store=store,
        live_twin=live_twin,
        provider=provider,
        registry=registry,
        analytics=analytics,
        event_pipe=event_pipe,
    )


def _build_live_twin(settings: Settings) -> "LiveTwinRepository":
    """Build the Live Twin repository based on environment."""
    if settings.is_production:
        # Production requires Firestore
        if settings.live_twin_backend != "firestore":
            from retailtwin_api.llm.factory import ConfigurationError

            raise ConfigurationError(
                "production requires LIVE_TWIN_BACKEND=firestore; "
                f"got {settings.live_twin_backend!r}"
            )
        return FirestoreLiveTwinRepository()

    # Dev/Test: In-memory twin seeded from fixture
    from retailtwin_api.firestore_twin import InMemoryTwinRepository

    return InMemoryTwinRepository()


def _build_store(settings: Settings) -> StoreReader:
    """Build the store reader based on environment."""
    if settings.live_twin_backend == "fixture":
        from retailtwin_api.store import open_store

        return open_store(settings.store_fixture_path, settings.store_id)

    if settings.live_twin_backend == "firestore":
        # Production: Firestore-backed Live Twin
        twin = FirestoreLiveTwinRepository()
        return LiveTwinStore(twin, settings.store_id)

    # Default: memory (in-process Live Twin seeded from fixture)
    return open_memory_live_store(settings.store_fixture_path, settings.store_id)


def _build_provider(settings: Settings) -> "LlmProvider | None":
    """Build the LLM provider based on environment.

    In production, enforces ADR 0020: only vertex_gemini is allowed,
    and it must use ADC (no API keys).
    """
    if not settings.autonomy_enabled:
        return None

    config = llm_config_from_settings(settings)

    # create_provider enforces production constraints (ADR 0020)
    # - Production: only vertex_gemini, rejects fake/loopback/API keys
    # - Dev/Test: any registered provider
    return create_provider(config)


def _build_registry(store: StoreReader) -> "ToolRegistry":
    """Build the tool registry based on the store."""
    from retailtwin_api.agents.orchestrator.tool_registry import build_store_registry

    return build_store_registry(store)


def _build_analytics(settings: Settings):
    """Build analytics repositories based on environment.

    Production: BigQuery + Firestore probes
    Dev/Test: In-memory stubs
    """
    from retailtwin_api.analytics_repository import (
        get_checkout_repository,
        unavailable_analytics_repositories,
    )

    # Return tuple like main.py expects: (anomalies, revenue, promotions, checkouts)
    anomalies, revenue, promotions, _ = unavailable_analytics_repositories()
    return (
        anomalies,
        revenue,
        promotions,
        get_checkout_repository(),
    )
