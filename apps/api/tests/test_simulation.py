<<<<<<< HEAD
from retailtwin_api.demo_runtime.services.simulation import SimulationService
from retailtwin_api.demo_runtime.services.twin import TwinService
import pytest

def test_simulation_service():
    twin = TwinService()
    twin.load_from_store([
        {"slot_id": "s1", "sku": "sku1", "facings": 1, "shelf_quantity": 10, "backroom_quantity": 5},
        {"slot_id": "s2", "sku": "sku1", "facings": 1, "shelf_quantity": 10, "backroom_quantity": 5}
    ])
    sim = SimulationService(twin)
    snap = sim.clone()
    
    # Test apply - facings
    sim.apply(snap, [
        {"action_type": "facings", "slot_id": "s1", "facings": 5}
    ])
    assert snap.slots["s1"].facings == 5
    
    # Test apply - replenish
    sim.apply(snap, [
        {"action_type": "replenish", "slot_id": "s2", "quantity": 10}
    ])
    assert snap.slots["s2"].shelf_quantity == 20
    
    # Test apply - move
    sim.apply(snap, [
        {"action_type": "move", "slot_id": "s1", "from_slot_id": "s1", "to_slot_id": "s2", "quantity": 2}
    ])
    assert snap.slots["s1"].shelf_quantity == 8
    assert snap.slots["s2"].shelf_quantity == 22
    
    # Test evaluate
    kpi = sim.evaluate(snap)
    assert kpi.total_shelf_quantity == 30

def test_simulation_apply_missing_slot():
    twin = TwinService()
    sim = SimulationService(twin)
    snap = sim.clone()
    
    results = sim.apply(snap, [
        {"action_type": "facings", "slot_id": "n/a", "facings": 5}
    ])
    assert len(results) == 1
    assert results[0].slot_id == "n/a"
=======
"""Tests for GET /simulations and GET /simulations/{simulation_id}."""

import pytest
from starlette.testclient import TestClient


class TestListSimulations:
    def test_returns_list(self, client: TestClient) -> None:
        response = client.get("/simulations")
        assert response.status_code == 200
        data = response.json()
        assert "simulations" in data
        assert isinstance(data["simulations"], list)
        assert len(data["simulations"]) == 1

    def test_returns_seed_simulation(self, client: TestClient) -> None:
        response = client.get("/simulations")
        data = response.json()["simulations"][0]
        assert data["simulation_id"] == "sim-seed-001"
        assert data["store_id"] == "store-001"
        assert data["status"] == "pending"
        assert "base_context_version" in data

    def test_filter_by_open_returns_seed(self, client: TestClient) -> None:
        response = client.get("/simulations?status=open")
        assert response.status_code == 200
        data = response.json()["simulations"]
        ids = [s["simulation_id"] for s in data]
        assert "sim-seed-001" in ids

    def test_filter_by_unknown_status_returns_empty(self, client: TestClient) -> None:
        response = client.get("/simulations?status=rejected")
        assert response.status_code == 200
        assert response.json()["simulations"] == []


class TestGetSimulation:
    def test_returns_detail(self, client: TestClient) -> None:
        response = client.get("/simulations/sim-seed-001")
        assert response.status_code == 200
        data = response.json()
        assert data["simulation_id"] == "sim-seed-001"
        assert data["store_id"] == "store-001"
        assert data["status"] == "pending"
        assert "base_context_version" in data
        assert "state" in data
        assert "actions" in data

    def test_actions_have_correct_types(self, client: TestClient) -> None:
        response = client.get("/simulations/sim-seed-001")
        actions = response.json()["actions"]
        assert len(actions) == 2
        types = {a["type"] for a in actions}
        assert "move_product" in types
        assert "change_facings" in types

    def test_move_action_has_required_fields(self, client: TestClient) -> None:
        response = client.get("/simulations/sim-seed-001")
        actions = response.json()["actions"]
        move = next(a for a in actions if a["type"] == "move_product")
        assert move["sku"] == "P001"
        assert move["from_slot"] == "A01-S01"
        assert move["to_slot"] == "A01-S02"

    def test_facings_action_has_required_fields(self, client: TestClient) -> None:
        response = client.get("/simulations/sim-seed-001")
        actions = response.json()["actions"]
        facings = next(a for a in actions if a["type"] == "change_facings")
        assert facings["sku"] == "P001"
        assert facings["facings"] == 5

    def test_proposed_state_differs_from_base(self, client: TestClient) -> None:
        response = client.get("/simulations/sim-seed-001")
        data = response.json()
        state = data["state"]
        assert state["store_id"] == "store-001"
        assert state["context_version"].startswith("store-001:v1+sim:")
        products = {p["sku"]: p for p in state["products"]}
        # The simulation moves P001 to A01-S02 and gives it 5 facings.
        assert products["P001"]["slot_id"] == "A01-S02"
        assert products["P001"]["facings"] == 5
        assert products["P001"]["shelf_quantity"] == 8  # unchanged

    def test_not_found_returns_404(self, client: TestClient) -> None:
        response = client.get("/simulations/nonexistent-id")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "simulation_not_found"


class TestSimulationStaysReadOnly:
    def test_get_does_not_mutate_simulation(self, client: TestClient) -> None:
        # Read the simulation twice.
        first = client.get("/simulations/sim-seed-001").json()
        second = client.get("/simulations/sim-seed-001").json()
        # Status should not change from reads.
        assert first["status"] == second["status"] == "pending"
        # The context_version may differ (timestamp), but the slot_id should not.
        assert first["state"]["products"][0]["slot_id"] == second["state"]["products"][0]["slot_id"] == "A01-S02"
>>>>>>> e122bcf (feat: calculate deterministic stockout risk and wire simulation API routes)
