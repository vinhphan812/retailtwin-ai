import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
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

describe("GET /revenue", () => {
  const NOW = new Date("2026-10-18T12:43:37Z");
  const served = (period: string, start: string, end = NOW.toISOString(), extra: Record<string, unknown> = {}) => ({
    store_id: "store-001",
    period,
    start,
    end,
    total_revenue: 0,
    total_transactions: 0,
    total_items_sold: 0,
    avg_transaction_value: 0,
    currency: "USD",
    buckets: [],
    ...extra,
  });

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
  });
  afterEach(() => vi.useRealTimers());

  test("asks for each window as a grain and a window apps/api accepts, never as today, 7d or 30d", async () => {
    const fetchImpl = vi.fn(async (url: RequestInfo | URL, _init?: RequestInit) => {
      const query = new URL(String(url)).searchParams;
      return jsonResponse(served(query.get("period")!, query.get("start")!, query.get("end")!));
    });
    const client = createClient("http://127.0.0.1:8000/", fetchImpl);
    await client.revenue("today");
    await client.revenue("7d");
    await client.revenue("30d");
    await client.promotions();
    expect(fetchImpl.mock.calls.map(([url]) => decodeURIComponent(String(url)))).toEqual([
      "http://127.0.0.1:8000/revenue?period=hourly&start=2026-10-18T00:00:00.000Z&end=2026-10-18T12:43:37.000Z",
      "http://127.0.0.1:8000/revenue?period=daily&start=2026-10-12T00:00:00.000Z&end=2026-10-18T12:43:37.000Z",
      "http://127.0.0.1:8000/revenue?period=daily&start=2026-09-19T00:00:00.000Z&end=2026-10-18T12:43:37.000Z",
      "http://127.0.0.1:8000/promotions",
    ]);
  });

  test("sends an X-Correlation-ID, and keeps apps/api's echo of it when it can read it", async () => {
    const fetchImpl = vi.fn(async (_url: RequestInfo | URL, _init?: RequestInit) =>
      new Response(JSON.stringify({ error: { code: "analytics_unavailable", message: "Revenue analytics are currently unavailable." } }), {
        status: 503,
        headers: { "x-correlation-id": "served-id" },
      }),
    );
    const client = createClient("http://127.0.0.1:8000", fetchImpl);
    const error = await client.revenue("today").catch((caught: unknown) => caught);
    expect(new Headers(fetchImpl.mock.calls[0][1]?.headers).get("x-correlation-id")).toMatch(/^web-/);
    expect(error).toMatchObject({ status: 503, code: "analytics_unavailable", correlationId: "served-id" });
  });

  test("a 422 keeps apps/api's validation details and the id it was sent with", async () => {
    const fetchImpl = vi.fn(async (_url: RequestInfo | URL, _init?: RequestInit) =>
      jsonResponse(
        {
          error: {
            code: "validation_error",
            message: "The request body is invalid.",
            details: [{ field: "query.period", message: "Input should be 'hourly', 'daily', 'weekly' or 'monthly'" }],
          },
        },
        422,
      ),
    );
    const client = createClient("http://127.0.0.1:8000", fetchImpl);
    const error = (await client.revenue("today").catch((caught: unknown) => caught)) as ApiError;
    const sent = new Headers(fetchImpl.mock.calls[0][1]?.headers).get("x-correlation-id");
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 422, code: "validation_error", correlationId: sent });
    expect(error.details).toEqual([{ field: "query.period", message: "Input should be 'hourly', 'daily', 'weekly' or 'monthly'" }]);
  });

  test("a payload that breaks RevenueResponse fails as invalid_response, never cast to a report", async () => {
    const client = createClient("http://127.0.0.1:8000", async () =>
      jsonResponse({ revenue: 10, transactions: 1, average_basket: 10, buckets: [] }),
    );
    await expect(client.revenue("today")).rejects.toMatchObject({ status: 200, code: "invalid_response" });
  });

  test("an answer for another grain than the one asked fails as invalid_response", async () => {
    const client = createClient("http://127.0.0.1:8000", async () => jsonResponse(served("daily", "2026-10-18T00:00:00Z")));
    await expect(client.revenue("today")).rejects.toMatchObject({ code: "invalid_response", message: expect.stringContaining("period") });
  });
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
