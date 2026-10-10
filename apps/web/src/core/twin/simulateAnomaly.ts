import type { AnomalyKind, AnomalySeverity } from "@/enums/anomaly.enum";
import { anomalyFor } from "@/fixtures/demo/anomalies";
import { useAnomalyStore } from "@/state/anomaly.store";
import type { ProductInventory } from "@/types/twin.type";

/**
 * Raising anomalies by hand, to check the highlight before the detector serves any.
 * Development builds only: in production an anomaly only ever comes from the anomaly API.
 */
export const canSimulateAnomalies = () => import.meta.env.DEV;

/** Raises an anomaly event on `product`, as read from the twin state at `contextVersion`. Returns its id. */
export function simulateAnomaly(
  product: ProductInventory,
  kind: AnomalyKind,
  severity: AnomalySeverity,
  contextVersion: string,
): string {
  const anomaly = anomalyFor(product, kind, severity, contextVersion, new Date().toISOString());
  useAnomalyStore.getState().raise(anomaly);
  return anomaly.anomaly_id;
}

/** Closes every open anomaly on `sku`. */
export function resolveAnomalies(sku: string) {
  const { anomalies, resolve } = useAnomalyStore.getState();
  anomalies.filter((anomaly) => anomaly.sku === sku).forEach((anomaly) => resolve(anomaly.anomaly_id));
}
