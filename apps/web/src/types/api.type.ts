import type { RevenuePeriod } from "@/enums/commerce.enum";
import type { PromotionsSummary } from "./promotion.type";
import type { RevenueSummary } from "./revenue.type";
import type { ReviewDecision } from "@/enums/simulation.enum";
import type { CandidatesResponse, ReviewRequest, ReviewResult, Simulation, SimulationsResponse } from "./simulation.type";
import type { ControlStage } from "./agent.type";
import type { ProductInventory, StoreResponse } from "./twin.type";

export type HealthResponse = {
  status: "ok" | "degraded";
  service: "retailtwin-api";
  environment: string;
  store_id: string;
  fixture_loaded: boolean;
};

/** Where the flagship demo controller (#41) stands. */
export type FlagshipPhase = "IDLE" | "RUNNING" | "COMPLETE" | "ERROR";

/**
 * `POST /flagship/start`: the run it started. TODO(BE): #41 (PR #202) answers only once the
 * run has ended; the web app needs it to answer at once (202) with the run's `correlation_id`.
 */
export type FlagshipStartResponse = { run_id: string; correlation_id: string | null; phase: FlagshipPhase };

/** `GET /flagship/status`, the fields the web app reads. */
export type FlagshipStatusResponse = {
  run_id: string;
  phase: FlagshipPhase;
  correlation_id: string | null;
  /** Why the run failed, while `phase` is ERROR. */
  error: string | null;
};

/** One entry of `GET /agent/events`, as apps/api serves `AgentActivityEntry`. */
export type AgentEvent = {
  id: string;
  ts: string;
  stage: ControlStage;
  status: string;
  correlation_id: string;
  decision?: string | null;
  simulation_id?: string | null;
  sku?: string | null;
  shelf_id?: string | null;
  slot_id?: string | null;
  summary?: string | null;
};

/** `GET /agent/events?since=`: a page of the feed, and the cursor of the next one (null at the end). */
export type AgentEventsResponse = { events: AgentEvent[]; cursor: string | null };

export type RetailTwinClient = {
  health: () => Promise<HealthResponse>;
  store: () => Promise<StoreResponse>;
  inventory: (sku: string) => Promise<ProductInventory>;
  /** `GET /revenue?period=`. TODO(BE): not served by apps/api yet. */
  revenue: (period: RevenuePeriod) => Promise<RevenueSummary>;
  /** `GET /promotions`. TODO(BE): not served by apps/api yet. */
  promotions: () => Promise<PromotionsSummary>;
  /** `GET /simulations?status=open`. TODO(BE): not served by apps/api yet (#26). */
  simulations: () => Promise<SimulationsResponse>;
  /** `GET /simulations/{simulation_id}`. TODO(BE): not served by apps/api yet (#26). */
  simulation: (simulationId: string) => Promise<Simulation>;
  /** `GET /simulations/{simulation_id}/candidates`. */
  candidates: (simulationId: string) => Promise<CandidatesResponse>;
  /**
   * `POST /simulations/{simulation_id}/approve|reject`. The only write the web app makes:
   * it asks, and the guard and the Executor decide. TODO(BE): not served by apps/api yet.
   */
  reviewSimulation: (simulationId: string, decision: ReviewDecision, request: ReviewRequest) => Promise<ReviewResult>;
  /** `POST /flagship/reset`: reseeds the Live Twin for the flagship demo (#41). TODO(BE): not mounted in the deployed API yet. */
  flagshipReset: () => Promise<unknown>;
  /** `POST /flagship/start`: starts the flagship run (#41). TODO(BE): see `FlagshipStartResponse`. */
  flagshipStart: () => Promise<FlagshipStartResponse>;
  /** `GET /flagship/status` (#41). */
  flagshipStatus: () => Promise<FlagshipStatusResponse>;
  /** `GET /agent/events?since=`: the agent activity feed, from `since` (the start when omitted). */
  agentEvents: (since?: string | null) => Promise<AgentEventsResponse>;
};
