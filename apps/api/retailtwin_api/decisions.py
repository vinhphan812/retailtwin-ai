"""Where the review routes find the Decision behind a simulation.

The planner or orchestrator records the Decision it simulated. The review
route never builds one: no evidence is invented at approval time.

ADR 0024: ``DecisionSource`` exposes both read (``get_for_simulation``) and
write (``put``). The orchestrator writes; the review route reads. The two
ends meet on the same ``simulation_id`` key. ``available`` is True while
the source is wired and ready to serve; ``unavailable_decision_source()``
returns the same Protocol with ``available=False`` so a route can refuse
the read cleanly instead of pretending a missing backend is healthy.
"""

from __future__ import annotations

import threading
from typing import Protocol

from retailtwin_api.contracts import Decision


class DecisionSource(Protocol):
    @property
    def available(self) -> bool: ...  # pragma: no branch

    def put(self, simulation_id: str, decision: Decision) -> None: ...

    def get_for_simulation(self, simulation_id: str) -> Decision | None: ...  # pragma: no branch


class InMemoryDecisionSource:
    """Process-memory decisions by simulation id, for development and tests."""

    def __init__(self, available: bool = True) -> None:
        self._available = available
        self._lock = threading.Lock()
        self._by_simulation: dict[str, Decision] = {}

    @property
    def available(self) -> bool:
        return self._available

    def put(self, simulation_id: str, decision: Decision) -> None:
        with self._lock:
            self._by_simulation[simulation_id] = decision.model_copy(deep=True)

    def get_for_simulation(self, simulation_id: str) -> Decision | None:
        with self._lock:
            found = self._by_simulation.get(simulation_id)
            return found.model_copy(deep=True) if found is not None else None


def unavailable_decision_source() -> DecisionSource:
    return InMemoryDecisionSource(available=False)
