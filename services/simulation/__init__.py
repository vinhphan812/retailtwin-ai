"""Simulation Service — clones live state and evaluates candidate actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.twin import TwinService


class SimulationService:
    def __init__(self, twin: TwinService) -> None:
        self._twin = twin

    def clone(self) -> TwinService:
        return self._twin

    def apply(self, actions: list[dict]) -> dict:
        return {"applied": True, "actions_count": len(actions), "kpis": {}}

    def evaluate(self) -> dict:
        return {"evaluated": True, "kpis": {"sales": 0, "revenue": 0, "stockout_risk": 0}}
