"""No-Stale-Commit (#17): a decision built at version N never commits at N+1."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from retailtwin_api.contracts import (
    ChangeFacings,
    DCGVerdict,
    Decision,
    EvidenceBundle,
    ExpectedImpact,
    ReplenishShelf,
)
from retailtwin_api.firestore_twin import InMemoryTwinRepository, InventorySeed
from retailtwin_api.guard.decision_context_guard import (
    BINDING_MISMATCH,
    CONTEXT_EXPIRED,
    INSUFFICIENT_EVIDENCE,
    VERSION_STALE,
    DecisionContextGuard,
    InMemoryGuardAudit,
    NoStaleCommit,
)

STORE = "store-001"
T0 = datetime(2026, 10, 13, 9, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def twin() -> InMemoryTwinRepository:
    repo = InMemoryTwinRepository()
    repo.seed(
        STORE,
        "v1",
        [
            InventorySeed(sku="P001", shelf_id="SH1", slot_id="S1", facings=2, shelf_quantity=10, backroom_quantity=30),
            InventorySeed(sku="P002", shelf_id="SH1", slot_id="S2", facings=3, shelf_quantity=4, backroom_quantity=9),
        ],
    )
    return repo


@pytest.fixture
def clock() -> Clock:
    return Clock(T0)


@pytest.fixture
def audit() -> InMemoryGuardAudit:
    return InMemoryGuardAudit()


@pytest.fixture
def gate(twin: InMemoryTwinRepository, audit: InMemoryGuardAudit, clock: Clock) -> NoStaleCommit:
    return NoStaleCommit(DecisionContextGuard(twin, clock=clock), audit, clock=clock)


def decision_at(twin: InMemoryTwinRepository, sku: str = "P001", *, sufficient: bool = True, **overrides: object) -> Decision:
    """A decision whose evidence read ``sku`` at its current live version."""
    doc = twin.get_inventory(STORE, sku)
    assert doc is not None
    fields: dict[str, object] = {
        "decision_id": "dec-1",
        "agent_id": "planner",
        "context_version": f"{STORE}:v1",
        "context_timestamp": T0,
        "evidence": [
            EvidenceBundle(
                bundle_id="bundle-1",
                provenance="tool-registry",
                source="investigator",
                entity_versions={sku: str(doc.version)},
                collected_at=T0,
                freshness=T0,
                store_id=STORE,
                correlation_id="corr-stale-1",
                is_sufficient=sufficient,
            )
        ],
        "proposed_actions": [ReplenishShelf(sku=sku, quantity=6)],
        "expected_impact": ExpectedImpact(kpi_score=0.3, description="fewer stockouts"),
    }
    fields.update(overrides)
    return Decision(**fields)  # type: ignore[arg-type]


def bump(twin: InMemoryTwinRepository, sku: str, **changes: int) -> None:
    doc = twin.get_inventory(STORE, sku)
    assert doc is not None
    twin.upsert_inventory(doc.model_copy(update={"version": doc.version + 1, **changes}), expected_version=doc.version)


def test_authorize_binds_the_live_versions(gate: NoStaleCommit, twin: InMemoryTwinRepository) -> None:
    result, binding = gate.authorize(decision_at(twin))

    assert result.verdict is DCGVerdict.ALLOW
    assert binding is not None
    assert binding.decision_id == "dec-1"
    assert binding.store_id == STORE
    assert binding.entity_versions == {"P001": 1}
    assert binding.context_hash == result.context_hash
    assert binding.expiry == T0 + timedelta(seconds=120)


def test_unchanged_context_passes_the_recheck(gate: NoStaleCommit, twin: InMemoryTwinRepository, clock: Clock) -> None:
    d1 = decision_at(twin)
    _, binding = gate.authorize(d1)
    assert binding is not None
    clock.now = T0 + timedelta(seconds=30)

    assert gate.recheck(d1, binding).verdict is DCGVerdict.ALLOW


def test_version_n_plus_one_blocks_before_authorization(
    gate: NoStaleCommit, twin: InMemoryTwinRepository, audit: InMemoryGuardAudit
) -> None:
    """Issue #17 scenario: D1 at N, live moves to N+1, no authorization is issued."""
    d1 = decision_at(twin)
    bump(twin, "P001", shelf_quantity=3)
    before = twin.get_inventory(STORE, "P001")

    result, binding = gate.authorize(d1)

    assert (result.verdict, result.reason_code) == (DCGVerdict.REFRESH_REQUIRED, VERSION_STALE)
    assert binding is None
    assert twin.get_inventory(STORE, "P001") == before
    [event] = audit.events("dec-1")
    assert (event.stage, event.verdict, event.reason_code) == ("authorize", DCGVerdict.REFRESH_REQUIRED, VERSION_STALE)
    assert event.correlation_id == "corr-stale-1"
    assert event.entity_versions == {"P001": "2"}
    assert event.failed_gate == "context"


def test_version_n_plus_one_blocks_at_commit(
    gate: NoStaleCommit, twin: InMemoryTwinRepository, audit: InMemoryGuardAudit
) -> None:
    """Authorized at N, live moves to N+1 before the commit: the recheck refuses."""
    d1 = decision_at(twin)
    _, binding = gate.authorize(d1)
    assert binding is not None
    bump(twin, "P001")
    before = [doc.model_dump() for doc in twin.list_inventory(STORE)]

    result = gate.recheck(d1, binding)

    assert (result.verdict, result.reason_code) == (DCGVerdict.REFRESH_REQUIRED, VERSION_STALE)
    assert [doc.model_dump() for doc in twin.list_inventory(STORE)] == before
    assert [(e.stage, e.verdict) for e in audit.events("dec-1")] == [
        ("authorize", DCGVerdict.ALLOW),
        ("commit", DCGVerdict.REFRESH_REQUIRED),
    ]


def test_change_to_another_sku_does_not_block(gate: NoStaleCommit, twin: InMemoryTwinRepository) -> None:
    d1 = decision_at(twin)
    _, binding = gate.authorize(d1)
    assert binding is not None
    bump(twin, "P002")

    assert gate.recheck(d1, binding).verdict is DCGVerdict.ALLOW


def test_context_that_ages_out_before_commit_requires_refresh(
    gate: NoStaleCommit, twin: InMemoryTwinRepository, clock: Clock
) -> None:
    d1 = decision_at(twin)
    _, binding = gate.authorize(d1)
    assert binding is not None
    clock.now = binding.expiry + timedelta(seconds=1)

    result = gate.recheck(d1, binding)
    assert (result.verdict, result.reason_code) == (DCGVerdict.REFRESH_REQUIRED, CONTEXT_EXPIRED)


def test_changed_actions_do_not_match_the_binding(
    gate: NoStaleCommit, twin: InMemoryTwinRepository, clock: Clock, audit: InMemoryGuardAudit
) -> None:
    d1 = decision_at(twin)
    _, binding = gate.authorize(d1)
    assert binding is not None
    altered = d1.model_copy(update={"proposed_actions": [ReplenishShelf(sku="P001", quantity=7)]})
    clock.now = T0 + timedelta(seconds=1)

    result = gate.recheck(altered, binding)

    assert (result.verdict, result.reason_code) == (DCGVerdict.DENY, BINDING_MISMATCH)
    assert result.policy_result["failed_gate"] == "binding"
    assert result.policy_result["checks"][-1]["gate"] == "binding"
    assert result.expiry == T0 + timedelta(seconds=1)
    assert audit.events("dec-1")[-1].reason_code == BINDING_MISMATCH


def test_binding_for_another_decision_is_refused(gate: NoStaleCommit, twin: InMemoryTwinRepository) -> None:
    _, binding = gate.authorize(decision_at(twin))
    assert binding is not None
    other = decision_at(twin, decision_id="dec-2", proposed_actions=[ChangeFacings(sku="P001", facings=3)])

    assert gate.recheck(other, binding).reason_code == BINDING_MISMATCH


def test_denied_decision_gets_no_binding(gate: NoStaleCommit, twin: InMemoryTwinRepository, audit: InMemoryGuardAudit) -> None:
    result, binding = gate.authorize(decision_at(twin, sufficient=False))
    assert (result.verdict, result.reason_code, binding) == (DCGVerdict.DENY, INSUFFICIENT_EVIDENCE, None)
    assert len(audit.events()) == 1


def test_decision_without_evidence_is_audited_without_correlation(
    gate: NoStaleCommit, twin: InMemoryTwinRepository, audit: InMemoryGuardAudit
) -> None:
    gate.authorize(decision_at(twin, evidence=[]))
    [event] = audit.events()
    assert (event.correlation_id, event.store_id, event.verdict) == ("", "", DCGVerdict.DENY)


def test_default_clock_is_utc(twin: InMemoryTwinRepository, audit: InMemoryGuardAudit) -> None:
    gate = NoStaleCommit(DecisionContextGuard(twin, clock=lambda: T0), audit)
    gate.authorize(decision_at(twin))
    assert audit.events()[0].at.tzinfo is not None
