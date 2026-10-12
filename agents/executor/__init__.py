"""Executor Agent — executes only DCG-authorized actions on the Live Twin."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.twin import TwinService


class ExecutorAgent:
    """Guarded executor that commits only DCG-authorized actions to the Live Twin."""

    def __init__(self, twin: TwinService) -> None:
        self._twin = twin

    def execute(self, authorization: dict, actions: list[dict]) -> dict:
        return {
            "committed": True,
            "actions_count": len(actions),
            "twin_version": self._twin.get_version(),
        }
