import i18n from "@/i18n";
import { isDemoMode } from "@/core/twin/demoMode";
import type { AgentEventsResponse, FlagshipStatusResponse, HealthResponse, RetailTwinClient } from "@/types/api.type";
import { PROMOTION_KIND, PROMOTION_STATUSES, REVENUE_PERIOD } from "@/enums/commerce.enum";
import { ContractError } from "@/core/commerce/revenueContract";
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
    buy_x_get_y: PROMOTION_KIND.BuyXGetY,
    bundle: PROMOTION_KIND.Bundle,
    loyalty_multiplier: PROMOTION_KIND.LoyaltyMultiplier,
  };

  const isObject = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
  const isText = (value: unknown): value is string => typeof value === "string" && value.trim() !== "";
  const isInstant = (value: unknown): value is string => isText(value) && !Number.isNaN(Date.parse(value));

  /**
   * Transform a BE `Promotion` (from `PromotionsResponse.promotions`) to the FE `Promotion` type.
   * Validates required fields and throws ContractError if malformed.
   */
  function toPromotion(raw: unknown, index = 0): Promotion {
    if (!isObject(raw)) throw new ContractError(`promotions[${index}]`);
    const rawId = raw.promotion_id ?? raw.id;
    if (!isText(rawId)) throw new ContractError(`promotions[${index}].id`);
    const rawName = raw.name;
    if (!isText(rawName)) throw new ContractError(`promotions[${index}].name`);
    const rawStatus = raw.status;
    if (!isText(rawStatus) || !PROMOTION_STATUSES.includes(rawStatus as never)) {
      throw new ContractError(`promotions[${index}].status`);
    }
    const rawStart = raw.start_time ?? raw.starts_at;
    if (!isInstant(rawStart)) throw new ContractError(`promotions[${index}].starts_at`);
    const rawEnd = raw.end_time ?? raw.ends_at;
    if (!isInstant(rawEnd)) throw new ContractError(`promotions[${index}].ends_at`);

    const rawKind = (raw.promotion_type ?? raw.kind ?? "") as string;
    const kind = PROMOTION_TYPE_TO_KIND[rawKind] ?? PROMOTION_KIND.Unknown;
    const value = raw.discount_value !== undefined ? raw.discount_value : raw.value !== undefined ? raw.value : null;
    const discountCost = raw.discount_cost !== undefined ? raw.discount_cost : null;

    return {
      id: rawId,
      name: rawName,
      kind,
      status: rawStatus as Promotion["status"],
      value: typeof value === "number" && Number.isFinite(value) ? value : null,
      starts_at: rawStart,
      ends_at: rawEnd,
      skus: Array.isArray(raw.skus) ? (raw.skus as string[]) : (isText(raw.sku) ? [raw.sku] : []),
      revenue: typeof raw.revenue === "number" && Number.isFinite(raw.revenue) ? raw.revenue : 0,
      incremental_revenue: typeof raw.incremental_revenue === "number" && Number.isFinite(raw.incremental_revenue) ? raw.incremental_revenue : 0,
      discount_cost: typeof discountCost === "number" && Number.isFinite(discountCost) ? discountCost : null,
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
        const rawPromotions = Array.isArray(response.promotions) ? response.promotions : [];
        const promotions: Promotion[] = rawPromotions.map(
          (p, index) =>
            isObject(p) && "kind" in p && typeof p.kind === "string"
              ? (p as Promotion)
              : toPromotion(p, index),
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
