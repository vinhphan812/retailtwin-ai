"""Unit tests for TwinService."""
import pytest
from datetime import datetime, timezone
from services.twin import TwinService, StoreState, SlotState


FIXTURES = [
    {"slot_id": "s01", "sku": "P001", "facings": 4, "shelf_quantity": 20, "backroom_quantity": 50},
    {"slot_id": "s02", "sku": "P017", "facings": 3, "shelf_quantity": 12, "backroom_quantity": 35},
]


class TestTwinService:
    def test_reset_loads_fixtures(self):
        twin = TwinService("store-001")
        twin.reset(FIXTURES)
        state = twin.read()
        assert state.store_id == "store-001"
        assert len(state.slots) == 2
        assert "s01" in state.slots
        assert state.slots["s01"].sku == "P001"

    def test_version_increments_on_mutation(self):
        twin = TwinService("store-001")
        twin.reset(FIXTURES)
        assert twin.get_version() == "0"
        twin.apply_facings("s01", 5)
        assert twin.get_version() == "1"
        twin.apply_replenish("s01", 10)
        assert twin.get_version() == "2"

    def test_context_version_changes_on_reset(self):
        twin = TwinService("store-001")
        twin.reset(FIXTURES)
        cv1 = twin.get_context_version()
        twin.reset(FIXTURES)
        cv2 = twin.get_context_version()
        assert cv1 != cv2

    def test_apply_facings(self):
        twin = TwinService("store-001")
        twin.reset(FIXTURES)
        twin.apply_facings("s01", 7)
        slot = twin.read_slot("s01")
        assert slot is not None
        assert slot.facings == 7
        assert slot.shelf_quantity == 20  # unchanged

    def test_apply_replenish(self):
        twin = TwinService("store-001")
        twin.reset(FIXTURES)
        twin.apply_replenish("s02", 5)
        slot = twin.read_slot("s02")
        assert slot is not None
        assert slot.shelf_quantity == 17  # 12 + 5

    def test_apply_move(self):
        twin = TwinService("store-001")
        twin.reset(FIXTURES)
        twin.apply_move("s01", "s02", 5)
        assert twin.read_slot("s01").shelf_quantity == 15  # 20 - 5
        assert twin.read_slot("s02").shelf_quantity == 17  # 12 + 5

    def test_read_sku(self):
        twin = TwinService("store-001")
        twin.reset(FIXTURES)
        slots = twin.read_sku("P017")
        assert len(slots) == 1
        assert slots[0].slot_id == "s02"

    def test_read_returns_copy(self):
        twin = TwinService("store-001")
        twin.reset(FIXTURES)
        state1 = twin.read()
        twin.apply_facings("s01", 99)
        state2 = twin.read()
        assert state1.slots["s01"].facings == 4
        assert state2.slots["s01"].facings == 99

    def test_slot_not_found(self):
        twin = TwinService("store-001")
        twin.reset(FIXTURES)
        with pytest.raises(KeyError):
            twin.apply_facings("nonexistent", 5)
