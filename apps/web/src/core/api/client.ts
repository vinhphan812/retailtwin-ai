import i18n from "@/i18n";
import { isDemoMode } from "@/core/twin/demoMode";
import type { AgentEventsResponse, FlagshipStatusResponse, HealthResponse, RetailTwinClient } from "@/types/api.type";
import type { ProductInventory, StoreResponse } from "@/types/twin.type";
import type { PromotionsSummary } from "@/types/promotion.type";
import { ContractError, parseRevenueResponse, toRevenueSummary } from "@/core/commerce/revenueContract";
import { revenueQuery, revenueSearch } from "@/core/commerce/revenueWindow";
import type { CandidatesResponse, ReviewResult, Simulation, SimulationsResponse } from "@/types/simulation.type";
import type { AnomaliesResponse } from "@/types/anomaly.type";
import type { CheckoutResponse } from "@/types/checkout.type";

/** One field apps/api found invalid, from the `details` of its error envelope (a 422). */
export type ErrorDetail = { field: string; message: string };

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  /** The `X-Correlation-ID` of the request, to find it in the apps/api logs; null when none was sent or served. */
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

/** The code of a payload that broke the contract: answered, but none of it is shown. */
export const INVALID_RESPONSE = "invalid_response";

type ErrorEnvelope = {
  error?: {
    code?: unknown;
    message?: unknown;
    details?: unknown;
  };
};

/**
 * How a read goes: `traced` sends an `X-Correlation-ID` (apps/api's CORS allows it, and its
 * logs carry it), so a failure can name the request; `parse` checks the payload against the
 * contract, and a payload it rejects fails with `INVALID_RESPONSE` instead of being cast.
 */
type ReadOptions<T> = { traced?: boolean; parse?: (raw: unknown) => T };

const newCorrelationId = () => `web-${crypto.randomUUID()}`;

export function createClient(baseUrl: string, fetchImpl?: typeof fetch): RetailTwinClient {
  const base = baseUrl.replace(/\/$/, "");

  async function request<T>(path: string, init?: RequestInit, { traced = false, parse }: ReadOptions<T> = {}): Promise<T> {
    // The demo is synthetic: whatever control a click reaches, it never writes to apps/api.
    if (init?.method && init.method !== "GET" && isDemoMode()) {
      throw new ApiError(0, "demo_read_only", i18n.t("errors.demoReadOnly"));
    }
    const doFetch = fetchImpl ?? fetch;
    const sent = traced ? newCorrelationId() : null;
    let response: Response;
    try {
      response = await doFetch(`${base}${path}`, sent ? { ...init, headers: { ...init?.headers, "X-Correlation-ID": sent } } : init);
    } catch {
      throw new ApiError(0, "network_error", i18n.t("errors.unreachable"), sent);
    }
    // apps/api echoes the id; a cross-origin page reads it only when the header is exposed.
    const correlationId = response.headers?.get?.("x-correlation-id") || sent;
    if (!response.ok) {
      throw await toApiError(response, correlationId);
    }
    let raw: unknown;
    try {
      raw = await response.json();
    } catch {
      throw new ApiError(response.status, INVALID_RESPONSE, i18n.t("errors.invalidResponse", { field: "body" }), correlationId);
    }
    if (!parse) return raw as T;
    try {
      return parse(raw);
    } catch (error) {
      const field = error instanceof ContractError ? error.field : "response";
      throw new ApiError(response.status, INVALID_RESPONSE, i18n.t("errors.invalidResponse", { field }), correlationId);
    }
  }

  return {
    health: () => request<HealthResponse>("/health"),
    store: () => request<StoreResponse>("/store"),
    inventory: (sku: string) => request<ProductInventory>(`/inventory/${encodeURIComponent(sku)}`),
    // The lens window is never sent as is: apps/api takes a grain (`hourly`, `daily`) and a window.
    revenue: (period) => {
      const query = revenueQuery(period);
      return request(`/revenue?${revenueSearch(query)}`, undefined, {
        traced: true,
        parse: (raw) => toRevenueSummary(parseRevenueResponse(raw), period, query),
      });
    },
    // TODO(#333): `GET /promotions` serves another shape than `PromotionsSummary`; bound there.
    promotions: () => request<PromotionsSummary>("/promotions", undefined, { traced: true }),
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
    flagshipStatus: () => request<FlagshipStatusResponse>("/flagship/status"),
    flagshipReset: () => request<{ run_id: string }>("/flagship/reset", { method: "POST" }),
    flagshipStart: (correlationId: string) =>
      request<{ run_id: string; correlation_id: string; phase: string }>("/flagship/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ correlation_id: correlationId }),
      }),
    agentEvents: (since?: string | null) =>
      request<AgentEventsResponse>(`/agent/events${since ? `?since=${encodeURIComponent(since)}` : ""}`, undefined, {
        traced: true,
      }),
  };
}

/** The fields of a 422's `details`, as apps/api's validation handler lists them; anything else is left out. */
function detailsOf(value: unknown): ErrorDetail[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item): ErrorDetail[] =>
    typeof item?.field === "string" && typeof item?.message === "string" ? [{ field: item.field, message: item.message }] : [],
  );
}

async function toApiError(response: Response, correlationId: string | null = null): Promise<ApiError> {
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
  return new ApiError(response.status, code, message, correlationId, detailsOf(envelope?.error?.details));
}

const configuredBase = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export const defaultClient = createClient(configuredBase);
