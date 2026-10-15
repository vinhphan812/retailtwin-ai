import { runVerified, type AiImpact } from "@/core/twin/aiImpact";
import { useImpactStore } from "@/state/impact.store";
import { useRunStore } from "@/state/run.store";

/** The last AI Impact, once an agent run of its simulation has reached VERIFY; else null. */
export function useVerifiedImpact(): AiImpact | null {
  const impact = useImpactStore((state) => state.last);
  const verified = useRunStore((state) => (impact ? runVerified(state.activity, impact.simulation_id) : false));
  return verified ? impact : null;
}
