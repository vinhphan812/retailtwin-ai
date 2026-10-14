"""Refresh evidence and authorize a new decision after a stale rejection.

``REFRESH_REQUIRED`` discards the binding from the rejected decision. The same
injected provider then runs the investigator and the planner. A new immutable
``Decision`` is authorized. The commit port is called only after ``ALLOW``
survives ``recheck``. This module does not write the Live Twin and does not
branch on which vendor the provider calls.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol

from retailtwin_api.agents.investigator.evidence import InvestigatorError, investigate
from retailtwin_api.agents.observer.consumer import InvestigationStart
from retailtwin_api.agents.orchestrator.tool_registry import ToolRegistry
from retailtwin_api.agents.planner.plans import UNSCORED_IMPACT, PlannerError, plan
from retailtwin_api.contracts import DCGVerdict, Decision
from retailtwin_api.guard.decision_context_guard.no_stale_commit import CommitBinding, NoStaleCommit
from retailtwin_api.llm.contracts import LlmProvider

log = logging.getLogger(__name__)

MAX_REFRESHES_ENV = "RETAILTWIN_REPLAN_MAX_REFRESHES"
DEFAULT_MAX_REFRESHES = 1

LINEAGE_MISMATCH = "lineage_mismatch"
PROVIDER_FAILED = "provider_failed"
SIMULATION_FAILED = "simulation_failed"
EMPTY_PLAN = "empty_plan"
COMMIT_FAILED = "commit_failed"
MISSING_BINDING = "missing_binding"


class ReplanConfigError(ValueError):
    """The refresh bound is set but is not a non-negative integer."""


class ReplanStatus(str, Enum):
    """How one recovery attempt ended. A commit exists only for ``COMMITTED``."""

    COMMITTED = "COMMITTED"
    DENIED = "DENIED"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    RETRY_LIMIT = "RETRY_LIMIT"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ReplanResult:
    """The terminal outcome. ``decision_id`` is the decision the loop stopped on."""

    status: ReplanStatus
    correlation_id: str
    decision_id: str | None
    committed_decision_id: str | None
    verdict: DCGVerdict | None
    reason_code: str
    refresh_count: int


class CommitPort(Protocol):
    """Hands an allowed decision to the guarded commit path.

    Called only with a binding that ``authorize`` just issued and ``recheck``
    still allows. Implementations must not accept a binding from an earlier
    ``REFRESH_REQUIRED``.
    """

    def commit(self, decision: Decision, binding: CommitBinding) -> None: ...


class SimulationPort(Protocol):
    """Scores refreshed decisions. The orchestrator does not compute a KPI."""

    def score(self, decisions: Sequence[Decision]) -> Sequence[Decision]: ...


def max_refreshes_from_env(environ: Mapping[str, str] | None = None) -> int:
    """Read ``RETAILTWIN_REPLAN_MAX_REFRESHES``. Unset or blank stays at 1."""

    env = os.environ if environ is None else environ
    raw = env.get(MAX_REFRESHES_ENV)
    if raw is None or not raw.strip():
        return DEFAULT_MAX_REFRESHES
    try:
        value = int(raw)
    except ValueError:
        raise ReplanConfigError(f"{MAX_REFRESHES_ENV} must be a non-negative integer.") from None
    if value < 0:
        raise ReplanConfigError(f"{MAX_REFRESHES_ENV} must be a non-negative integer.")
    return value


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _limit(max_refreshes: int | None) -> int:
    if max_refreshes is None:
        return max_refreshes_from_env()
    if max_refreshes < 0:
        raise ReplanConfigError("max_refreshes must be a non-negative integer.")
    return max_refreshes


def _same_lineage(decision: Decision, start: InvestigationStart) -> bool:
    event = start.event
    if not decision.evidence:
        return False
    return all(
        bundle.store_id == event.store_id and bundle.correlation_id == event.correlation_id
        for bundle in decision.evidence
    )


def _prefer(decisions: Sequence[Decision]) -> list[Decision]:
    """Authorize a scored candidate before an unscored one. ``-1.0`` is not a score."""

    indexed = list(enumerate(decisions))
    scored = [item for item in indexed if item[1].expected_impact.kpi_score != UNSCORED_IMPACT]
    unscored = [item[1] for item in indexed if item[1].expected_impact.kpi_score == UNSCORED_IMPACT]
    scored.sort(key=lambda item: (-item[1].expected_impact.kpi_score, item[0]))
    return [item[1] for item in scored] + unscored


def _finish(
    status: ReplanStatus,
    correlation_id: str,
    decision_id: str | None,
    committed_decision_id: str | None,
    verdict: DCGVerdict | None,
    reason_code: str,
    refresh_count: int,
) -> ReplanResult:
    log.info(
        "replan finished correlation_id=%s status=%s reason=%s refreshes=%s decision_id=%s",
        correlation_id,
        status.value,
        reason_code,
        refresh_count,
        decision_id or "",
    )
    return ReplanResult(
        status=status,
        correlation_id=correlation_id,
        decision_id=decision_id,
        committed_decision_id=committed_decision_id,
        verdict=verdict,
        reason_code=reason_code,
        refresh_count=refresh_count,
    )


def _from_guard(
    status: ReplanStatus,
    verdict_name: DCGVerdict,
    reason_code: str,
    correlation_id: str,
    decision_id: str,
    refresh_count: int,
) -> ReplanResult:
    return _finish(status, correlation_id, decision_id, None, verdict_name, reason_code, refresh_count)


async def _refresh(
    start: InvestigationStart,
    *,
    provider: LlmProvider,
    registry: ToolRegistry,
    context_version: str,
    simulate: SimulationPort | None,
    clock: Callable[[], datetime],
    previous_decision_id: str,
    refreshes: int,
    limit: int,
    reason_code: str,
) -> list[Decision] | ReplanResult:
    correlation_id = start.event.correlation_id
    if refreshes >= limit:
        return _finish(
            ReplanStatus.RETRY_LIMIT,
            correlation_id,
            previous_decision_id,
            None,
            DCGVerdict.REFRESH_REQUIRED,
            reason_code,
            refreshes,
        )
    attempt = refreshes + 1
    now = clock()
    log.info(
        "replan refresh correlation_id=%s previous_decision_id=%s refresh=%s",
        correlation_id,
        previous_decision_id,
        attempt,
    )
    try:
        bundle = await investigate(start, provider=provider, registry=registry, collected_at=now)
    except InvestigatorError:
        log.info(
            "replan provider failed correlation_id=%s error_type=InvestigatorError",
            correlation_id,
        )
        return _finish(
            ReplanStatus.FAILED,
            correlation_id,
            previous_decision_id,
            None,
            DCGVerdict.REFRESH_REQUIRED,
            PROVIDER_FAILED,
            attempt,
        )
    if bundle.correlation_id != correlation_id or bundle.store_id != start.event.store_id:
        return _finish(
            ReplanStatus.FAILED,
            correlation_id,
            previous_decision_id,
            None,
            DCGVerdict.REFRESH_REQUIRED,
            LINEAGE_MISMATCH,
            attempt,
        )
    try:
        decisions = await plan(
            bundle,
            provider=provider,
            context_version=context_version,
            context_timestamp=now,
        )
    except PlannerError as exc:
        log.info(
            "replan planning failed correlation_id=%s reason=%s error_type=PlannerError",
            correlation_id,
            exc.reason,
        )
        return _finish(
            ReplanStatus.FAILED,
            correlation_id,
            previous_decision_id,
            None,
            DCGVerdict.REFRESH_REQUIRED,
            exc.reason,
            attempt,
        )
    if simulate is not None:
        try:
            produced = list(simulate.score(decisions))
        except Exception as exc:
            log.info(
                "replan simulation failed correlation_id=%s error_type=%s",
                correlation_id,
                type(exc).__name__,
            )
            return _finish(
                ReplanStatus.FAILED,
                correlation_id,
                previous_decision_id,
                None,
                DCGVerdict.REFRESH_REQUIRED,
                SIMULATION_FAILED,
                attempt,
            )
        if not produced or not all(_same_lineage(item, start) for item in produced):
            reason = EMPTY_PLAN if not produced else LINEAGE_MISMATCH
            return _finish(
                ReplanStatus.FAILED,
                correlation_id,
                previous_decision_id,
                None,
                DCGVerdict.REFRESH_REQUIRED,
                reason,
                attempt,
            )
        decisions = produced
    return _prefer(decisions)


async def replan(
    decision: Decision,
    start: InvestigationStart,
    *,
    authorizer: NoStaleCommit,
    provider: LlmProvider,
    registry: ToolRegistry,
    commit: CommitPort,
    simulate: SimulationPort | None = None,
    max_refreshes: int | None = None,
    clock: Callable[[], datetime] = _utcnow,
) -> ReplanResult:
    """Recover one run after a stale decision, or stop on a terminal verdict.

    ``max_refreshes`` counts ``REFRESH_REQUIRED`` cycles. A provider failure
    does not start another cycle and does not call ``commit``.
    """

    limit = _limit(max_refreshes)
    correlation_id = start.event.correlation_id
    if not _same_lineage(decision, start):
        return _finish(
            ReplanStatus.FAILED,
            correlation_id,
            decision.decision_id,
            None,
            None,
            LINEAGE_MISMATCH,
            0,
        )
    pending: list[Decision] = [decision]
    refreshes = 0
    while pending:
        current = pending.pop(0)
        verdict, binding = authorizer.authorize(current)
        if verdict.verdict is DCGVerdict.ALLOW:
            if binding is None:
                return _finish(
                    ReplanStatus.FAILED,
                    correlation_id,
                    current.decision_id,
                    None,
                    verdict.verdict,
                    MISSING_BINDING,
                    refreshes,
                )
            checked = authorizer.recheck(current, binding)
            if checked.verdict is DCGVerdict.REFRESH_REQUIRED:
                # The binding authorized the previous version. It is not reused.
                outcome = await _refresh(
                    start,
                    provider=provider,
                    registry=registry,
                    context_version=current.context_version,
                    simulate=simulate,
                    clock=clock,
                    previous_decision_id=current.decision_id,
                    refreshes=refreshes,
                    limit=limit,
                    reason_code=checked.reason_code,
                )
                if isinstance(outcome, ReplanResult):
                    return outcome
                refreshes += 1
                pending = outcome
                continue
            if checked.verdict is not DCGVerdict.ALLOW:
                status = (
                    ReplanStatus.HUMAN_REVIEW
                    if checked.verdict is DCGVerdict.HUMAN_REVIEW
                    else ReplanStatus.DENIED
                )
                return _from_guard(
                    status, checked.verdict, checked.reason_code, correlation_id, current.decision_id, refreshes
                )
            try:
                commit.commit(current, binding)
            except Exception as exc:
                log.info(
                    "replan commit failed correlation_id=%s decision_id=%s error_type=%s",
                    correlation_id,
                    current.decision_id,
                    type(exc).__name__,
                )
                return _finish(
                    ReplanStatus.FAILED,
                    correlation_id,
                    current.decision_id,
                    None,
                    DCGVerdict.ALLOW,
                    COMMIT_FAILED,
                    refreshes,
                )
            return _finish(
                ReplanStatus.COMMITTED,
                correlation_id,
                current.decision_id,
                current.decision_id,
                DCGVerdict.ALLOW,
                checked.reason_code,
                refreshes,
            )
        if verdict.verdict is DCGVerdict.REFRESH_REQUIRED:
            outcome = await _refresh(
                start,
                provider=provider,
                registry=registry,
                context_version=current.context_version,
                simulate=simulate,
                clock=clock,
                previous_decision_id=current.decision_id,
                refreshes=refreshes,
                limit=limit,
                reason_code=verdict.reason_code,
            )
            if isinstance(outcome, ReplanResult):
                return outcome
            refreshes += 1
            pending = outcome
            continue
        if verdict.verdict is DCGVerdict.HUMAN_REVIEW:
            return _from_guard(
                ReplanStatus.HUMAN_REVIEW,
                verdict.verdict,
                verdict.reason_code,
                correlation_id,
                current.decision_id,
                refreshes,
            )
        if pending:
            continue
        return _from_guard(
            ReplanStatus.DENIED,
            verdict.verdict,
            verdict.reason_code,
            correlation_id,
            current.decision_id,
            refreshes,
        )
    return _finish(ReplanStatus.FAILED, correlation_id, decision.decision_id, None, None, EMPTY_PLAN, refreshes)
