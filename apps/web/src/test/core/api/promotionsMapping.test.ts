import { describe, expect, test, vi } from "vitest";
import { createClient } from "@/core/api/client";
import { PROMOTION_KIND } from "@/enums/commerce.enum";
import { discountOf } from "@/components/promotions/PromotionCard";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("promotions type mapping and semantics", () => {
  test("correctly maps loyalty_multiplier, buy_one_get_one, unknown kinds, and missing values", async () => {
    const rawPromotions = {
      store_id: "store-001",
      revenue: 5000,
      incremental_revenue: 1000,
      discount_cost: 200,
      promotions: [
        {
          promotion_id: "p-1",
          name: "Loyalty promo",
          promotion_type: "loyalty_multiplier",
          status: "active",
          store_id: "store-001",
          sku: "P001",
          discount_value: 2.5,
          discount_cost: 50,
          start_time: "2026-10-01T00:00:00Z",
          end_time: "2026-10-07T00:00:00Z",
        },
        {
          promotion_id: "p-2",
          name: "BOGO promo",
          promotion_type: "buy_one_get_one",
          status: "active",
          store_id: "store-001",
          sku: "P002",
          discount_value: 1,
          discount_cost: 30,
          start_time: "2026-10-01T00:00:00Z",
          end_time: "2026-10-07T00:00:00Z",
        },
        {
          promotion_id: "p-3",
          name: "Unknown promo",
          promotion_type: "future_mystery_promo",
          status: "active",
          store_id: "store-001",
          sku: "P003",
          discount_value: 10,
          discount_cost: null,
          start_time: "2026-10-01T00:00:00Z",
          end_time: "2026-10-07T00:00:00Z",
        },
        {
          promotion_id: "p-4",
          name: "Missing value promo",
          promotion_type: "discount_percent",
          status: "active",
          store_id: "store-001",
          sku: "P004",
          discount_value: null,
          discount_cost: null,
          start_time: "2026-10-01T00:00:00Z",
          end_time: "2026-10-07T00:00:00Z",
        },
      ],
    };

    const fetchImpl = vi.fn(async () => jsonResponse(rawPromotions));
    const client = createClient("http://127.0.0.1:8000", fetchImpl);

    const summary = await client.promotions();
    expect(summary.promotions).toHaveLength(4);

    // 1. loyalty_multiplier maps to LoyaltyMultiplier, value 2.5, not PercentOff
    expect(summary.promotions[0].kind).toBe(PROMOTION_KIND.LoyaltyMultiplier);
    expect(summary.promotions[0].value).toBe(2.5);
    expect(discountOf(summary.promotions[0])).toBe("2.5x");

    // 2. buy_one_get_one maps to BuyXGetY
    expect(summary.promotions[1].kind).toBe(PROMOTION_KIND.BuyXGetY);
    expect(summary.promotions[1].value).toBe(1);

    // 3. unknown kind maps to Unknown, never PercentOff
    expect(summary.promotions[2].kind).toBe(PROMOTION_KIND.Unknown);
    expect(summary.promotions[2].discount_cost).toBeNull();

    // 4. missing discount_value maps to null, discountOf renders terms unavailable
    expect(summary.promotions[3].value).toBeNull();
    expect(discountOf(summary.promotions[3])).toBeTruthy();
  });
});
