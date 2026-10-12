"""Additional tests for firestore_twin helper functions and UrllibTransport.

Tests error paths, malformed data, and edge cases that improve coverage
of the helper layer and FirestoreLiveTwinRepository.
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
    _commit_update_time,
    _database_root,
    _doc_name,
    _doc_path,
    _http_error,
    _int_field,
    _opt_string_field,
    _parse_inventory_doc,
    _parse_store_doc,
    _precondition_conflict,
    _string_field,
    _timestamp,
    _bump_version,
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
            resp = transport.request("GET", "https://example.com", None, {})
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

            def read(self, n: int | None = None) -> bytes:
                return body

        with patch("urllib.request.urlopen", side_effect=FakeHTTPError()):
            resp = transport.request("GET", "https://example.com", None, {})
            assert resp.status == 404
            assert "not found" in resp.body

    def test_request_raises_twin_unavailable_on_url_error(self) -> None:
        transport = UrllibTransport()
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("Connection refused")
        ):
            with pytest.raises(TwinUnavailable, match="Connection refused"):
                transport.request("GET", "https://example.com", None, {})


class TestInMemoryTwinRepository:
    @pytest.fixture
    def repo(self) -> InMemoryTwinRepository:
        return InMemoryTwinRepository()

    def test_get_inventory_returns_none_for_unknown_sku(
        self, repo: InMemoryTwinRepository
    ) -> None:
        assert repo.get_inventory("store-001", "P999") is None

    def test_get_store_returns_none_for_unknown_store(
        self, repo: InMemoryTwinRepository
    ) -> None:
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


# ---------------------------------------------------------------------------
# Fake HTTP transport for FirestoreLiveTwinRepository testing
# ---------------------------------------------------------------------------


class FakeHttpResponse:
    def __init__(self, status: int, body: str) -> None:
        self.status = status
        self.body = body


class _FakeToken:
    """Fake CommandRunner that returns a deterministic token."""
    def run(self, cmd: list[str], **kwargs: object) -> str:
        return "fake-token-abc123"


class FakeFirestoreTransport:
    """In-process fake of the Firestore REST API for unit testing.

    Pass a list of (status, body) response tuples. Each HTTP call cycles
    through the list in order. Responses are yielded as FakeHttpResponse objects.
    """

    def __init__(self, responses: list[tuple[int, str]]) -> None:
        self._responses = responses
        self._index = 0
        self.calls: list[tuple[str, str, object | None]] = []

    def request(
        self,
        method: str,
        url: str,
        payload: bytes | None,
        headers: dict[str, str],
    ) -> FakeHttpResponse:
        self.calls.append((method, url, payload))
        resp = self._responses[self._index % len(self._responses)]
        self._index += 1
        return FakeHttpResponse(resp[0], resp[1])


def _make_live_repo(*responses: tuple[int, str]):
    """Build a FirestoreLiveTwinRepository with fake transport and token."""
    from retailtwin_api.firestore_twin import FirestoreLiveTwinRepository

    transport = FakeFirestoreTransport(list(responses))

    class Repo(FirestoreLiveTwinRepository):
        def _headers(self) -> dict[str, str]:
            return {"Authorization": "Bearer fake"}

    repo = Repo(
        TwinConfig(project="retailtwin-ai-511002", location="us-central1"),
        transport=transport,  # type: ignore[arg-type]
    )
    repo._runner = _FakeToken()  # type: ignore[assignment]
    return repo


class TestFirestoreLiveTwinGetStore:
    """Coverage for FirestoreLiveTwinRepository.get_store error paths."""

    def test_returns_none_on_404(self) -> None:
        repo = _make_live_repo((404, '{"error": {"message": "Not found"}}'))
        assert repo.get_store("store-001") is None

    def test_raises_on_500(self) -> None:
        repo = _make_live_repo((500, '{"error": {"message": "Internal error"}}'))
        with pytest.raises(TwinUnavailable, match="Internal error"):
            repo.get_store("store-001")

    def test_raises_on_non_json_500(self) -> None:
        repo = _make_live_repo((500, "Server Error"))
        with pytest.raises(TwinUnavailable, match="Server Error"):
            repo.get_store("store-001")

    def test_raises_on_malformed_document_missing_fields(self) -> None:
        repo = _make_live_repo((200, '{"name": "store/store-001", "fields": {}}'))
        with pytest.raises(TwinUnavailable, match="store_id"):
            repo.get_store("store-001")

    def test_raises_on_invalid_version_field(self) -> None:
        repo = _make_live_repo((
            200,
            '{"name": "store/store-001", '
            '"fields": {"store_id": {"stringValue": "store-001"}, '
            '"version": {"integerValue": "v1"}}}',
        ))
        with pytest.raises(TwinUnavailable, match="version"):
            repo.get_store("store-001")

    def test_token_runner_is_called(self) -> None:
        repo = _make_live_repo((404, '{}'))
        assert repo._runner is not None
        assert repo._runner.run(["gcloud"]) == "fake-token-abc123"
        repo.get_store("store-001")

    def test_headers_includes_authorization(self) -> None:
        repo = _make_live_repo((404, '{}'))
        h = repo._headers()
        assert "Authorization" in h
        assert h["Authorization"] == "Bearer fake"


class TestFirestoreLiveTwinListInventory:
    """Coverage for FirestoreLiveTwinRepository.list_inventory error paths.

    Note: list_inventory catches TwinUnavailable per-item and skips them,
    so malformed items in a list never propagate. We test the 500 error path.
    """

    def test_returns_empty_on_200_empty_documents(self) -> None:
        repo = _make_live_repo((200, '{"documents": []}'))
        assert repo.list_inventory("store-001") == []

    def test_skips_malformed_items_and_returns_remaining(self) -> None:
        # One malformed item (missing shelf_id), one valid item
        repo = _make_live_repo((
            200,
            json.dumps({
                "documents": [
                    {"name": "inventory/store-001/P001", "fields": {
                        "store_id": {"stringValue": "store-001"},
                        "sku": {"stringValue": "P001"},
                        # missing shelf_id — raises TwinUnavailable, skipped
                    }},
                    {"name": "inventory/store-001/P002", "fields": {
                        "store_id": {"stringValue": "store-001"},
                        "sku": {"stringValue": "P002"},
                        "shelf_id": {"stringValue": "A01"},
                        "slot_id": {"stringValue": "A01-S01"},
                        "facings": {"integerValue": "2"},
                        "shelf_quantity": {"integerValue": "5"},
                        "backroom_quantity": {"integerValue": "10"},
                        "version": {"integerValue": "1"},
                    }},
                ]
            }),
        ))
        items = repo.list_inventory("store-001")
        assert len(items) == 1
        assert items[0].sku == "P002"

    def test_raises_on_500(self) -> None:
        repo = _make_live_repo((500, '{"error": {"message": "boom"}}'))
        with pytest.raises(TwinUnavailable, match="boom"):
            repo.list_inventory("store-001")


class TestFirestoreLiveTwinGetInventory:
    """Coverage for FirestoreLiveTwinRepository.get_inventory error paths."""

    def test_returns_none_on_404(self) -> None:
        repo = _make_live_repo((404, '{"error": {"message": "Not found"}}'))
        assert repo.get_inventory("store-001", "P999") is None

    def test_raises_on_500(self) -> None:
        repo = _make_live_repo((500, '{"error": {"message": "fail"}}'))
        with pytest.raises(TwinUnavailable, match="fail"):
            repo.get_inventory("store-001", "P001")

    def test_raises_on_missing_sku_field(self) -> None:
        repo = _make_live_repo((
            200,
            '{"name": "inventory/store-001/P001", '
            '"fields": {"store_id": {"stringValue": "store-001"}}}',
        ))
        with pytest.raises(TwinUnavailable, match="sku"):
            repo.get_inventory("store-001", "P001")

    def test_raises_on_non_json_200(self) -> None:
        repo = _make_live_repo((200, "not json at all"))
        with pytest.raises(TwinUnavailable, match="not JSON"):
            repo.get_inventory("store-001", "P001")


class TestFirestoreLiveTwinUpsertInventory:
    """Coverage for FirestoreLiveTwinRepository.upsert_inventory error paths.

    upsert_inventory with expected_version != None first makes a POST (commit),
    then (on conflict) calls get_inventory — so provide 2 responses for conflict tests.
    """

    def test_raises_conflict_on_409(self) -> None:
        # Response 0: commit → 409 (conflict)
        # Response 1: get_inventory → 404 (current item not found)
        repo = _make_live_repo(
            (409, '{"error": {"message": "Conflict"}}'),
            (404, '{"error": {"message": "Not found"}}'),
        )
        item = InventoryDocument(
            store_id="store-001", sku="P001",
            shelf_id="S-A1", slot_id="S-A1-01",
            facings=3, shelf_quantity=10,
            backroom_quantity=20, version=1,
            updated_at=datetime.now(timezone.utc),
        )
        with pytest.raises(TwinConflict) as exc_info:
            repo.upsert_inventory(item, expected_version=1)
        assert exc_info.value.sku == "P001"

    def test_raises_conflict_on_400_failed_precondition(self) -> None:
        # Response 0: commit → 400 FAILED_PRECONDITION
        # Response 1: get_inventory → 200 with existing item
        existing_doc = json.dumps({
            "name": "inventory/store-001/P001",
            "fields": {
                "store_id": {"stringValue": "store-001"},
                "sku": {"stringValue": "P001"},
                "shelf_id": {"stringValue": "A01"},
                "slot_id": {"stringValue": "A01-S01"},
                "facings": {"integerValue": "5"},
                "shelf_quantity": {"integerValue": "20"},
                "backroom_quantity": {"integerValue": "40"},
                "version": {"integerValue": "3"},
            },
        })
        repo = _make_live_repo(
            (400, '{"error": {"status": "FAILED_PRECONDITION"}}'),
            (200, existing_doc),
        )
        item = InventoryDocument(
            store_id="store-001", sku="P001",
            shelf_id="S-A1", slot_id="S-A1-01",
            facings=3, shelf_quantity=10,
            backroom_quantity=20, version=1,
            updated_at=datetime.now(timezone.utc),
        )
        with pytest.raises(TwinConflict) as exc_info:
            repo.upsert_inventory(item, expected_version=1)
        assert exc_info.value.sku == "P001"
        assert exc_info.value.stored_version == 3

    def test_raises_unavailable_on_500(self) -> None:
        repo = _make_live_repo((500, '{"error": {"message": "boom"}}'))
        item = InventoryDocument(
            store_id="store-001", sku="P001",
            shelf_id="S-A1", slot_id="S-A1-01",
            facings=3, shelf_quantity=10,
            backroom_quantity=20, version=1,
            updated_at=datetime.now(timezone.utc),
        )
        with pytest.raises(TwinUnavailable, match="boom"):
            repo.upsert_inventory(item, expected_version=None)

    def test_unconditional_write_succeeds(self) -> None:
        repo = _make_live_repo((200, '{"writeResults": [{"updateTime": "2026-01-01T00:00:00Z"}]}'))
        item = InventoryDocument(
            store_id="store-001", sku="P001",
            shelf_id="S-A1", slot_id="S-A1-01",
            facings=3, shelf_quantity=10,
            backroom_quantity=20, version=1,
            updated_at=datetime.now(timezone.utc),
        )
        result = repo.upsert_inventory(item, expected_version=None)
        assert result.sku == "P001"
        assert result.version == 1


class TestFirestoreLiveTwinSeed:
    """Coverage for FirestoreLiveTwinRepository.seed error paths."""

    def test_raises_on_500(self) -> None:
        repo = _make_live_repo((500, '{"error": {"message": "seed fail"}}'))
        with pytest.raises(TwinUnavailable, match="seed fail"):
            repo.seed("store-001", "v1", [])


class TestFirestoreLiveTwinReset:
    """Coverage for FirestoreLiveTwinRepository.reset error paths."""

    def test_raises_on_500(self) -> None:
        repo = _make_live_repo((500, '{"error": {"message": "reset fail"}}'))
        with pytest.raises(TwinUnavailable, match="reset fail"):
            repo.reset("store-001")


class TestFirestoreLiveTwinIsAvailable:
    """Coverage for FirestoreLiveTwinRepository.is_available."""

    def test_returns_true_on_200(self) -> None:
        repo = _make_live_repo((200, '{"documents": []}'))
        assert repo.is_available() is True

    def test_returns_false_on_500(self) -> None:
        repo = _make_live_repo((500, '{"error": {"message": "unavailable"}}'))
        assert repo.is_available() is False

    def test_returns_false_when_transport_raises(self) -> None:
        from retailtwin_api.firestore_twin import FirestoreLiveTwinRepository

        class FailingTransport:
            def request(self, **kwargs: object) -> FakeHttpResponse:
                raise TwinUnavailable("connection refused")

        repo = FirestoreLiveTwinRepository(
            TwinConfig(project="retailtwin-ai-511002", location="us-central1"),
            transport=FailingTransport(),  # type: ignore[arg-type]
        )
        repo._runner = _FakeToken()  # type: ignore[assignment]
        assert repo.is_available() is False


class TestCommitUpdateTime:
    def test_commit_update_time_parses_valid(self) -> None:
        body = '{"writeResults": [{"updateTime": "2026-03-15T10:30:00Z"}]}'
        assert _commit_update_time(body) == "2026-03-15T10:30:00Z"

    def test_commit_update_time_raises_on_non_json(self) -> None:
        with pytest.raises(TwinUnavailable, match="not JSON"):
            _commit_update_time("not json")

    def test_commit_update_time_raises_on_missing_results(self) -> None:
        with pytest.raises(TwinUnavailable, match="no update time"):
            _commit_update_time('{"writeResults": []}')

    def test_commit_update_time_raises_on_missing_update_time(self) -> None:
        with pytest.raises(TwinUnavailable, match="no update time"):
            _commit_update_time('{"writeResults": [{}]}')

    def test_commit_update_time_raises_when_result_not_dict(self) -> None:
        with pytest.raises(TwinUnavailable, match="no update time"):
            _commit_update_time('{"writeResults": ["not a dict"]}')


class TestParseInventoryDoc:
    def test_parse_inventory_doc_full(self) -> None:
        from retailtwin_api.firestore_twin import _FirestoreDocument
        doc = _FirestoreDocument(
            name="inventory/store-001/P001",
            fields={
                "store_id": {"stringValue": "store-001"},
                "sku": {"stringValue": "P001"},
                "shelf_id": {"stringValue": "A01"},
                "slot_id": {"stringValue": "A01-S01"},
                "facings": {"integerValue": "3"},
                "shelf_quantity": {"integerValue": "10"},
                "backroom_quantity": {"integerValue": "20"},
                "version": {"integerValue": "1"},
                "updated_at": {"stringValue": "2026-01-01T12:00:00Z"},
            },
        )
        result = _parse_inventory_doc(doc)
        assert result.store_id == "store-001"
        assert result.sku == "P001"
        assert result.facings == 3

    def test_parse_inventory_doc_raises_on_bad_integer(self) -> None:
        from retailtwin_api.firestore_twin import _FirestoreDocument
        doc = _FirestoreDocument(
            name="inventory/store-001/P001",
            fields={
                "store_id": {"stringValue": "store-001"},
                "sku": {"stringValue": "P001"},
                "shelf_id": {"stringValue": "A01"},
                "slot_id": {"stringValue": "A01-S01"},
                "facings": {"integerValue": "not-an-int"},
                "shelf_quantity": {"integerValue": "10"},
                "backroom_quantity": {"integerValue": "20"},
                "version": {"integerValue": "1"},
                "updated_at": {"stringValue": "2026-01-01T12:00:00Z"},
            },
        )
        with pytest.raises(TwinUnavailable, match="not a valid integer"):
            _parse_inventory_doc(doc)


class TestParseStoreDoc:
    def test_parse_store_doc_full(self) -> None:
        from retailtwin_api.firestore_twin import _FirestoreDocument
        doc = _FirestoreDocument(
            name="store/store-001",
            fields={
                "store_id": {"stringValue": "store-001"},
                "version": {"stringValue": "v3"},
                "updated_at": {"stringValue": "2026-01-01T12:00:00Z"},
            },
        )
        result = _parse_store_doc(doc)
        assert result.store_id == "store-001"
        assert result.version == "v3"


class TestBumpVersion:
    def test_bump_v1(self) -> None:
        assert _bump_version("v1") == "v2"

    def test_bump_v99(self) -> None:
        assert _bump_version("v99") == "v100"

    def test_bump_unknown_format(self) -> None:
        assert _bump_version("latest") == "v2"

    def test_bump_non_numeric(self) -> None:
        assert _bump_version("beta") == "v2"


class TestTwinConflict:
    def test_conflict_message(self) -> None:
        exc = TwinConflict("P001", 3, 1)
        assert exc.sku == "P001"
        assert exc.stored_version == 3
        assert exc.incoming_version == 1
        assert "P001" in str(exc)
        assert "conflict" in str(exc).lower()
        assert "3" in str(exc)
        assert "1" in str(exc)


class TestTwinNotFound:
    def test_twin_not_found_path(self) -> None:
        from retailtwin_api.firestore_twin import TwinNotFound
        exc = TwinNotFound("/store/999")
        assert exc.path == "/store/999"
        assert "/store/999" in str(exc)


class TestInventorySeed:
    def test_seed_requires_non_negative_facings(self) -> None:
        from retailtwin_api.firestore_twin import InventorySeed
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            InventorySeed(sku="P001", shelf_id="A01", slot_id="A01-S01",
                         facings=-1, shelf_quantity=0, backroom_quantity=0)

    def test_seed_requires_non_negative_quantity(self) -> None:
        from retailtwin_api.firestore_twin import InventorySeed
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            InventorySeed(sku="P001", shelf_id="A01", slot_id="A01-S01",
                         facings=0, shelf_quantity=-1, backroom_quantity=0)
