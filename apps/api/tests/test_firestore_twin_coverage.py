"""Additional tests for FirestoreLiveTwin to improve coverage.

Tests error paths, malformed data, and edge cases in:
- firestore_twin helper functions
- UrllibTransport error handling
- FirestoreLiveTwinRepository methods
"""
from __future__ import annotations

import json
import urllib.error
from collections.abc import Mapping
from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import patch

import pytest

from retailtwin_api.firestore_twin import (
    COLLECTION_INVENTORY,
    FirestoreLiveTwinRepository,
    HttpResponse,
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# HTTP error helpers
# ---------------------------------------------------------------------------

class TestHttpError:
    def test_http_error_with_json_error_message(self) -> None:
        body = '{"error": {"message": "Document not found"}}'
        with pytest.raises(TwinUnavailable, match="Document not found"):
            _http_error("get_store", 404, body)

    def test_http_error_with_non_json_body(self) -> None:
        body = "Internal Server Error"
        with pytest.raises(TwinUnavailable, match="Internal Server Error"):
            _http_error("get_store", 500, body)

    def test_http_error_with_truncated_long_body(self) -> None:
        long_body = "x" * 500
        with pytest.raises(TwinUnavailable, match="x{200}"):
            _http_error("get_store", 500, long_body)

    def test_http_error_with_json_but_no_message(self) -> None:
        body = '{"error": {"code": 404}}'
        with pytest.raises(TwinUnavailable, match="get_store failed"):
            _http_error("get_store", 404, body)

    def test_http_error_with_json_but_error_not_dict(self) -> None:
        body = '{"error": "just a string"}'
        with pytest.raises(TwinUnavailable, match="get_store failed"):
            _http_error("get_store", 404, body)


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


# ---------------------------------------------------------------------------
# Timestamp
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Field helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# UrllibTransport
# ---------------------------------------------------------------------------

class TestUrllibTransport:
    def test_request_returns_response_on_success(self) -> None:
        transport = UrllibTransport()
        body = b'{"ok": true}'

        class FakeResponse:
            status = 200

            def read(self, n: int | None = None) -> bytes:
                return body

            def __enter__(self) -> FakeResponse:
                return self

            def __exit__(self, *a: object) -> None:
                pass

        with patch("urllib.request.urlopen", return_value=FakeResponse()) as mock_urlopen:
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


# ---------------------------------------------------------------------------
# FirestoreLiveTwinRepository
# ---------------------------------------------------------------------------

class MockTransport:
    def __init__(self, responses: list[HttpResponse]) -> None:
        self._responses = responses
        self._index = 0

    def request(
        self,
        method: str,
        url: str,
        payload: bytes | None,
        headers: Mapping[str, str],
    ) -> HttpResponse:
        resp = self._responses[self._index % len(self._responses)]
        self._index += 1
        return resp


def _inv_doc(store_id: str, sku: str) -> str:
    return json.dumps({
        "name": f"projects/test/databases/(default)/documents/inventory/{store_id}/{sku}",
        "fields": {
            "store_id": {"stringValue": store_id},
            "sku": {"stringValue": sku},
            "shelf_id": {"stringValue": "S-A1"},
            "slot_id": {"stringValue": "S-A1-01"},
            "facings": {"integerValue": "3"},
            "shelf_quantity": {"integerValue": "10"},
            "backroom_quantity": {"integerValue": "20"},
            "version": {"integerValue": "1"},
        },
    })


def _inv_doc_with_version(store_id: str, sku: str, version: str) -> str:
    d = json.loads(_inv_doc(store_id, sku))
    d["fields"]["version"] = {"integerValue": version}
    return json.dumps(d)


class TestFirestoreLiveTwinGetStore:
    def _repo(self, *responses: HttpResponse) -> FirestoreLiveTwinRepository:
        return FirestoreLiveTwinRepository(transport=MockTransport(list(responses)))

    def test_get_store_returns_none_on_404(self) -> None:
        repo = self._repo(HttpResponse(404, "{}"))
        assert repo.get_store("store-001") is None

    def test_get_store_raises_on_non_200(self) -> None:
        repo = self._repo(HttpResponse(500, "Internal Error"))
        with pytest.raises(TwinUnavailable, match="get_store failed"):
            repo.get_store("store-001")

    def test_get_store_raises_on_non_json(self) -> None:
        repo = self._repo(HttpResponse(200, "not json"))
        with pytest.raises(TwinUnavailable, match="not JSON"):
            repo.get_store("store-001")

    def test_get_store_raises_on_non_dict_response(self) -> None:
        repo = self._repo(HttpResponse(200, '["array"]'))
        with pytest.raises(TwinUnavailable, match="malformed"):
            repo.get_store("store-001")

    def test_get_store_raises_on_missing_fields(self) -> None:
        repo = self._repo(HttpResponse(200, '{"Name": "stores/store-001"}'))
        with pytest.raises(TwinUnavailable, match="no fields"):
            repo.get_store("store-001")


class TestFirestoreLiveTwinListInventory:
    def _repo(self, *responses: HttpResponse) -> FirestoreLiveTwinRepository:
        return FirestoreLiveTwinRepository(transport=MockTransport(list(responses)))

    def test_list_inventory_returns_empty_on_404(self) -> None:
        repo = self._repo(HttpResponse(404, "{}"))
        assert repo.list_inventory("store-001") == []

    def test_list_inventory_raises_on_non_200(self) -> None:
        repo = self._repo(HttpResponse(500, "Error"))
        with pytest.raises(TwinUnavailable, match="list_inventory failed"):
            repo.list_inventory("store-001")

    def test_list_inventory_raises_on_non_json(self) -> None:
        repo = self._repo(HttpResponse(200, "not json"))
        with pytest.raises(TwinUnavailable, match="not JSON"):
            repo.list_inventory("store-001")

    def test_list_inventory_raises_on_non_dict_response(self) -> None:
        repo = self._repo(HttpResponse(200, '["array"]'))
        with pytest.raises(TwinUnavailable, match="malformed"):
            repo.list_inventory("store-001")

    def test_list_inventory_skips_malformed_documents(self) -> None:
        body = json.dumps({
            "documents": [
                json.loads(_inv_doc("store-001", "P001")),
                "not a document",
                {"name": "inv/store-001/P002", "fields": {}},
            ]
        })
        repo = self._repo(HttpResponse(200, body))
        result = repo.list_inventory("store-001")
        assert len(result) == 1
        assert result[0].sku == "P001"


class TestFirestoreLiveTwinGetInventory:
    def _repo(self, *responses: HttpResponse) -> FirestoreLiveTwinRepository:
        return FirestoreLiveTwinRepository(transport=MockTransport(list(responses)))

    def test_get_inventory_returns_none_on_404(self) -> None:
        repo = self._repo(HttpResponse(404, "{}"))
        assert repo.get_inventory("store-001", "P017") is None

    def test_get_inventory_raises_on_non_200(self) -> None:
        repo = self._repo(HttpResponse(500, "Error"))
        with pytest.raises(TwinUnavailable, match="get_inventory failed"):
            repo.get_inventory("store-001", "P017")

    def test_get_inventory_raises_on_non_json(self) -> None:
        repo = self._repo(HttpResponse(200, "not json"))
        with pytest.raises(TwinUnavailable, match="not JSON"):
            repo.get_inventory("store-001", "P017")

    def test_get_inventory_raises_on_non_dict_response(self) -> None:
        repo = self._repo(HttpResponse(200, '["array"]'))
        with pytest.raises(TwinUnavailable, match="malformed"):
            repo.get_inventory("store-001", "P017")

    def test_get_inventory_raises_on_missing_fields(self) -> None:
        repo = self._repo(HttpResponse(200, '{"Name": "inv/store-001/P017"}'))
        with pytest.raises(TwinUnavailable, match="no fields"):
            repo.get_inventory("store-001", "P017")


class TestFirestoreLiveTwinUpsertInventory:
    def _repo(self, *responses: HttpResponse) -> FirestoreLiveTwinRepository:
        return FirestoreLiveTwinRepository(transport=MockTransport(list(responses)))

    def test_upsert_inventory_returns_item_on_200(self) -> None:
        repo = self._repo(HttpResponse(200, '{"commitTime": "2026-01-01T00:00:00Z"}'))
        item = InventoryDocument(
            store_id="store-001", sku="P017",
            shelf_id="S-A1", slot_id="S-A1-01",
            facings=3, shelf_quantity=10,
            backroom_quantity=20, version=1,
            updated_at=datetime.now(timezone.utc),
        )
        result = repo.upsert_inventory(item, expected_version=None)
        assert result.sku == "P017"

    def test_upsert_inventory_raises_conflict_on_409(self) -> None:
        repo = self._repo(
            HttpResponse(409, '{"error": {"status": "ALREADY_EXISTS"}}'),
            HttpResponse(200, _inv_doc_with_version("store-001", "P017", "2")),
        )
        item = InventoryDocument(
            store_id="store-001", sku="P017",
            shelf_id="S-A1", slot_id="S-A1-01",
            facings=3, shelf_quantity=10,
            backroom_quantity=20, version=1,
            updated_at=datetime.now(timezone.utc),
        )
        with pytest.raises(TwinConflict) as exc_info:
            repo.upsert_inventory(item, expected_version=1)
        assert exc_info.value.sku == "P017"

    def test_upsert_inventory_raises_on_non_200(self) -> None:
        repo = self._repo(HttpResponse(500, "Error"))
        item = InventoryDocument(
            store_id="store-001", sku="P017",
            shelf_id="S-A1", slot_id="S-A1-01",
            facings=3, shelf_quantity=10,
            backroom_quantity=20, version=1,
            updated_at=datetime.now(timezone.utc),
        )
        with pytest.raises(TwinUnavailable, match="upsert_inventory failed"):
            repo.upsert_inventory(item, expected_version=None)


class TestFirestoreLiveTwinSeed:
    def _repo(self, *responses: HttpResponse) -> FirestoreLiveTwinRepository:
        return FirestoreLiveTwinRepository(transport=MockTransport(list(responses)))

    def test_seed_raises_on_non_200(self) -> None:
        repo = self._repo(HttpResponse(500, "Error"))
        with pytest.raises(TwinUnavailable, match="seed failed"):
            repo.seed("store-001", "v1", [])


class TestFirestoreLiveTwinReset:
    def _repo(self, *responses: HttpResponse) -> FirestoreLiveTwinRepository:
        return FirestoreLiveTwinRepository(transport=MockTransport(list(responses)))

    def test_reset_does_nothing_when_no_items(self) -> None:
        repo = self._repo(HttpResponse(200, '{"documents": []}'))
        repo.reset("store-001")  # should not raise

    def test_reset_deletes_items(self) -> None:
        body = json.dumps({
            "documents": [json.loads(_inv_doc("store-001", "P001"))],
        })
        repo = self._repo(
            HttpResponse(200, body),
            HttpResponse(200, '{"commitTime": "2026-01-01T00:00:00Z"}'),
        )
        repo.reset("store-001")  # should not raise


class TestFirestoreLiveTwinIsAvailable:
    def _repo(self, *responses: HttpResponse) -> FirestoreLiveTwinRepository:
        return FirestoreLiveTwinRepository(transport=MockTransport(list(responses)))

    def test_is_available_returns_true_on_200(self) -> None:
        repo = self._repo(HttpResponse(200, "{}"))
        assert repo.is_available() is True

    def test_is_available_returns_false_on_error(self) -> None:
        repo = self._repo(HttpResponse(500, "Error"))
        assert repo.is_available() is False
