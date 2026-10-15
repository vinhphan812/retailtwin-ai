import type { KpiTrend } from "@/enums/simulation.enum";
import type { ActivityEntry } from "@/types/agent.type";
import type { Candidate, CandidateKPI } from "@/types/simulation.type";
import { compareCandidates } from "./candidateComparison";

/** One KPI before and after: the baseline's value, the accepted candidate's, and the move between them. */
export type ImpactRow = {
  name: string;
  before: CandidateKPI;
  after: CandidateKPI;
  /** `after - before`, a display-only difference of two served values. */
  delta: number;
  trend: KpiTrend;
};

/**
 * What an executed approval changed, as the evaluator scored it: the baseline candidate's
 * KPIs (before) against the accepted candidate's (after). Kept after the run closes, with
 * the run's candidates, so the comparison can still be shown.
 */
export type AiImpact = {
  simulation_id: string;
  candidate_id: string;
  evaluator_version: string;
  rows: ImpactRow[];
  /** Every candidate of the run as served at the approval, baseline included. */
  candidates: Candidate[];
};

/**
 * The impact of approving candidate `candidateId` of `simulationId`, from the served
 * candidates. Null without an accepted candidate, without a served baseline, or when no
 * KPI was scored on both: the UI never fills in a value.
 */
export function impactOf(candidates: Candidate[], simulationId: string, candidateId: string | null): AiImpact | null {
  if (candidateId === null) return null;
  const own = candidates.filter((candidate) => candidate.simulation_id === simulationId);
  const accepted = own.find((candidate) => candidate.candidate_id === candidateId);
  const { baseline, rows } = compareCandidates(own);
  if (!accepted || !baseline || accepted === baseline) return null;
  const impactRows = rows.flatMap((row): ImpactRow[] => {
    const cell = row.cells[candidateId];
    if (!row.baseline || !cell || cell.delta === null || cell.trend === null) return [];
    return [{ name: row.name, before: row.baseline, after: cell.kpi, delta: cell.delta, trend: cell.trend }];
  });
  if (!impactRows.length) return null;
  return {
    simulation_id: simulationId,
    candidate_id: candidateId,
    evaluator_version: accepted.evaluator_version,
    rows: impactRows,
    candidates: structuredClone(own),
  };
}

/**
 * Whether an agent run of simulation `simulationId` has reached VERIFY: a run with an entry
 * naming the simulation, and a VERIFY entry under the same `correlation_id`.
 */
export function runVerified(activity: readonly ActivityEntry[], simulationId: string): boolean {
  const runs = new Set(
    activity.filter((entry) => entry.simulation_id === simulationId && entry.correlation_id).map((entry) => entry.correlation_id),
  );
  return activity.some((entry) => entry.stage === "VERIFY" && runs.has(entry.correlation_id));
}
