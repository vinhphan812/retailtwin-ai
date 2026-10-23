// @vitest-environment jsdom
// TEMPORARY probe — proves the current mapper behaviour against the three real
// payload shapes (deployed v0.8.0, current origin/main backend, FE-shaped).
import { describe, expect, it, vi } from "vitest";
import { createClient } from "@/core/api/client";

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });
}

const DEPLOYED_V080 = {
  promotions: [
    {
      promotion_id: "p-1",
      name: "Deployed loyalty promo",
      promotion_type: "loyalty_multiplier",
      status: "active",
      store_id: "store-001",
      sku: "P001",
      discount_value: 2.5,
      start_time: "2026-10-01T00:00:00Z",
      end_time: "2026-10-07T00:00:00Z",
    },
  ],
  total: 1,
  active_count: 1,
};

const CURRENT_MAIN_BE = {
  store_id: "store-001",
  revenue: 10,
  incremental_revenue: 2,
  discount_cost: 3,
  promotions: [
    {
      id: "p-2",
      name: "Current-BE BOGO",
      kind: "buy_one_get_one",
      status: "active",
      starts_at: "2026-10-01T00:00:00Z",
      ends_at: "2026-10-07T00:00:00Z",
      skus: ["P002"],
      revenue: 10,
      incremental_revenue: 2,
      discount_cost: 3,
    },
  ],
};

const FE_SHAPED = {
  promotions: [
    {
      id: "p-3",
      name: "FE-shaped BOGO",
      kind: "buy_x_get_y",
      status: "active",
      value: 1,
      starts_at: "2026-10-01T00:00:00Z",
      ends_at: "2026-10-07T00:00:00Z",
      skus: ["P003"],
      revenue: 0,
      incremental_revenue: 0,
      discount_cost: 0,
    },
  ],
};

async function fetchPromotions(body: unknown) {
  const fetchImpl = vi.fn(async () => jsonResponse(body));
  const client = createClient("http://127.0.0.1:8000", fetchImpl);
  return client.promotions();
}

describe("PROBE", () => {
  it("deployed v0.8.0 payload with status=upcoming", async () => {
    const body = JSON.parse(JSON.stringify(DEPLOYED_V080));
    body.promotions[0].status = "upcoming";
    let out = "";
    try {
      const s = await fetchPromotions(body);
      out = "OK kind=" + s.promotions[0].kind + " status=" + s.promotions[0].status;
    } catch (e) {
      out = "THREW " + (e as Error).constructor.name + ": " + (e as Error).message;
    }
    console.log("[deployed status=upcoming] ->", out);
    expect(true).toBe(true);
  });

  it("deployed v0.8.0 payload with status=cancelled", async () => {
    const body = JSON.parse(JSON.stringify(DEPLOYED_V080));
    body.promotions[0].status = "cancelled";
    let out = "";
    try {
      const s = await fetchPromotions(body);
      out = "OK kind=" + s.promotions[0].kind + " status=" + s.promotions[0].status;
    } catch (e) {
      out = "THREW " + (e as Error).constructor.name + ": " + (e as Error).message;
    }
    console.log("[deployed status=cancelled] ->", out);
    expect(true).toBe(true);
  });

  it("current origin/main backend payload (kind field, BE enum values)", async () => {
    let out = "";
    try {
      const s = await fetchPromotions(CURRENT_MAIN_BE);
      const p = s.promotions[0];
      out = `OK kind=${p.kind} status=${p.status} value=${String(p.value)} starts_at=${p.starts_at}`;
    } catch (e) {
      out = "THREW " + (e as Error).constructor.name + ": " + (e as Error).message;
    }
    console.log("[current main BE shape] ->", out);
    expect(true).toBe(true);
  });

  it("FE-shaped payload through the same mapper", async () => {
    let out = "";
    try {
      const s = await fetchPromotions(FE_SHAPED);
      const p = s.promotions[0];
      out = `OK kind=${p.kind} status=${p.status} value=${String(p.value)}`;
    } catch (e) {
      out = "THREW " + (e as Error).constructor.name + ": " + (e as Error).message;
    }
    console.log("[FE-shaped payload] ->", out);
    expect(true).toBe(true);
  });
});
