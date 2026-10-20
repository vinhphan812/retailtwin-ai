import i18n from "@/i18n";
import { isDemoMode } from "@/core/twin/demoMode";
import type { AgentEventsResponse, FlagshipStatusResponse, HealthResponse, RetailTwinClient } from "@/types/api.type";
import { PROMOTION_KIND, REVENUE_PERIOD } from "@/enums/commerce.enum";
import type { ProductInventory, StoreResponse } from "@/types/twin.type";
import type { Promotion, PromotionsSummary } from "@/types/promotion.type";
import type { RevenueSummary } from "@/types/revenue.type";
import type { CandidatesResponse, ReviewResult, Simulation, SimulationsResponse } from "@/types/simulation.type";
import type { AnomaliesResponse } from "@/types/anomaly.type";
import type { CheckoutResponse } from "@/types/checkout.type";
import type { RevenueResponse } from "@/types/revenue.type";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly correlationId: string | null;
  readonly details: ErrorDetail[];

  constructor(status: number, code: string, message: string, correlationId: string | null = null, details: ErrorDetail[] = []) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.correlationId = correlationId;
    this.details = details;
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

  /** Maps UI period to backend period. */
  const UI_TO_BACKEND_PERIOD: Record<string, string> = {
    [REVENUE_PERIOD.Today]: "hourly",
    [REVENUE_PERIOD.Week]: "7d",
    [REVENUE_PERIOD.Month]: "30d",
  };

  /**
   * Backend `PromotionType` → FE `PromotionKind` mapping.
   * The BE schema uses `PromotionType` enum values (e.g. "discount_percent");
   * the FE `Promotion` type uses `PromotionKind` (e.g. "percent_off").
   * See: BE `schemas.py PromotionType`, FE `types/promotion.type.ts Promotion.kind`.
   */
  const PROMOTION_TYPE_TO_KIND: Record<string, (typeof PROMOTION_KIND)[keyof typeof PROMOTION_KIND]> = {
    discount_percent: PROMOTION_KIND.PercentOff,
    discount_absolute: PROMOTION_KIND.AmountOff,
    buy_one_get_one: PROMOTION_KIND.BuyXGetY,
    bundle: PROMOTION_KIND.Bundle,
    loyalty_multiplier: PROMOTION_KIND.PercentOff, // closest approximation
  };

  /**
   * Transform a BE `Promotion` (from `PromotionsResponse.promotions`) to the FE `Promotion` type.
   * Handles field name differences (`promotion_type` → `kind`) and type enum translation.
   */
  function toPromotion(raw: {
    promotion_id: string;
    name: string;
    promotion_type: string;
    status: string;
    store_id: string;
    sku: string | null;
    category: string | null;
    discount_value: number | null;
    conditions: string | null;
    start_time: string;
    end_time: string;
    redemption_count: number;
    metadata?: Record<string, string>;
  }): Promotion {
    return {
      id: raw.promotion_id,
      name: raw.name,
      kind: PROMOTION_TYPE_TO_KIND[raw.promotion_type] ?? PROMOTION_KIND.PercentOff,
      status: raw.status as Promotion["status"],
      value: raw.discount_value ?? 0,
      starts_at: raw.start_time,
      ends_at: raw.end_time,
      skus: raw.sku ? [raw.sku] : [],
      revenue: 0,
      incremental_revenue: 0,
      discount_cost: 0,
    };
  }

  /** Transform the BE `RevenueResponse` to the FE `RevenueSummary`. */
  function toRevenueSummary(response: RevenueResponse, period: string): RevenueSummary {
    return {
      store_id: response.store_id,
      period: period as RevenueSummary["period"],
      start: response.start,
      end: response.end,
      currency: response.currency,
      revenue: response.total_revenue,
      transactions: response.total_transactions,
      average_basket: response.avg_transaction_value,
      items_sold: response.total_items_sold,
      margin_rate: null,
      lost_to_stockout: null,
      previous: null,
      bucket_size: period === REVENUE_PERIOD.Today ? "hour" : "day",
      buckets: (response.buckets ?? []).map((b) => ({ start: b.timestamp ?? b.start ?? "", revenue: b.revenue })),
      categories: null,
      top_skus: null,
      slow_skus: null,
    };
  }

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
    revenue: (period) => {
      const backendPeriod = UI_TO_BACKEND_PERIOD[period] ?? period;
      return request<RevenueResponse>(`/revenue?period=${encodeURIComponent(backendPeriod)}`).then(
        (response) => toRevenueSummary(response, backendPeriod),
      );
    },
    promotions: () =>
      request<PromotionsSummary>("/promotions").then((response) => {
        const promotions: Promotion[] = (response.promotions as Promotion[]).map(
          (p) =>
            "kind" in p
              ? p // already transformed (demo client path)
              : toPromotion(p as Parameters<typeof toPromotion>[0]),
        );
        return {
          store_id: response.store_id,
          revenue: promotions.reduce((sum, p) => sum + (p.revenue ?? 0), 0),
          incremental_revenue: promotions.reduce((sum, p) => sum + (p.incremental_revenue ?? 0), 0),
          discount_cost: promotions.reduce((sum, p) => sum + (p.discount_cost ?? 0), 0),
          promotions,
        };
      }),
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
    checkouts: (checkoutId: string) => request<CheckoutResponse>(`/checkouts/${encodeURIComponent(checkoutId)}`),
    stockoutRisk: () => request<unknown>("/stockout-risk"),
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

export async function toApiError(response: Response): Promise<ApiError> {
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

export const configuredBase = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

/** Code for an invalid API response. */
export const INVALID_RESPONSE = "invalid_response";

export type ErrorDetail = {
  field: string;
  message: string;
};

export async function toApiErrorExported(response: Response): Promise<ApiError> {
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
      : `HTTP ${response.status}`;
  return new ApiError(
    response.status,
    code,
    message,
    null,
    envelope?.error && "details" in envelope.error ? (envelope.error.details as ErrorDetail[]) ?? [] : [],
  );
}

export const defaultClient = createClient(configuredBase);
