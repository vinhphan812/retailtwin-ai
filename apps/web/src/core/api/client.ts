import i18n from "@/i18n";
import { isDemoMode } from "@/core/twin/demoMode";
import type { AgentEventsResponse, FlagshipStatusResponse, HealthResponse, RetailTwinClient } from "@/types/api.type";
import type { ProductInventory, StoreResponse } from "@/types/twin.type";
import type { PromotionsSummary } from "@/types/promotion.type";
import type { RevenueSummary } from "@/types/revenue.type";
import type { CandidatesResponse, ReviewResult, Simulation, SimulationsResponse } from "@/types/simulation.type";
import type { AnomaliesResponse } from "@/types/anomaly.type";
import type { CheckoutResponse } from "@/types/checkout.type";
import { REVENUE_PERIOD, BUCKET_SIZE, type RevenuePeriod } from "@/enums/commerce.enum";

/** Maps frontend period keys to backend period values. */
function toBackendPeriod(period: RevenuePeriod): string {
  switch (period) {
    case REVENUE_PERIOD.Today:
      return "hourly";
    case REVENUE_PERIOD.Week:
    case REVENUE_PERIOD.Month:
      return "daily";
  }
}

/** Backend RevenueResponse fields mapped to frontend RevenueSummary. */
interface BackendRevenueResponse {
  store_id: string;
  period: "hourly" | "daily" | "weekly" | "monthly";
  start: string;
  end: string;
  total_revenue: number;
  total_transactions: number;
  total_items_sold: number;
  avg_transaction_value: number;
  currency: "USD";
  buckets: { timestamp: string; revenue: number; transactions: number; items_sold: number }[];
}

/** Transform backend RevenueResponse to frontend RevenueSummary. */
function fromBackendRevenue(response: BackendRevenueResponse, period: RevenuePeriod): RevenueSummary {
  return {
    store_id: response.store_id,
    period,
    revenue: response.total_revenue,
    transactions: response.total_transactions,
    average_basket: response.avg_transaction_value,
    margin_rate: 0, // Backend doesn't provide this
    lost_to_stockout: 0, // Backend doesn't provide this
    previous: {
      revenue: 0,
      transactions: 0,
      average_basket: 0,
      margin_rate: 0,
    },
    bucket_size: period === REVENUE_PERIOD.Today ? BUCKET_SIZE.Hour : BUCKET_SIZE.Day,
    buckets: response.buckets.map((b) => ({
      start: b.timestamp,
      revenue: b.revenue,
    })),
    categories: [], // Backend doesn't provide this
    top_skus: [], // Backend doesn't provide this
    slow_skus: [], // Backend doesn't provide this
  };
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

type ErrorEnvelope = {
  error?: {
    code?: unknown;
    message?: unknown;
  };
};

export function createClient(baseUrl: string, fetchImpl?: typeof fetch): RetailTwinClient {
  const base = baseUrl.replace(/\/$/, "");

  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    // The demo is synthetic: whatever control a click reaches, it never writes to apps/api.
    if (init?.method && init.method !== "GET" && isDemoMode()) {
      throw new ApiError(0, "demo_read_only", i18n.t("errors.demoReadOnly"));
    }
    const doFetch = fetchImpl ?? fetch;
    let response: Response;
    try {
      response = await doFetch(`${base}${path}`, init);
    } catch {
      throw new ApiError(0, "network_error", i18n.t("errors.unreachable"));
    }
    if (!response.ok) {
      throw await toApiError(response);
    }
    return (await response.json()) as T;
  }

  return {
    health: () => request<HealthResponse>("/health"),
    store: () => request<StoreResponse>("/store"),
    inventory: (sku: string) => request<ProductInventory>(`/inventory/${encodeURIComponent(sku)}`),
    revenue: (period) =>
      request<BackendRevenueResponse>(`/revenue?period=${encodeURIComponent(toBackendPeriod(period))}`).then(
        (response) => fromBackendRevenue(response, period),
      ),
    promotions: () => request<PromotionsSummary>("/promotions"),
    simulations: () => request<SimulationsResponse>("/simulations?status=open"),
    simulation: (simulationId: string) => request<Simulation>(`/simulations/${encodeURIComponent(simulationId)}`),
    candidates: (simulationId: string) => request<CandidatesResponse>(`/simulations/${encodeURIComponent(simulationId)}/candidates`),
    reviewSimulation: (simulationId, decision, body) =>
      request<ReviewResult>(`/simulations/${encodeURIComponent(simulationId)}/${decision}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
anomalies: () => request<AnomaliesResponse>("/anomalies"),
    checkout: (checkoutId: string) => request<CheckoutResponse>(`/checkouts/${encodeURIComponent(checkoutId)}`),
    flagshipStatus: () => request<FlagshipStatusResponse>("/flagship/status"),
    flagshipReset: () => request<{ run_id: string }>("/flagship/reset", { method: "POST" }),
    flagshipStart: (correlationId: string) =>
      request<{ run_id: string; correlation_id: string; phase: string }>("/flagship/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ correlation_id: correlationId }),
      }),
    agentEvents: (since?: string | null) =>
      request<AgentEventsResponse>(`/agent/events${since ? `?since=${encodeURIComponent(since)}` : ""}`),
  };
}

async function toApiError(response: Response): Promise<ApiError> {
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  const envelope = payload as ErrorEnvelope | null;
  const code = typeof envelope?.error?.code === "string" ? envelope.error.code : "request_failed";
  const message =
    typeof envelope?.error?.message === "string"
      ? envelope.error.message
      : i18n.t("errors.requestFailed", { status: response.status });
  return new ApiError(response.status, code, message);
}

const configuredBase = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export const defaultClient = createClient(configuredBase);
