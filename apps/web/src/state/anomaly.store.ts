import { create } from "zustand";
import type { AnomaliesResponse, Anomaly } from "@/types/anomaly.type";

type AnomalyStore = {
  /** Open anomalies, as the anomaly API last served them. */
  anomalies: Anomaly[];
  /** Replaces every open anomaly with a fresh `GET /anomalies` response. */
  setAll: (response: AnomaliesResponse) => void;
  /** An anomaly event: adds the anomaly, or replaces the one with the same id. */
  raise: (anomaly: Anomaly) => void;
  /** The anomaly was handled and is no longer open. */
  resolve: (anomalyId: string) => void;
};

/**
 * Read-side copy of the open anomalies. Never the source of truth.
 * TODO(BE): apps/api serves no anomalies yet; fill this from `GET /anomalies` and its
 * event feed once they exist. Until then only `?twin=demo` and tests fill it.
 */
export const useAnomalyStore = create<AnomalyStore>()((set) => ({
  anomalies: [],
  setAll: (response) => set({ anomalies: response.anomalies }),
  raise: (anomaly) =>
    set((state) => ({
      anomalies: [...state.anomalies.filter((open) => open.anomaly_id !== anomaly.anomaly_id), anomaly],
    })),
  resolve: (anomalyId) =>
    set((state) => ({ anomalies: state.anomalies.filter((open) => open.anomaly_id !== anomalyId) })),
}));

/** Open anomalies on one product, oldest first. */
export function anomaliesOf(anomalies: Anomaly[], sku: string) {
  return anomalies.filter((anomaly) => anomaly.sku === sku);
}
