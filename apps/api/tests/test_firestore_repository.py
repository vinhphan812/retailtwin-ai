"""Tests for FirestoreRepository."""
from __future__ import annotations

import pytest
from unittest.mock import patch

from retailtwin_api.firestore_repository import FirestoreRepository


class TestFirestoreRepositoryInit:
    def test_init_sets_project_id_and_store_id(self) -> None:
        repo = FirestoreRepository(project_id="test-project", store_id="store-001")
        assert repo.project_id == "test-project"
        assert repo.store_id == "store-001"
        assert repo.loaded is True
        assert repo.error is None


class TestFirestoreRepositoryView:
    def test_view_returns_store_response(self) -> None:
        repo = FirestoreRepository(project_id="test-project", store_id="store-001")
        mock_response = {
            "fields": {
                "version": {"stringValue": "v3"},
                "context_version": {"stringValue": "ctx-2"},
            }
        }
        with patch.object(repo, "_call", return_value=mock_response):
            result = repo.view()
        assert result.store_id == "store-001"
        assert result.version == "v3"
        assert result.context_version == "ctx-2"
        assert result.products == []

    def test_view_uses_version_when_context_version_missing(self) -> None:
        repo = FirestoreRepository(project_id="test-project", store_id="store-001")
        mock_response = {
            "fields": {
                "version": {"stringValue": "v5"},
            }
        }
        with patch.object(repo, "_call", return_value=mock_response):
            result = repo.view()
        assert result.version == "v5"
        assert result.context_version == "v5"

    def test_view_raises_on_error(self) -> None:
        repo = FirestoreRepository(project_id="test-project", store_id="store-001")
        mock_response = {"error": "Not found"}
        with patch.object(repo, "_call", return_value=mock_response):
            with pytest.raises(RuntimeError, match="Firestore Live Twin unavailable"):
                repo.view()


class TestFirestoreRepositoryInventory:
    def test_inventory_returns_product_inventory(self) -> None:
        repo = FirestoreRepository(project_id="test-project", store_id="store-001")
        mock_response = {
            "fields": {
                "sku": {"stringValue": "P017"},
                "shelf_id": {"stringValue": "S-A1"},
                "slot_id": {"stringValue": "slot-3"},
                "facings": {"integerValue": "4"},
                "shelf_quantity": {"integerValue": "12"},
                "backroom_quantity": {"integerValue": "30"},
                "version": {"integerValue": "7"},
            }
        }
        with patch.object(repo, "_call", return_value=mock_response):
            result = repo.inventory("P017")
        assert result is not None
        assert result.store_id == "store-001"
        assert result.sku == "P017"
        assert result.shelf_id == "S-A1"
        assert result.slot_id == "slot-3"
        assert result.facings == 4
        assert result.shelf_quantity == 12
        assert result.backroom_quantity == 30
        assert result.version == 7

    def test_inventory_returns_none_on_error(self) -> None:
        repo = FirestoreRepository(project_id="test-project", store_id="store-001")
        with patch.object(repo, "_call", return_value={"error": "Not found"}):
            result = repo.inventory("P017")
        assert result is None

    def test_inventory_handles_missing_fields(self) -> None:
        repo = FirestoreRepository(project_id="test-project", store_id="store-001")
        mock_response: dict = {"fields": {}}
        with patch.object(repo, "_call", return_value=mock_response):
            result = repo.inventory("P017")
        assert result is not None
        assert result.sku == "P017"
        assert result.shelf_id == ""
        assert result.slot_id == ""
        assert result.facings == 0
        assert result.shelf_quantity == 0
        assert result.backroom_quantity == 0
        assert result.version == 0

    def test_inventory_handles_non_integer_values(self) -> None:
        repo = FirestoreRepository(project_id="test-project", store_id="store-001")
        mock_response = {
            "fields": {
                "facings": {"integerValue": "not-a-number"},
                "shelf_quantity": {},
                "version": {"integerValue": "1.5"},
            }
        }
        with patch.object(repo, "_call", return_value=mock_response):
            result = repo.inventory("P017")
        assert result is not None
        assert result.facings == 0  # invalid string -> 0
        assert result.shelf_quantity == 0  # missing field -> 0
        assert result.backroom_quantity == 0  # missing field -> 0
        assert result.version == 0  # "1.5" not parseable -> 0
