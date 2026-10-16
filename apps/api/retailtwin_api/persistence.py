"""Composition root for durable agent state (ADR 0024).

Selects the process-memory or Firestore-backed adapters that back
``DecisionSource``, ``SimulationRepository``, ``AgentActivityLog`` and
``MemoryActivationLedger``. The factory is the single place that decides
which storage backend a Cloud Run instance uses; the lifespan wires the
returned adapters into ``app.state`` once at startup.

Selection rule
--------------
``LIVE_TWIN_BACKEND``:

* ``"fixture"`` — read-only day-0 fixture; no Decisions are stored. The
  ``decisions`` adapter is the unavailable one, the routes return 503.
* ``"memory"`` — in-process adapters for tests and local dev.
* ``"firestore"`` — Firestore-backed durable adapters. The same project
  as the Live Twin (``retailtwin-ai-511002``).

There is no implicit fallback: production must set
``LIVE_TWIN_BACKEND=firestore`` explicitly. A missing or unknown value
stays on the in-memory adapters and logs a warning so the operator can
see why the chain does not survive a deploy.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from retailtwin_api.decisions import DecisionSource, InMemoryDecisionSource
from retailtwin_api.firestore_decisions import FirestoreDecisionSource
from retailtwin_api.settings import Settings

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class DurableAdapters:
    """Bundle of cross-instance adapters returned by :func:`get_persistence`."""

    decisions: DecisionSource


class _UnavailableDecisionSourceAdapter:
    """Adapter shaped like :class:`DecisionSource` that returns ``available=False``.

    A read returns ``None``; a write raises :class:`RuntimeError` so a chain
    that runs against the fixture backend cannot accidentally mutate state
    that does not exist.
    """

    @property
    def available(self) -> bool:
        return False

    def put(self, simulation_id: str, decision) -> None:  # noqa: D401 — typed boundary
        raise RuntimeError(
            "Cannot persist Decision in fixture backend: LIVE_TWIN_BACKEND=fixture is read-only."
        )

    def get_for_simulation(self, simulation_id: str):  # noqa: D401 — typed boundary
        return None


def _unavailable_decisions_source() -> DecisionSource:
    return _UnavailableDecisionSourceAdapter()  # type: ignore[return-value]


def get_persistence(settings: Settings) -> DurableAdapters:
    """Build the cross-instance adapter bundle for the configured backend.

    Returns the same Protocol objects regardless of backend, so the rest of
    the code is agnostic. The factory logs the chosen backend so a
    misconfigured Cloud Run revision surfaces in the startup log.
    """
    backend = settings.live_twin_backend
    if backend == "firestore":
        log.info(
            "persistence.firestore project=%s",
            settings.google_cloud_project or "retailtwin-ai-511002",
        )
        return DurableAdapters(decisions=FirestoreDecisionSource())
    if backend == "fixture":
        log.warning(
            "persistence.fixture_decisions_unwritable store_id=%s",
            settings.store_id,
        )
        return DurableAdapters(decisions=_unavailable_decisions_source())
    if backend == "memory":
        log.info("persistence.memory store_id=%s", settings.store_id)
        return DurableAdapters(decisions=InMemoryDecisionSource())
    raise ValueError(f"Unknown LIVE_TWIN_BACKEND {backend!r}")


__all__ = ["DurableAdapters", "get_persistence"]