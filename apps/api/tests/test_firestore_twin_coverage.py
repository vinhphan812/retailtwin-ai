"""Additional tests for firestore_twin helper functions and UrllibTransport.

Tests error paths, malformed data, and edge cases that improve coverage
of the helper layer. FirestoreLiveTwinRepository integration tests
(requiring a live gcloud runner) are covered by the InMemoryTwinRepository
interface contract tests in test_firestore_twin.py.
"""
from __future__ import annotations

import json
import urllib.error
from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import patch

import pytest

from retailtwin_api.firestore_twin import (
    COLLECTION_INVENTORY,
    InMemoryTwinRepository,
    InventoryDocument,
    TwinConfig,
    TwinConflict,
    TwinUnavailable,
    UrllibTransport,
    _bool_field,
    _database_root,
    _doc_name,
    _doc_path,
    _http_error,
    _int_field,
    _opt_string_field,
    _precondition_conflict,
    _string_field,
    _timestamp,
)


class TestDatabaseRoot:
    def test_database_root(self) -> None:
        assert _database_root("my-project") == (
            "https://firestore.googleapis.com/v1/projects/my-project"
            "/databases/(default)/documents"
        )


class TestDocName:
    def test_doc_name_no_path(self) -> None:
        config = TwinConfig(project="test-project")
        result = _doc_name(config, "stores")
        assert "projects/test-project" in result
        assert "stores" in result

    def test_doc_name_with_path(self) -> None:
        config = TwinConfig(project="test-project")
        result = _doc_name(config, "stores", "store-001")
        assert "stores/store-001" in result

    def test_doc_name_multiple_path(self) -> None:
        config = TwinConfig(project="test-project")
        result = _doc_name(config, COLLECTION_INVENTORY, "store-001", "P017")
        assert "inventory/store-001/P017" in result


class TestDocPath:
    def test_doc_path_no_path(self) -> None:
        assert _doc_path("stores") == "stores/"

    def test_doc_path_with_path(self) -> None:
        assert _doc_path("stores", "store-001") == "stores/store-001"

    def test_doc_path_multiple_path(self) -> None:
        assert _doc_path("inventory", "store-001", "P017") == "inventory/store-001/P017"


class TestHttpError:
    def test_http_error_with_json_error_message(self) -> None:
        # _http_error returns (not raises) a TwinUnavailable
        body = '{"error": {"message": "Document not found"}}'
        exc = _http_error("get_store", 404, body)
        assert isinstance(exc, TwinUnavailable)
        assert "Document not found" in str(exc)

    def test_http_error_with_non_json_body(self) -> None:
        body = "Internal Server Error"
        exc = _http_error("get_store", 500, body)
        assert isinstance(exc, TwinUnavailable)
        assert "Internal Server Error" in str(exc)

    def test_http_error_with_truncated_long_body(self) -> None:
        long_body = "x" * 500
        exc = _http_error("get_store", 500, long_body)
        assert isinstance(exc, TwinUnavailable)
        # Body is truncated to 200 chars
        assert "xxxx" in str(exc)

    def test_http_error_with_json_but_no_message(self) -> None:
        # _http_error always raises TwinUnavailable with "{action} failed (HTTP {status})"
        body = '{"error": {"code": 404}}'
        exc = _http_error("get_store", 404, body)
        assert isinstance(exc, TwinUnavailable)
        assert "get_store failed" in str(exc)

    def test_http_error_with_json_but_error_not_dict(self) -> None:
        body = '{"error": "just a string"}'
        exc = _http_error("get_store", 404, body)
        assert isinstance(exc, TwinUnavailable)
        assert "get_store failed" in str(exc)


class TestPreconditionConflict:
    def test_precondition_conflict_returns_true_for_409(self) -> None:
        assert _precondition_conflict(409, "{}") is True

    def test_precondition_conflict_returns_false_for_other_status(self) -> None:
        assert _precondition_conflict(400, "{}") is False
        assert _precondition_conflict(200, "{}") is False
        assert _precondition_conflict(500, "{}") is False

    def test_precondition_conflict_false_when_400_non_precondition(self) -> None:
        body = '{"error": {"status": "INVALID_ARGUMENT"}}'
        assert _precondition_conflict(400, body) is False

    def test_precondition_conflict_true_when_400_failed_precondition(self) -> None:
        body = '{"error": {"status": "FAILED_PRECONDITION"}}'
        assert _precondition_conflict(400, body) is True

    def test_precondition_conflict_true_when_400_already_exists(self) -> None:
        body = '{"error": {"status": "ALREADY_EXISTS"}}'
        assert _precondition_conflict(400, body) is True

    def test_precondition_conflict_false_when_non_json(self) -> None:
        assert _precondition_conflict(400, "not json") is False

    def test_precondition_conflict_false_when_error_not_dict(self) -> None:
        body = '{"error": "just a string"}'
        assert _precondition_conflict(400, body) is False


class TestTimestamp:
    def test_timestamp_with_z_suffix(self) -> None:
        dt = _timestamp("2026-01-01T12:00:00Z")
        assert dt.year == 2026
        assert dt.month == 1
        assert dt.day == 1
        assert dt.tzinfo is not None

    def test_timestamp_without_z_suffix(self) -> None:
        dt = _timestamp("2026-01-01T12:00:00+00:00")
        assert dt.year == 2026

    def test_timestamp_without_tz(self) -> None:
        dt = _timestamp("2026-01-01T12:00:00")
        assert dt.year == 2026
        assert dt.tzinfo is not None

    def test_timestamp_raises_on_invalid_format(self) -> None:
        with pytest.raises(TwinUnavailable, match="Unreadable timestamp"):
            _timestamp("not-a-timestamp")


class TestStringField:
    def test_string_field_returns_value(self) -> None:
        from retailtwin_api.firestore_twin import _FirestoreField
        fields = {"name": _FirestoreField(stringValue="hello")}
        assert _string_field(fields, "name") == "hello"

    def test_string_field_raises_on_missing(self) -> None:
        from retailtwin_api.firestore_twin import _FirestoreField
        fields: dict[str, _FirestoreField] = {}
        with pytest.raises(TwinUnavailable, match="Document field 'name' is missing"):
            _string_field(fields, "name")

    def test_string_field_raises_on_none_value(self) -> None:
        from retailtwin_api.firestore_twin import _FirestoreField
        fields = {"name": _FirestoreField()}
        with pytest.raises(TwinUnavailable, match="Document field 'name' is missing"):
            _string_field(fields, "name")


class TestIntField:
    def test_int_field_returns_int(self) -> None:
        from retailtwin_api.firestore_twin import _FirestoreField
        fields = {"qty": _FirestoreField(integerValue="42")}
        assert _int_field(fields, "qty") == 42

    def test_int_field_raises_on_missing(self) -> None:
        from retailtwin_api.firestore_twin import _FirestoreField
        fields: dict[str, _FirestoreField] = {}
        with pytest.raises(TwinUnavailable, match="Document field 'qty' is missing"):
            _int_field(fields, "qty")

    def test_int_field_raises_on_none_value(self) -> None:
        from retailtwin_api.firestore_twin import _FirestoreField
        fields = {"qty": _FirestoreField()}
        with pytest.raises(TwinUnavailable, match="Document field 'qty' is missing"):
            _int_field(fields, "qty")


class TestOptStringField:
    def test_opt_string_field_returns_value(self) -> None:
        from retailtwin_api.firestore_twin import _FirestoreField
        fields = {"opt": _FirestoreField(stringValue="hello")}
        assert _opt_string_field(fields, "opt") == "hello"

    def test_opt_string_returns_none_for_missing(self) -> None:
        from retailtwin_api.firestore_twin import _FirestoreField
        fields: dict[str, _FirestoreField] = {}
        assert _opt_string_field(fields, "opt") is None

    def test_opt_string_returns_none_for_none_value(self) -> None:
        from retailtwin_api.firestore_twin import _FirestoreField
        fields = {"opt": _FirestoreField()}
        assert _opt_string_field(fields, "opt") is None


class TestBoolField:
    def test_bool_field_true(self) -> None:
        from retailtwin_api.firestore_twin import _FirestoreField
        fields = {"flag": _FirestoreField(booleanValue=True)}
        assert _bool_field(fields, "flag") is True

    def test_bool_field_false(self) -> None:
        from retailtwin_api.firestore_twin import _FirestoreField
        fields = {"flag": _FirestoreField(booleanValue=False)}
        assert _bool_field(fields, "flag") is False

    def test_bool_field_raises_on_missing(self) -> None:
        from retailtwin_api.firestore_twin import _FirestoreField
        fields: dict[str, _FirestoreField] = {}
        with pytest.raises(TwinUnavailable, match="Document field 'flag' is missing"):
            _bool_field(fields, "flag")


class TestUrllibTransport:
    def test_request_returns_response_on_success(self) -> None:
        transport = UrllibTransport()
        body = b'{"ok": true}'

        class FakeResponse:
            status = 200

            def read(self, n: int | None = None) -> bytes:
                return body

            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, *a: object) -> None:
                pass

        with patch("urllib.request.urlopen", return_value=FakeResponse()):
            resp = transport.request("GET", "https://example.com", None, {})  # type: ignore[arg-type]
            assert resp.status == 200
            assert resp.body == '{"ok": true}'

    def test_request_returns_httpresponse_on_http_error(self) -> None:
        transport = UrllibTransport()
        body = b'{"error": "not found"}'

        class FakeHTTPError(urllib.error.HTTPError):
            def __init__(self) -> None:
                super().__init__(
                    "url", 404, "Not Found",
                    {"Content-Type": "application/json"},  # type: ignore[arg-type]
                    BytesIO(body)
                )

            def read(self, n: int | None = None) -> bytes:  # type: ignore[override]
                return body

        with patch("urllib.request.urlopen", side_effect=FakeHTTPError()):
            resp = transport.request("GET", "https://example.com", None, {})  # type: ignore[arg-type]
            assert resp.status == 404
            assert "not found" in resp.body

    def test_request_raises_twin_unavailable_on_url_error(self) -> None:
        transport = UrllibTransport()
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("Connection refused")
        ):
            with pytest.raises(TwinUnavailable, match="Connection refused"):
                transport.request("GET", "https://example.com", None, {})  # type: ignore[arg-type]


class TestInMemoryTwinRepository:
    @pytest.fixture
    def repo(self) -> InMemoryTwinRepository:
        return InMemoryTwinRepository()

    def test_get_inventory_returns_none_for_unknown_sku(self, repo: InMemoryTwinRepository) -> None:
        # InMemoryTwinRepository returns None, does not raise
        assert repo.get_inventory("store-001", "P999") is None

    def test_get_store_returns_none_for_unknown_store(self, repo: InMemoryTwinRepository) -> None:
        # InMemoryTwinRepository returns None, does not raise
        assert repo.get_store("store-999") is None

    def test_upsert_inventory_raises_conflict_wrong_version(
        self, repo: InMemoryTwinRepository
    ) -> None:
        item = InventoryDocument(
            store_id="store-001", sku="P001",
            shelf_id="S-A1", slot_id="S-A1-01",
            facings=3, shelf_quantity=10,
            backroom_quantity=20, version=1,
            updated_at=datetime.now(timezone.utc),
        )
        repo.upsert_inventory(item, expected_version=None)
        with pytest.raises(TwinConflict):
            repo.upsert_inventory(item, expected_version=0)

    def test_upsert_inventory_stale_version_conflict(
        self, repo: InMemoryTwinRepository
    ) -> None:
        item_v1 = InventoryDocument(
            store_id="store-001", sku="P002",
            shelf_id="S-A1", slot_id="S-A1-01",
            facings=1, shelf_quantity=5,
            backroom_quantity=10, version=5,
            updated_at=datetime.now(timezone.utc),
        )
        repo.upsert_inventory(item_v1, expected_version=None)
        item_v2 = InventoryDocument(
            store_id="store-001", sku="P002",
            shelf_id="S-A1", slot_id="S-A1-01",
            facings=2, shelf_quantity=6,
            backroom_quantity=11, version=5,
            updated_at=datetime.now(timezone.utc),
        )
        with pytest.raises(TwinConflict):
            repo.upsert_inventory(item_v2, expected_version=3)

    def test_list_inventory_returns_empty_for_unknown_store(
        self, repo: InMemoryTwinRepository
    ) -> None:
        assert repo.list_inventory("store-999") == []

    def test_reset_deletes_all_inventory(self, repo: InMemoryTwinRepository) -> None:
        item = InventoryDocument(
            store_id="store-001", sku="P001",
            shelf_id="S-A1", slot_id="S-A1-01",
            facings=3, shelf_quantity=10,
            backroom_quantity=20, version=1,
            updated_at=datetime.now(timezone.utc),
        )
        repo.upsert_inventory(item, expected_version=None)
        repo.reset("store-001")
        assert repo.list_inventory("store-001") == []

    def test_is_available_returns_true(self, repo: InMemoryTwinRepository) -> None:
        assert repo.is_available() is True
