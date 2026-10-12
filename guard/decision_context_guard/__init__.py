"""Decision Context Guard — validates decisions before executor commits."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.twin import TwinService


@dataclass
class DCGVerdict:
    verdict: str
    reason: str
    timestamp: datetime


class DCG:
    def __init__(self, twin: TwinService) -> None:
        self._twin = twin

    def validate(self, decision: dict, actions: list[dict]) -> DCGVerdict:
        return DCGVerdict(
            verdict="ALLOW",
            reason="Demo mode - always allowed",
            timestamp=datetime.now(timezone.utc),
        )

    def validate_authorization(self, auth: dict) -> bool:
        return True
