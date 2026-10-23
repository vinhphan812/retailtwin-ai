import { describe, expect, test, vi } from "vitest";
import { createClient } from "@/core/api/client";
import { PROMOTION_KIND } from "@/enums/commerce.enum";
import { discountOf } from "@/components/promotions/PromotionCard";
import { ContractError } from "@/core/commerce/revenueContract";
import i18n from "@/i18n";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("promotions type mapping and semantics", () => {
  test("correctly maps loyalty_multiplier, buy_one_get_one, buy_x_get_y, unknown kinds, and missing values", async () => {
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
          promotion_id: "p-2a",
          name: "BOGO promo 1",
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
          promotion_id: "p-2b",
          name: "BOGO promo 2",
          promotion_type: "buy_x_get_y",
          status: "active",
          store_id: "store-001",
          sku: "P002b",
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
    expect(summary.promotions).toHaveLength(5);

    expect(summary.promotions[0].kind).toBe(PROMOTION_KIND.LoyaltyMultiplier);
    expect(summary.promotions[0].value).toBe(2.5);
    expect(discountOf(summary.promotions[0])).toBe("2.5x");

    // BOGO variants map to BuyXGetY and render translation correctly via buy_x_get_y key
    expect(summary.promotions[1].kind).toBe(PROMOTION_KIND.BuyXGetY);
    expect(i18n.t(`promotions.kind.${summary.promotions[1].kind}`, { value: discountOf(summary.promotions[1]) })).toBe("1 free");

    expect(summary.promotions[2].kind).toBe(PROMOTION_KIND.BuyXGetY);
    expect(i18n.t(`promotions.kind.${summary.promotions[2].kind}`, { value: discountOf(summary.promotions[2]) })).toBe("1 free");

    expect(summary.promotions[3].kind).toBe(PROMOTION_KIND.Unknown);
    expect(summary.promotions[3].discount_cost).toBeNull();

    expect(summary.promotions[4].value).toBeNull();
    expect(discountOf(summary.promotions[4])).toBeTruthy();
  });

  test("rejects malformed or missing required fields with ContractError", async () => {
    const invalidPromotions = {
      store_id: "store-001",
      revenue: 5000,
      incremental_revenue: 1000,
      discount_cost: 200,
      promotions: [
        {
          // missing id
          name: "Invalid promo",
          promotion_type: "discount_percent",
          status: "active",
          start_time: "2026-10-01T00:00:00Z",
          end_time: "2026-10-07T00:00:00Z",
        },
      ],
    };

    const fetchImpl = vi.fn(async () => jsonResponse(invalidPromotions));
    const client = createClient("http://127.0.0.1:8000", fetchImpl);

    await expect(client.promotions()).rejects.toThrow(ContractError);
  });
});
