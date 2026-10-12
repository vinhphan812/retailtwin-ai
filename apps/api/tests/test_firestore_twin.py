"""Tests for the Firestore Live Twin boundary.

These tests use the InMemoryTwinRepository to avoid any dependency on
a live Firestore instance. The production FirestoreLiveTwinRepository
is tested via the same interface contract.
"""

from datetime import datetime, timezone
from collections.abc import Mapping

import pytest

from retailtwin_api.firestore_twin import (
    COLLECTION_INVENTORY,
    COLLECTION_STORE,
    InMemoryTwinRepository,
    InventoryDocument,
    InventorySeed,
    LiveTwinRepository,
    StoreDocument,
    TwinConflict,
    TwinNotFound,
    TwinUnavailable,
    _bump_version,
)


class TestInMemoryTwinRepository:
    """Unit tests for InMemoryTwinRepository."""

    def test_get_store_returns_none_when_empty(self) -> None:
        repo = InMemoryTwinRepository()
        assert repo.get_store("store-001") is None

    def test_get_store_returns_store_when_seeded(self) -> None:
        repo = InMemoryTwinRepository()
        repo.seed("store-001", "v1", [])
        doc = repo.get_store("store-001")
        assert doc is not None
        assert doc.store_id == "store-001"
        assert doc.version == "v1"

    def test_seed_is_idempotent(self) -> None:
        repo = InMemoryTwinRepository()
        repo.seed("store-001", "v1", [
            InventorySeed(sku="P001", shelf_id="A01", slot_id="A01-S01",
                         facings=3, shelf_quantity=8, backroom_quantity=42),
        ])
        repo.seed("store-001", "v2", [
            InventorySeed(sku="P001", shelf_id="A01", slot_id="A01-S01",
                         facings=5, shelf_quantity=10, backroom_quantity=50),
        ])
        doc = repo.get_store("store-001")
        assert doc is not None
        assert doc.version == "v2"
        inv = repo.get_inventory("store-001", "P001")
        assert inv is not None
        assert inv.facings == 5

    def test_list_inventory_returns_empty_when_no_items(self) -> None:
        repo = InMemoryTwinRepository()
        repo.seed("store-001", "v1", [])
        items = repo.list_inventory("store-001")
        assert items == []

    def test_list_inventory_returns_all_items(self) -> None:
        repo = InMemoryTwinRepository()
        repo.seed("store-001", "v1", [
            InventorySeed(sku="P001", shelf_id="A01", slot_id="A01-S01",
                         facings=3, shelf_quantity=8, backroom_quantity=42),
            InventorySeed(sku="P002", shelf_id="A02", slot_id="A02-S01",
                         facings=2, shelf_quantity=5, backroom_quantity=20),
        ])
        items = repo.list_inventory("store-001")
        assert len(items) == 2
        skus = {item.sku for item in items}
        assert skus == {"P001", "P002"}

    def test_get_inventory_returns_item(self) -> None:
        repo = InMemoryTwinRepository()
        repo.seed("store-001", "v1", [
            InventorySeed(sku="P001", shelf_id="A01", slot_id="A01-S01",
                         facings=3, shelf_quantity=8, backroom_quantity=42),
        ])
        item = repo.get_inventory("store-001", "P001")
        assert item is not None
        assert item.sku == "P001"
        assert item.shelf_quantity == 8
        assert item.backroom_quantity == 42
        assert item.version == 1

    def test_get_inventory_returns_none_for_unknown_sku(self) -> None:
        repo = InMemoryTwinRepository()
        repo.seed("store-001", "v1", [])
        item = repo.get_inventory("store-001", "P999")
        assert item is None

    def test_upsert_inventory_creates_new_item(self) -> None:
        repo = InMemoryTwinRepository()
        repo.seed("store-001", "v1", [])
        item = InventoryDocument(
            store_id="store-001",
            sku="P001",
            shelf_id="A01",
            slot_id="A01-S01",
            facings=3,
            shelf_quantity=8,
            backroom_quantity=42,
            version=1,
            updated_at=datetime.now(timezone.utc),
        )
        result = repo.upsert_inventory(item, expected_version=None)
        assert result.sku == "P001"
        assert result.version == 1

    def test_upsert_inventory_updates_existing_item(self) -> None:
        repo = InMemoryTwinRepository()
        repo.seed("store-001", "v1", [
            InventorySeed(sku="P001", shelf_id="A01", slot_id="A01-S01",
                         facings=3, shelf_quantity=8, backroom_quantity=42),
        ])
        item = InventoryDocument(
            store_id="store-001",
            sku="P001",
            shelf_id="A01",
            slot_id="A01-S01",
            facings=5,
            shelf_quantity=10,
            backroom_quantity=50,
            version=2,
            updated_at=datetime.now(timezone.utc),
        )
        result = repo.upsert_inventory(item, expected_version=1)
        assert result.facings == 5
        assert result.version == 2

    def test_upsert_inventory_raises_conflict_when_stored_version_differs(self) -> None:
        """expected_version causes conflict when the stored version does NOT match it."""
        repo = InMemoryTwinRepository()
        repo.seed("store-001", "v1", [
            InventorySeed(sku="P001", shelf_id="A01", slot_id="A01-S01",
                         facings=3, shelf_quantity=8, backroom_quantity=42),
        ])
        # The seeded P001 has version=1. Passing expected_version=99 should conflict.
        item = InventoryDocument(
            store_id="store-001",
            sku="P001",
            shelf_id="A01",
            slot_id="A01-S01",
            facings=5,
            shelf_quantity=10,
            backroom_quantity=50,
            version=99,  # New version number in the payload
            updated_at=datetime.now(timezone.utc),
        )
        with pytest.raises(TwinConflict) as exc_info:
            repo.upsert_inventory(item, expected_version=99)  # We expect 99, but stored is 1
        assert exc_info.value.sku == "P001"
        assert exc_info.value.stored_version == 1
        assert exc_info.value.incoming_version == 99

    def test_reset_clears_inventory(self) -> None:
        repo = InMemoryTwinRepository()
        repo.seed("store-001", "v1", [
            InventorySeed(sku="P001", shelf_id="A01", slot_id="A01-S01",
                         facings=3, shelf_quantity=8, backroom_quantity=42),
        ])
        repo.reset("store-001")
        items = repo.list_inventory("store-001")
        assert items == []
        store = repo.get_store("store-001")
        assert store is not None
        assert store.version == "v2"  # Version was bumped

    def test_reset_is_idempotent(self) -> None:
        repo = InMemoryTwinRepository()
        repo.seed("store-001", "v1", [])
        repo.reset("store-001")
        repo.reset("store-001")  # Should not raise

    def test_is_available_returns_true(self) -> None:
        repo = InMemoryTwinRepository()
        assert repo.is_available() is True

    def test_thread_safety(self) -> None:
        import threading
        repo = InMemoryTwinRepository()
        repo.seed("store-001", "v1", [])
        errors: list[Exception] = []

        def writer(n: int) -> None:
            try:
                for i in range(50):
                    item = InventoryDocument(
                        store_id="store-001",
                        sku=f"P{n:03d}",
                        shelf_id="A01",
                        slot_id="A01-S01",
                        facings=i,
                        shelf_quantity=i,
                        backroom_quantity=i,
                        version=1,
                        updated_at=datetime.now(timezone.utc),
                    )
                    repo.upsert_inventory(item, expected_version=None)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == [], f"Thread safety violations: {errors}"


class TestStoreRepositoryAdapter:
    """Tests for the StoreRepository adapter over LiveTwinRepository."""

    def test_adapter_loads_from_firestore(self) -> None:
        from retailtwin_api.firestore_twin import StoreRepository
        live = InMemoryTwinRepository()
        live.seed("store-001", "v1", [
            InventorySeed(sku="P001", shelf_id="A01", slot_id="A01-S01",
                         facings=3, shelf_quantity=8, backroom_quantity=42),
        ])
        adapter = StoreRepository(live, "store-001")
        assert adapter.loaded is True
        assert adapter.store_id == "store-001"
        assert adapter.error is None

    def test_adapter_reports_unavailable_when_store_missing(self) -> None:
        from retailtwin_api.firestore_twin import StoreRepository
        live = InMemoryTwinRepository()
        adapter = StoreRepository(live, "store-001")
        assert adapter.loaded is False
        assert adapter.error is not None

    def test_adapter_view_returns_correct_structure(self) -> None:
        from retailtwin_api.firestore_twin import StoreRepository
        live = InMemoryTwinRepository()
        live.seed("store-001", "v1", [
            InventorySeed(sku="P001", shelf_id="A01", slot_id="A01-S01",
                         facings=3, shelf_quantity=8, backroom_quantity=42),
        ])
        adapter = StoreRepository(live, "store-001")
        view = adapter.view()
        assert view["store_id"] == "store-001"
        assert view["version"] == "v1"
        assert view["context_version"] == "store-001:v1"
        assert len(view["products"]) == 1
        assert view["products"][0]["sku"] == "P001"
        assert view["products"][0]["shelf_quantity"] == 8

    def test_adapter_inventory_returns_item(self) -> None:
        from retailtwin_api.firestore_twin import StoreRepository
        live = InMemoryTwinRepository()
        live.seed("store-001", "v1", [
            InventorySeed(sku="P001", shelf_id="A01", slot_id="A01-S01",
                         facings=3, shelf_quantity=8, backroom_quantity=42),
        ])
        adapter = StoreRepository(live, "store-001")
        inv = adapter.inventory("P001")
        assert inv is not None
        assert inv["sku"] == "P001"
        assert inv["backroom_quantity"] == 42

    def test_adapter_inventory_returns_none_for_unknown_sku(self) -> None:
        from retailtwin_api.firestore_twin import StoreRepository
        live = InMemoryTwinRepository()
        live.seed("store-001", "v1", [])
        adapter = StoreRepository(live, "store-001")
        inv = adapter.inventory("P999")
        assert inv is None

    def test_adapter_inventory_raises_when_not_loaded(self) -> None:
        from retailtwin_api.firestore_twin import StoreRepository
        live = InMemoryTwinRepository()
        adapter = StoreRepository(live, "store-001")
        assert adapter.loaded is False
        with pytest.raises(RuntimeError, match="not loaded"):
            adapter.view()


class TestBumpVersion:
    def test_bump_v1(self) -> None:
        assert _bump_version("v1") == "v2"

    def test_bump_v99(self) -> None:
        assert _bump_version("v99") == "v100"

    def test_bump_unknown_format(self) -> None:
        assert _bump_version("latest") == "v2"


class TestCanonicalPaths:
    """Verify canonical path constants match the specification."""

    def test_store_collection_name(self) -> None:
        assert COLLECTION_STORE == "store"

    def test_inventory_collection_name(self) -> None:
        assert COLLECTION_INVENTORY == "inventory"


class TestInventoryDocument:
    def test_to_product_inventory_returns_correct_dict(self) -> None:
        doc = InventoryDocument(
            store_id="store-001",
            sku="P001",
            shelf_id="A01",
            slot_id="A01-S01",
            facings=3,
            shelf_quantity=8,
            backroom_quantity=42,
            version=1,
            updated_at=datetime.now(timezone.utc),
        )
        result = doc.to_product_inventory()
        assert result["store_id"] == "store-001"
        assert result["sku"] == "P001"
        assert result["shelf_id"] == "A01"
        assert result["slot_id"] == "A01-S01"
        assert result["facings"] == 3
        assert result["shelf_quantity"] == 8
        assert result["backroom_quantity"] == 42
        assert result["version"] == 1


class TestTwinConflict:
    def test_conflict_message(self) -> None:
        exc = TwinConflict("P001", 1, 3)
        assert exc.sku == "P001"
        assert exc.stored_version == 1
        assert exc.incoming_version == 3
        assert "P001" in str(exc)
        assert "conflict" in str(exc).lower()


class TestLiveTwinRepositoryInterface:
    """Verify InMemoryTwinRepository satisfies LiveTwinRepository."""

    def test_interface_methods_exist(self) -> None:
        repo: LiveTwinRepository = InMemoryTwinRepository()
        assert callable(repo.get_store)
        assert callable(repo.list_inventory)
        assert callable(repo.get_inventory)
        assert callable(repo.upsert_inventory)
        assert callable(repo.seed)
        assert callable(repo.reset)
        assert callable(repo.is_available)


# ---------------------------------------------------------------------------
# Fake HTTP transport for FirestoreLiveTwinRepository testing
# ---------------------------------------------------------------------------


class FakeHttpResponse:
    def __init__(self, status: int, body: str) -> None:
        self.status = status
        self.body = body


class FakeFirestoreTransport:
    """In-process fake of the Firestore REST API for unit testing."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, object | None]] = []
        self._documents: dict[str, dict[str, object]] = {}

    def request(
        self,
        method: str,
        url: str,
        payload: bytes | None,
        headers: Mapping[str, str],
    ) -> FakeHttpResponse:
        self.calls.append((method, url, payload))
        return self._handle(method, url, payload)

    def _handle(self, method: str, url: str, payload: bytes | None) -> FakeHttpResponse:
        import json

        # GET /store/{store_id}
        if method == "GET" and "/store/" in url and "/documents" in url:
            # URL: .../projects/{project}/databases/(default)/documents/store/{store_id}
            parts = url.split("/documents/")
            rest = parts[-1] if parts else ""  # "store/store-001"
            segments = rest.split("/")
            if len(segments) >= 2:
                key = f"{segments[0]}/{segments[1]}"  # "store/store-001"
            else:
                key = rest
            if key in self._documents:
                doc = self._documents[key]
                return FakeHttpResponse(200, json.dumps(doc))
            return FakeHttpResponse(404, json.dumps({"error": {"message": "Not found"}}))

        # GET /inventory/{store_id}
        if method == "GET" and "/inventory/" in url and "/documents" not in url:
            parts = url.split("/inventory/")
            store_id = parts[1] if len(parts) > 1 else ""
            docs = [v for k, v in self._documents.items() if k.startswith(f"inventory/{store_id}/")]
            return FakeHttpResponse(200, json.dumps({"documents": docs}))

        # POST /documents:commit
        if method == "POST" and ":commit" in url:
            if payload is None:
                return FakeHttpResponse(400, json.dumps({"error": {"message": "Empty payload"}}))
            data = json.loads(payload.decode())
            results = []
            for write in data.get("writes", []):
                if "update" in write:
                    name = write["update"]["name"]
                    fields = write["update"].get("fields", {})
                    doc: dict[str, object] = {"name": name, "fields": fields, "updateTime": "2026-01-01T00:00:00.000000Z"}
                    self._documents[name] = doc
                    results.append({"updateTime": "2026-01-01T00:00:00.000000Z"})
                elif "delete" in write:
                    name = write["delete"]
                    if name in self._documents:
                        del self._documents[name]
                    results.append({"delete": {}})

            return FakeHttpResponse(200, json.dumps({"writeResults": results}))

        # POST /documents/{collection}
        if method == "POST" and "/documents/" in url:
            if payload is None:
                return FakeHttpResponse(400, json.dumps({"error": {"message": "Empty payload"}}))
            return FakeHttpResponse(200, json.dumps({"name": url, "updateTime": "2026-01-01T00:00:00.000000Z"}))

        return FakeHttpResponse(404, json.dumps({"error": {"message": "Not found"}}))

    def seed_data(self, store_id: str, version: str, items: list[InventorySeed]) -> None:
        """Pre-populate the fake store."""
        import json
        now = "2026-01-01T00:00:00.000000Z"
        store_key = f"store/{store_id}"
        self._documents[store_key] = json.dumps({
            "name": f"projects/test/databases/(default)/documents/store/{store_id}",
            "fields": {
                "store_id": {"stringValue": store_id},
                "version": {"stringValue": version},
                "updated_at": {"timestampValue": now},
            },
            "updateTime": now,
        })

    def clear(self) -> None:
        self._documents.clear()
        self.calls.clear()


class TestFirestoreLiveTwinRepository:
    """Tests for FirestoreLiveTwinRepository using FakeFirestoreTransport."""

    def test_get_store_returns_none_when_missing(self) -> None:
        from retailtwin_api.firestore_twin import FirestoreLiveTwinRepository, TwinConfig
        from retailtwin_api.firestore_twin import HttpResponse

        transport = FakeFirestoreTransport()

        class Repo(FirestoreLiveTwinRepository):
            def _headers(self) -> dict[str, str]:
                return {"Authorization": "Bearer fake"}

        repo = Repo(TwinConfig(project="retailtwin-ai-511002", location="us-central1"), transport=transport)  # type: ignore[annotation-unchecked]
        result = repo.get_store("store-001")
        assert result is None

    def test_get_store_returns_store_when_exists(self) -> None:
        from retailtwin_api.firestore_twin import FirestoreLiveTwinRepository, TwinConfig

        transport = FakeFirestoreTransport()
        # Store with the key format the code uses (extracted from URL)
        transport._documents["store/store-001"] = {
            "name": "projects/retailtwin-ai-511002/databases/(default)/documents/store/store-001",
            "fields": {
                "store_id": {"stringValue": "store-001"},
                "version": {"stringValue": "v1"},
                "updated_at": {"timestampValue": "2026-01-01T00:00:00.000000Z"},
            },
            "updateTime": "2026-01-01T00:00:00.000000Z",
        }

        class Repo(FirestoreLiveTwinRepository):
            def _headers(self) -> dict[str, str]:
                return {"Authorization": "Bearer fake"}

        repo = Repo(TwinConfig(project="retailtwin-ai-511002", location="us-central1"), transport=transport)  # type: ignore[annotation-unchecked]
        result = repo.get_store("store-001")
        assert result is not None
        assert result.store_id == "store-001"
        assert result.version == "v1"

    def test_seed_writes_store_and_inventory(self) -> None:
        from retailtwin_api.firestore_twin import FirestoreLiveTwinRepository, InventorySeed, TwinConfig

        transport = FakeFirestoreTransport()

        class Repo(FirestoreLiveTwinRepository):
            def _headers(self) -> dict[str, str]:
                return {"Authorization": "Bearer fake"}

        repo = Repo(TwinConfig(project="retailtwin-ai-511002", location="us-central1"), transport=transport)  # type: ignore[annotation-unchecked]
        repo.seed("store-001", "v1", [
            InventorySeed(sku="P001", shelf_id="A01", slot_id="A01-S01",
                         facings=3, shelf_quantity=8, backroom_quantity=42),
        ])
        # Verify the commit was called
        assert any("commit" in call[1] for call in transport.calls)

    def test_reset_deletes_inventory(self) -> None:
        from retailtwin_api.firestore_twin import FirestoreLiveTwinRepository, InventorySeed, TwinConfig

        transport = FakeFirestoreTransport()

        class Repo(FirestoreLiveTwinRepository):
            def _headers(self) -> dict[str, str]:
                return {"Authorization": "Bearer fake"}

        repo = Repo(TwinConfig(project="retailtwin-ai-511002", location="us-central1"), transport=transport)  # type: ignore[annotation-unchecked]
        repo.seed("store-001", "v1", [
            InventorySeed(sku="P001", shelf_id="A01", slot_id="A01-S01",
                         facings=3, shelf_quantity=8, backroom_quantity=42),
        ])
        repo.reset("store-001")
        items = repo.list_inventory("store-001")
        assert items == []

    def test_is_available_returns_true_when_firestore_reachable(self) -> None:
        from retailtwin_api.firestore_twin import FirestoreLiveTwinRepository, TwinConfig
        import json

        transport = FakeFirestoreTransport()
        # Return 200 for a GET on the store collection
        transport._documents["projects/test/databases/(default)/documents/store"] = json.dumps({"documents": []})

        class Repo(FirestoreLiveTwinRepository):
            def _headers(self) -> dict[str, str]:
                return {"Authorization": "Bearer fake"}

        repo = Repo(TwinConfig(project="retailtwin-ai-511002", location="us-central1"), transport=transport)  # type: ignore[annotation-unchecked]
        assert repo.is_available() is True


class TestTwinConfig:
    def test_config_validates_allowed_project(self) -> None:
        from retailtwin_api.firestore_twin import TwinConfig, TwinConfigError
        config = TwinConfig(project="retailtwin-ai-511002", location="us-central1")
        assert config.validated().project == "retailtwin-ai-511002"

    def test_config_rejects_wrong_project(self) -> None:
        from retailtwin_api.firestore_twin import TwinConfig, TwinConfigError
        config = TwinConfig(project="wrong-project", location="us-central1")
        with pytest.raises(TwinConfigError):
            config.validated()


class TestDocPathHelpers:
    def test_bump_version(self) -> None:
        from retailtwin_api.firestore_twin import _bump_version
        assert _bump_version("v1") == "v2"
        assert _bump_version("v9") == "v10"
        assert _bump_version("v99") == "v100"
        assert _bump_version("bad") == "v2"


class TestTwinUnavailable:
    def test_twin_unavailable_message(self) -> None:
        from retailtwin_api.firestore_twin import TwinUnavailable
        exc = TwinUnavailable("connection refused")
        assert exc.reason == "connection refused"
        assert "connection refused" in str(exc)


class TestTwinNotFound:
    def test_twin_not_found_message(self) -> None:
        from retailtwin_api.firestore_twin import TwinNotFound
        exc = TwinNotFound("/store/999")
        assert exc.path == "/store/999"
        assert "/store/999" in str(exc)


class TestInventorySeedValidation:
    def test_seed_requires_positive_facings(self) -> None:
        from retailtwin_api.firestore_twin import InventorySeed
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            InventorySeed(sku="P001", shelf_id="A01", slot_id="A01-S01",
                          facings=-1, shelf_quantity=0, backroom_quantity=0)

    def test_seed_requires_positive_quantities(self) -> None:
        from retailtwin_api.firestore_twin import InventorySeed
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            InventorySeed(sku="P001", shelf_id="A01", slot_id="A01-S01",
                          facings=0, shelf_quantity=-1, backroom_quantity=0)


class TestHttpResponse:
    def test_http_response_slots(self) -> None:
        from retailtwin_api.firestore_twin import HttpResponse
        resp = HttpResponse(200, "body")
        assert resp.status == 200
        assert resp.body == "body"


class TestFirestoreField:
    def test_firestore_field_string_value(self) -> None:
        from retailtwin_api.firestore_twin import _FirestoreField
        f = _FirestoreField(stringValue="hello")
        assert f.stringValue == "hello"
        assert f.integerValue is None

    def test_firestore_field_integer_value(self) -> None:
        from retailtwin_api.firestore_twin import _FirestoreField
        f = _FirestoreField(integerValue="42")
        assert f.integerValue == "42"

    def test_firestore_field_boolean_value(self) -> None:
        from retailtwin_api.firestore_twin import _FirestoreField
        f = _FirestoreField(booleanValue=True)
        assert f.booleanValue is True

