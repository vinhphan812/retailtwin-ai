"""Simulation Service — clones live state and evaluates candidate actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.twin import TwinService


class SimulationService:
    """Simulates candidate actions on a clone of the Live Twin.

    This is a stub implementation for demo purposes only.
    """

    def __init__(self, twin: TwinService) -> None:
        self._twin = twin
        self._clone = None

    def clone(self) -> TwinService:
        """Create a clone of the current Live Twin state."""
        return self._twin

    def apply(self, actions: list[dict]) -> dict:
        """Apply candidate actions to the simulation clone.

        Args:
            actions: List of actions to simulate

        Returns:
            Simulation result with KPIs
        """
        return {
            "applied": True,
            "actions_count": len(actions),
            "kpis": {},
        }

    def evaluate(self) -> dict:
        """Evaluate simulation KPIs before/after actions.

        Returns:
            KPI evaluation result
        """
        return {
            "evaluated": True,
            "kpis": {
                "sales": 0,
                "revenue": 0,
                "stockout_risk": 0,
            },
        }
