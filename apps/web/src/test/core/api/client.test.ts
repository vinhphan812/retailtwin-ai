import { describe, expect, test, vi } from "vitest";
import { ApiError, createClient } from "@/core/api/client";
import type { HealthResponse } from "@/types/api.type";
import type { ProductInventory, StoreResponse } from "@/types/twin.type";

const health: HealthResponse = {
  status: "ok",
  service: "retailtwin-api",
  environment: "test",
  store_id: "store-001",
  fixture_loaded: true,
};

const product: ProductInventory = {
  store_id: "store-001",
  sku: "P001",
  shelf_id: "A01",
  slot_id: "A01-S01",
  facings: 3,
  shelf_quantity: 8,
  backroom_quantity: 42,
  version: 1,
};

const store: StoreResponse = {
  store_id: "store-001",
  context_version: "store-001:v1",
  version: "v1",
  products: [product],
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("createClient", () => {
  test("reads health, store, and inventory", async () => {
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/health")) return jsonResponse(health);
      if (url.endsWith("/store")) return jsonResponse(store);
      if (url.endsWith("/inventory/P001")) return jsonResponse(product);
      return jsonResponse({ error: { code: "http_error", message: "missing" } }, 404);
    });
    const client = createClient("http://127.0.0.1:8000/", fetchImpl);

    await expect(client.health()).resolves.toEqual(health);
    await expect(client.store()).resolves.toEqual(store);
    await expect(client.inventory("P001")).resolves.toEqual(product);
    expect(String(fetchImpl.mock.calls[0][0])).toBe("http://127.0.0.1:8000/health");
  });

  test("encodes the SKU and surfaces the API message", async () => {
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      if (!String(input).endsWith("/inventory/NO%20SUCH")) {
        throw new Error(`unexpected ${String(input)}`);
      }
      return jsonResponse(
        { error: { code: "sku_not_found", message: "SKU 'NO SUCH' is not in store store-001." } },
        404,
      );
    });
    const client = createClient("http://127.0.0.1:8000", fetchImpl);

    await expect(client.inventory("NO SUCH")).rejects.toMatchObject({
      name: "ApiError",
      status: 404,
      code: "sku_not_found",
      message: "SKU 'NO SUCH' is not in store store-001.",
    });
    expect(String(fetchImpl.mock.calls[0][0])).toBe("http://127.0.0.1:8000/inventory/NO%20SUCH");
  });

  test("turns a network failure into a controlled error", async () => {
    const client = createClient(
      "http://127.0.0.1:8000",
      vi.fn(async () => {
        throw new TypeError("connect ECONNREFUSED");
      }),
    );

    await expect(client.health()).rejects.toEqual(new ApiError(0, "network_error", "The API is unreachable."));
  });

  test("does not crash when the error body is not JSON", async () => {
    const client = createClient(
      "http://127.0.0.1:8000",
      vi.fn(async () => new Response("nope", { status: 502 })),
    );

    await expect(client.store()).rejects.toEqual(new ApiError(502, "request_failed", "Request failed (502)."));
  });
});

test("asks the revenue route with the correct period mapping", async () => {
  const fetchImpl = vi.fn(async (_url: RequestInfo | URL) =>
    jsonResponse({ store_id: "store-001", period: "daily", start: "2026-10-02T00:00:00Z", end: "2026-10-09T00:00:00Z", total_revenue: 0, total_transactions: 0, total_items_sold: 0, avg_transaction_value: 0, currency: "USD", buckets: [] }),
  );
  const client = createClient("http://127.0.0.1:8000/", fetchImpl);

  await client.revenue("today");
  await client.revenue("7d");
  await client.revenue("30d");
  await client.promotions();

  expect(fetchImpl.mock.calls.map(([url]) => String(url))).toEqual([
    "http://127.0.0.1:8000/revenue?period=hourly",   // today → hourly
    "http://127.0.0.1:8000/revenue?period=daily",    // 7d → daily
    "http://127.0.0.1:8000/revenue?period=daily",    // 30d → daily
    "http://127.0.0.1:8000/promotions",           // promotions unchanged
  ]);
});

test("maps backend period values to UI period and shapes RevenueSummary correctly", async () => {
  const hourlyResponse = {
    store_id: "store-001", period: "hourly", start: "2026-10-09T00:00:00Z", end: "2026-10-09T12:00:00Z",
    total_revenue: 1500, total_transactions: 30, total_items_sold: 90, avg_transaction_value: 50,
    currency: "USD",
    buckets: [
      { timestamp: "2026-10-09T00:00:00Z", revenue: 100, transactions: 2, items_sold: 6 },
      { timestamp: "2026-10-09T01:00:00Z", revenue: 200, transactions: 4, items_sold: 12 },
    ],
  };
  const fetchImpl = vi.fn(async (_url: RequestInfo | URL) => jsonResponse(hourlyResponse));
  const client = createClient("http://127.0.0.1:8000/", fetchImpl);

  const summary = await client.revenue("today");

  // Period mapped back to UI value.
  expect(summary.period).toBe("today");
  // Totals derived from backend aggregates.
  expect(summary.revenue).toBe(1500);
  expect(summary.transactions).toBe(30);
  expect(summary.average_basket).toBe(50);
  // Buckets mapped from timestamp → start.
  expect(summary.buckets).toEqual([
    { start: "2026-10-09T00:00:00Z", revenue: 100 },
    { start: "2026-10-09T01:00:00Z", revenue: 200 },
  ]);
  // Fields not returned by backend default to safe zeros.
  expect(summary.margin_rate).toBe(0);
  expect(summary.lost_to_stockout).toBe(0);
  expect(summary.categories).toEqual([]);
  expect(summary.top_skus).toEqual([]);
  expect(summary.slow_skus).toEqual([]);
});

test("asks the simulation routes for the open runs and one run, encoding its id", async () => {
  const fetchImpl = vi.fn(async (_url: RequestInfo | URL) => jsonResponse({}));
  const client = createClient("http://127.0.0.1:8000/", fetchImpl);
  await client.simulations();
  await client.simulation("sim 1");
  expect(fetchImpl.mock.calls.map(([url]) => String(url))).toEqual([
    "http://127.0.0.1:8000/simulations?status=open",
    "http://127.0.0.1:8000/simulations/sim%201",
  ]);
});

test("posts a review to the run's approve or reject route with what the reviewer saw", async () => {
  const fetchImpl = vi.fn(async (_url: RequestInfo | URL, _init?: RequestInit) => jsonResponse({}));
  const client = createClient("http://127.0.0.1:8000", fetchImpl);
  const request = { base_context_version: "store-001:v1", proposal_context_version: "store-001:v1-sim" };
  await client.reviewSimulation("sim 1", "approve", request);
  await client.reviewSimulation("sim 1", "reject", request);

  expect(fetchImpl.mock.calls.map(([url]) => String(url))).toEqual([
    "http://127.0.0.1:8000/simulations/sim%201/approve",
    "http://127.0.0.1:8000/simulations/sim%201/reject",
  ]);
  const init = fetchImpl.mock.calls[0][1]!;
  expect(init.method).toBe("POST");
  expect(JSON.parse(String(init.body))).toEqual(request);
});
