"""In-memory Simulation Twin, backed by the store fixture.

This is not the Live Twin. It starts from the store's current view and applies
proposed actions to produce a simulated state. The store stays unchanged.

Once the Simulation Service (A07) and KPI evaluator (D11) are wired in, this
module becomes the adapter that calls them — the routes and the response contracts
stay the same.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from retailtwin_api.schemas import ProductInventory, StoreResponse


# ─── Enums (mirrors FE enums/simulation.enum.ts) ────────────────────────────

SIMULATION_STATUSES = {"pending", "evaluated", "committed", "rejected"}
ACTION_TYPES = {"move_product", "change_facings", "replenish_shelf"}


# ─── Pydantic models ────────────────────────────────────────────────────────

class SimActionMove(BaseModel):
    type: Literal["move_product"] = "move_product"
    sku: str
    from_slot: str
    to_slot: str


class SimActionFacings(BaseModel):
    type: Literal["change_facings"] = "change_facings"
    sku: str
    facings: int = Field(ge=1)


class SimActionReplenish(BaseModel):
    type: Literal["replenish_shelf"] = "replenish_shelf"
    sku: str
    quantity: int = Field(ge=1)


SimulationAction = SimActionMove | SimActionFacings | SimActionReplenish


class SimulationSummary(BaseModel):
    simulation_id: str
    store_id: str
    base_context_version: str
    status: str


class SimulationDetail(BaseModel):
    simulation_id: str
    store_id: str
    base_context_version: str
    status: str
    actions: list[SimulationAction]
    state: StoreResponse


# ─── Helpers ────────────────────────────────────────────────────────────────

_HOLDER_RE = re.compile(r"^(?P<holder>.+)-\w+$")


def _holder_of(slot_id: str) -> str:
    m = _HOLDER_RE.match(slot_id)
    return m.group("holder") if m else slot_id.rsplit("-", 1)[0]


def _apply(product: ProductInventory, action: SimulationAction) -> ProductInventory:
    if action.type == "replenish_shelf":
        qty = min(action.quantity, product.backroom_quantity)
        return product.model_copy(
            update={
                "shelf_quantity": product.shelf_quantity + qty,
                "backroom_quantity": product.backroom_quantity - qty,
            }
        )
    elif action.type == "change_facings":
        return product.model_copy(update={"facings": action.facings})
    elif action.type == "move_product":
        return product.model_copy(
            update={
                "shelf_id": _holder_of(action.to_slot),
                "slot_id": action.to_slot,
            }
        )
    return product


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_state(
    base: StoreResponse, actions: list[SimulationAction]
) -> StoreResponse:
    products = []
    seen: set[str] = set()
    for product in base.products:
        affected = [a for a in actions if a.sku == product.sku]
        p = product
        for a in affected:
            p = _apply(p, a)
        products.append(
            p.model_copy(
                update={
                    "version": product.version + (1 if affected else 0)
                }
            )
        )
        seen.add(product.sku)
    return StoreResponse(
        store_id=base.store_id,
        context_version=f"{base.context_version}+sim:{_stamp()}",
        version=base.version,
        products=products,
    )


# ─── Seed simulation ─────────────────────────────────────────────────────────

"""The simulation seeded at startup.

A meaningful demo run: move P001 from A01-S01 → A01-S02 and increase its facings.
The store fixture only has P001, so this is always applicable.
"""
SEED_SIMULATION_ID = "sim-seed-001"
SEED_ACTIONS: list[SimulationAction] = [
    SimActionMove(sku="P001", from_slot="A01-S01", to_slot="A01-S02"),
    SimActionFacings(sku="P001", facings=5),
]


# ─── SimulationRepository ────────────────────────────────────────────────────

class SimulationRepository:
    """In-memory simulation runs.

    Today the simulations are seeded at startup. When A07 / D11 are wired in, this
    class calls them instead of applying in-memory actions.

    If the store fixture is not loaded (fixture unavailable, or Firestore not ready),
    the repository enters a degraded state: list returns empty and get returns None.
    """

    def __init__(self, store_view_fn, store_id: str) -> None:
        self._store_view_fn = store_view_fn
        self._store_id = store_id
        self._runs: dict[str, SimulationDetail] = {}
        self._available = False
        self._seed()

    def _seed(self) -> None:
        """Seed one open simulation from the store fixture.

        If the store is not loaded yet (fixture missing, Firestore not ready), the
        repository stays degraded — callers get empty results.
        """
        try:
            base = self._store_view_fn()
        except RuntimeError:
            # Store not loaded. The simulation routes will return 503 or empty lists.
            return
        try:
            proposed_state = _build_state(base, SEED_ACTIONS)
        except Exception:
            # Fall back to the base state if actions cannot be applied.
            proposed_state = base
        self._runs[SEED_SIMULATION_ID] = SimulationDetail(
            simulation_id=SEED_SIMULATION_ID,
            store_id=self._store_id,
            base_context_version=base.context_version,
            status="pending",
            actions=SEED_ACTIONS,
            state=proposed_state,
        )
        self._available = True

    # ── read ────────────────────────────────────────────────────────────────

    def list_open(self) -> list[SimulationSummary]:
        if not self._available:
            return []
        return [
            SimulationSummary(
                simulation_id=run.simulation_id,
                store_id=run.store_id,
                base_context_version=run.base_context_version,
                status=run.status,
            )
            for run in self._runs.values()
            if run.status in {"pending", "evaluated"}
        ]

    def get(self, simulation_id: str) -> SimulationDetail | None:
        if not self._available:
            return None
        return self._runs.get(simulation_id)

    def summary(self, simulation_id: str) -> SimulationSummary | None:
        if not self._available:
            return None
        run = self._runs.get(simulation_id)
        if run is None:
            return None
        return SimulationSummary(
            simulation_id=run.simulation_id,
            store_id=run.store_id,
            base_context_version=run.base_context_version,
            status=run.status,
        )
