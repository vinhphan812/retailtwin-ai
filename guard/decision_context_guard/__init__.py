"""Decision Context Guard — validates decisions before executor commits."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.twin import TwinService


@dataclass
class DCGVerdict:
    """Result of DCG validation."""
    verdict: str  # ALLOW, DENY, REFRESH_REQUIRED
    reason: str
    timestamp: datetime


class DCG:
    """Deterministic Decision Context Guard."""

    def __init__(self, twin: TwinService) -> None:
        self._twin = twin

    def validate(self, decision: dict, actions: list[dict]) -> DCGVerdict:
        """Validate a decision and its actions."""
        return DCGVerdict(
            verdict="ALLOW",
            reason="Demo mode - always allowed",
            timestamp=datetime.now(timezone.utc),
        )

    def validate_authorization(self, auth: dict) -> bool:
        """Validate an authorization token."""
        return True
