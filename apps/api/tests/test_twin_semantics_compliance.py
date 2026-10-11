import pytest
from services.twin import InMemoryTwinService

FIXTURES = [
    {"slot_id": "s01", "sku": "P001", "facings": 4, "shelf_quantity": 20, "backroom_quantity": 50},
]

def test_apply_replenish_decrements_backroom_quantity():
    twin = InMemoryTwinService("store-001")
    twin.reset(FIXTURES)
    
    # Replenish 5 items
    twin.apply_replenish("s01", 5)
    
    slot = twin.read_slot("s01")
    assert slot.shelf_quantity == 25  # 20 + 5
    assert slot.backroom_quantity == 45  # 50 - 5, THIS is what we need to enforce
