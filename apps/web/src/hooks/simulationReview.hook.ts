import { useState } from "react";
import { useTranslation } from "react-i18next";
import { notify } from "@/core/notify";
import type { SimulationReviewer } from "@/core/twin/simulationReview";
import { GUARD_VERDICT, REVIEW_DECISION, SIMULATION_STATUS, type ReviewDecision } from "@/enums/simulation.enum";
import type { ReviewResult, Simulation } from "@/types/simulation.type";

/**
 * Accept and Reject for the simulation on screen. A review only asks: the twin state on
 * screen changes when the live feed and the simulation feed say so, never here. An
 * evaluated run can be reviewed once; after a committed or rejected answer it waits for
 * the run to close.
 */
export function useSimulationReview(reviewer: SimulationReviewer | null, simulation: Simulation | null) {
  const { t } = useTranslation();
  const [pending, setPending] = useState<ReviewDecision | null>(null);
  const [settledId, setSettledId] = useState<string | null>(null);

  const announce = (result: ReviewResult, base: string) => {
    const id = result.simulation_id;
    const reason = result.reason_code ?? t("simulation.review.noReason");
    if (result.decision === REVIEW_DECISION.Reject) {
      notify.info(t("simulation.review.rejected", { id }), t("simulation.review.liveUnchanged"));
      return;
    }
    switch (result.verdict) {
      case GUARD_VERDICT.Allow:
        notify.success(
          t("simulation.review.approved", { id }),
          result.live_context_version
            ? t("simulation.review.committed", { version: result.live_context_version })
            : t("simulation.review.executing"),
        );
        return;
      case GUARD_VERDICT.RefreshRequired:
        notify.warning(t("simulation.review.refresh", { id }), t("simulation.review.refreshHint", { base }));
        return;
      case GUARD_VERDICT.Deny:
        notify.warning(t("simulation.review.denied", { id }), reason);
        return;
      default:
        notify.info(t("simulation.review.humanReview", { id }), reason);
    }
  };

  const review = async (decision: ReviewDecision) => {
    if (!reviewer || !simulation || pending) return;
    setPending(decision);
    try {
      const result = await reviewer(simulation, decision);
      announce(result, simulation.base_context_version);
      if (result.status === SIMULATION_STATUS.Committed || result.status === SIMULATION_STATUS.Rejected) {
        setSettledId(result.simulation_id);
      }
    } catch (error) {
      notify.error(t("simulation.review.failed"), error);
    } finally {
      setPending(null);
    }
  };

  const settled = simulation !== null && settledId === simulation.simulation_id;
  return {
    review,
    pending,
    settled,
    /** Accept and Reject show only for an evaluated run, while something can take the review. */
    canReview: reviewer !== null && simulation?.status === SIMULATION_STATUS.Evaluated && !settled,
  };
}
