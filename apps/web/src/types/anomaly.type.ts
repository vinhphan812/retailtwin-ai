import type { AnomalyKind, AnomalySeverity } from "@/enums/anomaly.enum";

/**
 * One open anomaly on a product, as the anomaly API serves it.
 */
export type Anomaly = {
  anomaly_id: string;
  store_id: string;
  sku: string;
  /** Where the product stood when the anomaly was detected. */
  shelf_id: string;
  slot_id: string;
  kind: AnomalyKind;
  severity: AnomalySeverity;
  /** ISO timestamp. */
  detected_at: string;
  /** Twin state the detector read, as `StoreResponse.context_version`. */
  context_version: string;
  /** Ties the anomaly to the agent run that handles it. */
  correlation_id: string;
};

export type AnomaliesResponse = {
  store_id: string;
  context_version: string;
  anomalies: Anomaly[];
};
