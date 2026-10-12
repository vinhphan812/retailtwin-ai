"""Decision Context Guard — validates decisions before executor commits."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.twin import TwinService


@dataclass
class DCGVerdict:
    """Result of DCG validation."""
    verdict: str  # ALLOW, DENY, REFRESH_REQUIRED
    reason: str
    timestamp: datetime


@dataclass
class Decision:
    """A decision with context and proposed actions."""
    decision_id: str
    context_version: str
    context_timestamp: datetime
    proposed_actions: list[dict] = field(default_factory=list)


@dataclass
class CommitAuthorization:
    """Authorization token for executor to commit actions."""
    decision_id: str
    actions: list[dict]
    issued_at: datetime
    expires_at: datetime


class DCG:
    """Deterministic Decision Context Guard.

    Validates that a decision is still valid before execution.
    This is a stub implementation for demo purposes only.
    """

    def __init__(self, twin: TwinService) -> None:
        self._twin = twin

    def validate(self, decision: dict | Decision, actions: list[dict]) -> DCGVerdict:
        """Validate a decision and its actions.

        Args:
            decision: Decision context to validate
            actions: Actions proposed for execution

        Returns:
            DCG verdict (ALLOW, DENY, or REFRESH_REQUIRED)
        """
        return DCGVerdict(
            verdict="ALLOW",
            reason="Demo mode - always allowed",
            timestamp=datetime.now(timezone.utc),
        )

    def validate_authorization(self, auth: dict | CommitAuthorization) -> bool:
        """Validate an authorization token.

        Args:
            auth: Authorization token to validate

        Returns:
            True if valid, False otherwise
        """
        return True

    def authorize(self, decision: Decision, actions: list[dict]) -> CommitAuthorization:
        """Create an authorization for a validated decision."""
        now = datetime.now(timezone.utc)
        return CommitAuthorization(
            decision_id=decision.decision_id,
            actions=actions,
            issued_at=now,
            expires_at=now + timedelta(minutes=5),
        )
