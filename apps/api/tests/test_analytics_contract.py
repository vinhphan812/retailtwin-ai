"""Focused contract tests for Issue #334/#95: Revenue 422 surfacing and analytics wiring.

Tests the contract between the API and the frontend client:
- Revenue period adapter: FE period → BE period mapping (today→hourly, 7d→7d, 30d→30d).
- 422 responses include path, method, and actionable details with error types.
- 503 responses include path and method.
- Promotions schema: BE returns id, kind, starts_at, ends_at, skus, and financial aggregates.
- Absent arrays return [] (not None) — critical for FE rendering.
"""

from datetime import datetime, timezone
from fastapi.testclient import TestClient


class TestRevenueContract:
    """Contract tests for GET /revenue — verifies period mapping and error surfacing."""

    def test_7d_period_returns_200(self, client: TestClient):
        """Extended period 7d should be accepted by the backend."""
        response = client.get("/revenue", params={"period": "7d"})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.json()}"

    def test_30d_period_returns_200(self, client: TestClient):
        """Extended period 30d should be accepted by the backend."""
        response = client.get("/revenue", params={"period": "30d"})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.json()}"

    def test_today_as_period_returns_422(self, client: TestClient):
        """Frontend sends 'today' but BE only accepts 'hourly'; this surfaces a 422 with hints."""
        response = client.get("/revenue", params={"period": "today"})
        assert response.status_code == 422
        data = response.json()
        # The FE period adapter should prevent this from reaching the BE,
        # but if it does, the error must be actionable.
        assert data["error"]["code"] == "validation_error"
        assert "period" in str(data["error"]["details"])
        assert "path" in data["error"]
        assert "method" in data["error"]
        assert data["error"]["path"] == "/revenue"
        assert data["error"]["method"] == "GET"

    def test_422_includes_path_and_method(self, client: TestClient):
        """All 422 responses must include the endpoint path and HTTP method."""
        response = client.get("/revenue", params={"period": "hourly", "start": "not-a-date"})
        assert response.status_code == 422
        data = response.json()
        assert data["error"]["path"] == "/revenue"
        assert data["error"]["method"] == "GET"

    def test_422_includes_actionable_hints(self, client: TestClient):
        """422 detail items must include the Pydantic error type for FE debugging."""
        response = client.get("/revenue", params={"period": "invalid"})
        assert response.status_code == 422
        data = response.json()
        details = data["error"]["details"]
        assert len(details) > 0
        # Each detail must have a "type" field (Pydantic error type).
        for detail in details:
            assert "type" in detail, f"Detail missing 'type': {detail}"
            assert "field" in detail, f"Detail missing 'field': {detail}"
            assert "message" in detail, f"Detail missing 'message': {detail}"

    def test_422_datetime_error_has_iso8601_hint(self, client: TestClient):
        """Malformed datetime in 422 must include an ISO-8601 format hint."""
        response = client.get("/revenue", params={"start": "bad-date"})
        assert response.status_code == 422
        data = response.json()
        details = data["error"]["details"]
        hint = next((d for d in details if "datetime" in d.get("type", "").lower() or "time" in d.get("type", "").lower()), None)
        # Should have a contextual hint about ISO-8601 format.
        found_hint = any("ISO-8601" in str(d.get("message", "")) for d in details)
        assert found_hint, f"Expected ISO-8601 hint in details: {details}"

    def test_422_message_includes_route(self, client: TestClient):
        """422 error message must identify the route for debugging."""
        response = client.get("/revenue", params={"period": "nonsense"})
        assert response.status_code == 422
        data = response.json()
        assert "/revenue" in data["error"]["message"], f"Message should include /revenue: {data['error']['message']}"
        assert "GET" in data["error"]["message"], f"Message should include GET: {data['error']['message']}"

    def test_503_includes_path_and_method(self, client: TestClient):
        """503 responses from the API must include path and method for observability."""
        # Force analytics error by replacing the revenue repo with one that raises AnalyticsError.
        from retailtwin_api.analytics_repository import AnalyticsError
        from retailtwin_api.routes import RevenueRepository

        class FailingRevenueRepo:
            available = False

            def get_revenue(self, store_id, period, start, end):
                raise AnalyticsError("BigQuery timeout")

        client.app.state.revenue = FailingRevenueRepo()
        response = client.get("/revenue", params={"period": "daily"})
        assert response.status_code == 503
        data = response.json()
        assert "code" in data["error"]
        assert data["error"]["code"] in ("analytics_unavailable", "http_error")
        assert "path" in data["error"], f"503 response missing path: {data}"
        assert "method" in data["error"], f"503 response missing method: {data}"


class TestPromotionsContract:
    """Contract tests for GET /promotions — verifies BE→FE schema alignment."""

    def test_response_has_store_id(self, client: TestClient):
        """PromotionsSummary must include store_id for the FE store binding."""
        response = client.get("/promotions")
        assert response.status_code == 200
        data = response.json()
        assert "store_id" in data, f"Missing store_id in response: {data}"

    def test_empty_response_has_promotions_array(self, client: TestClient):
        """An empty promotions response must return promotions=[] (not null)."""
        response = client.get("/promotions")
        assert response.status_code == 200
        data = response.json()
        assert data.get("promotions") == [], f"Expected empty list, got: {data.get('promotions')}"

    def test_empty_response_has_financial_aggregates(self, client: TestClient):
        """Empty promotions must have revenue=0.0, not missing fields."""
        response = client.get("/promotions")
        assert response.status_code == 200
        data = response.json()
        assert "revenue" in data, "Missing revenue aggregate"
        assert "incremental_revenue" in data, "Missing incremental_revenue aggregate"
        assert "discount_cost" in data, "Missing discount_cost aggregate"
        assert data["revenue"] == 0.0, f"Expected revenue=0.0, got: {data['revenue']}"
        assert data["incremental_revenue"] == 0.0
        assert data["discount_cost"] == 0.0

    def test_response_uses_new_schema_field_names(
        self, client: TestClient, promotion_repo
    ):
        """BE must return new field names: id, kind, starts_at, ends_at, skus."""
        now = datetime.now(timezone.utc)
        from retailtwin_api.schemas import Promotion, PromotionType, PromotionStatus

        promotion_repo.seed([
            Promotion(
                id="p-test-001",
                name="Test Promo",
                kind=PromotionType.DISCOUNT_PERCENT,
                status=PromotionStatus.ACTIVE,
                starts_at=now.isoformat(),
                ends_at=(now).isoformat(),
                skus=["SKU001", "SKU002"],
                revenue=1000.0,
                incremental_revenue=250.0,
                discount_cost=150.0,
            ),
        ])
        response = client.get("/promotions")
        assert response.status_code == 200
        data = response.json()
        promotions = data.get("promotions", [])
        assert len(promotions) == 1
        p = promotions[0]
        # New field names (not promotion_id, start_time, sku).
        assert "id" in p, f"Missing 'id': {p}"
        assert "kind" in p, f"Missing 'kind': {p}"
        assert "starts_at" in p, f"Missing 'starts_at': {p}"
        assert "ends_at" in p, f"Missing 'ends_at': {p}"
        assert "skus" in p, f"Missing 'skus': {p}"
        # Old field names must NOT be present.
        assert "promotion_id" not in p, f"Old field 'promotion_id' should not be in response: {p}"
        assert "start_time" not in p, f"Old field 'start_time' should not be in response: {p}"
        assert "sku" not in p, f"Old field 'sku' should not be in response: {p}"

    def test_financial_aggregates_are_from_summary(
        self, client: TestClient, promotion_repo
    ):
        """The PromotionsSummary aggregates come from the summary, not re-summed from items."""
        now = datetime.now(timezone.utc)
        from retailtwin_api.schemas import Promotion, PromotionType, PromotionStatus

        promotion_repo.seed([
            Promotion(
                id=f"p-{i:03d}",
                name=f"Promo {i}",
                kind=PromotionType.DISCOUNT_PERCENT,
                status=PromotionStatus.ACTIVE,
                starts_at=now.isoformat(),
                ends_at=(now).isoformat(),
                skus=[f"SKU{i:03d}"],
                revenue=100.0,
                incremental_revenue=20.0,
                discount_cost=15.0,
            )
            for i in range(3)
        ])
        response = client.get("/promotions")
        assert response.status_code == 200
        data = response.json()
        # Summary aggregates
        assert data["revenue"] == 300.0, f"Expected revenue=300.0, got: {data['revenue']}"
        assert data["incremental_revenue"] == 60.0
        assert data["discount_cost"] == 45.0

    def test_kind_is_promotiontype_value(self, client: TestClient, promotion_repo):
        """BE 'kind' field contains PromotionType enum values (e.g. 'discount_percent')."""
        now = datetime.now(timezone.utc)
        from retailtwin_api.schemas import Promotion, PromotionType, PromotionStatus

        promotion_repo.seed([
            Promotion(
                id="p-kind-test",
                name="Discount Test",
                kind=PromotionType.DISCOUNT_PERCENT,
                status=PromotionStatus.ACTIVE,
                starts_at=now.isoformat(),
                ends_at=(now).isoformat(),
                skus=["SKU001"],
                revenue=100.0,
                incremental_revenue=20.0,
                discount_cost=15.0,
            ),
        ])
        response = client.get("/promotions")
        assert response.status_code == 200
        data = response.json()
        p = data["promotions"][0]
        # BE kind is a PromotionType value; FE must translate via PROMOTION_TYPE_TO_KIND.
        assert p["kind"] in ("discount_percent", "discount_absolute", "buy_one_get_one", "bundle", "loyalty_multiplier"), \
            f"Unexpected kind value: {p['kind']}"

    def test_skus_is_list_not_string(self, client: TestClient, promotion_repo):
        """BE 'skus' field must be a list[str], not a comma-joined string."""
        now = datetime.now(timezone.utc)
        from retailtwin_api.schemas import Promotion, PromotionType, PromotionStatus

        promotion_repo.seed([
            Promotion(
                id="p-skus-test",
                name="SKU Test",
                kind=PromotionType.DISCOUNT_PERCENT,
                status=PromotionStatus.ACTIVE,
                starts_at=now.isoformat(),
                ends_at=(now).isoformat(),
                skus=["SKU001", "SKU002", "SKU003"],
                revenue=100.0,
                incremental_revenue=20.0,
                discount_cost=15.0,
            ),
        ])
        response = client.get("/promotions")
        assert response.status_code == 200
        data = response.json()
        skus = data["promotions"][0]["skus"]
        assert isinstance(skus, list), f"skus must be a list, got: {type(skus)}"
        assert skus == ["SKU001", "SKU002", "SKU003"]
