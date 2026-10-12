import type { RevenuePeriod } from "@/enums/commerce.enum";
import type { PromotionsSummary } from "./promotion.type";
import type { RevenueSummary } from "./revenue.type";
import type { ReviewDecision } from "@/enums/simulation.enum";
import type { ReviewRequest, ReviewResult, Simulation, SimulationsResponse } from "./simulation.type";
import type { ProductInventory, StoreResponse } from "./twin.type";

export type HealthResponse = {
  status: "ok" | "degraded";
  service: "retailtwin-api";
  environment: string;
  store_id: string;
  fixture_loaded: boolean;
};

export type RetailTwinClient = {
  health: () => Promise<HealthResponse>;
  store: () => Promise<StoreResponse>;
  inventory: (sku: string) => Promise<ProductInventory>;
  /** `GET /revenue?period=`. TODO(BE): not served by apps/api yet. */
  revenue: (period: RevenuePeriod) => Promise<RevenueSummary>;
  /** `GET /promotions`. TODO(BE): not served by apps/api yet. */
  promotions: () => Promise<PromotionsSummary>;
  /** `GET /simulations?status=open`. */
  simulations: () => Promise<SimulationsResponse>;
  /** `GET /simulations/{simulation_id}`. */
  simulation: (simulationId: string) => Promise<Simulation>;
  /**
   * `POST /simulations/{simulation_id}/approve|reject`. The only write the web app makes:
   * it asks, and the guard and the Executor decide.
   */
  reviewSimulation: (simulationId: string, decision: ReviewDecision, request: ReviewRequest) => Promise<ReviewResult>;
};
