import { Button } from "@heroui/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { resolveAnomalies, simulateAnomaly } from "@/core/twin/simulateAnomaly";
import {
  ANOMALY_KIND,
  ANOMALY_KINDS,
  ANOMALY_SEVERITIES,
  ANOMALY_SEVERITY,
  type AnomalyKind,
  type AnomalySeverity,
} from "@/enums/anomaly.enum";
import type { ProductInventory } from "@/types/twin.type";

type AnomalySimulatorProps = {
  product: ProductInventory;
  contextVersion: string;
  /** The product has open anomalies to clear. */
  hasAnomalies: boolean;
};

/**
 * Raises an anomaly event of a chosen kind and severity on the product, or clears its
 * anomalies: the same as `twin.raise()` and `twin.resolve()` in the console. Development
 * builds only (`canSimulateAnomalies`).
 */
export function AnomalySimulator({ product, contextVersion, hasAnomalies }: AnomalySimulatorProps) {
  const { t } = useTranslation();
  const [kind, setKind] = useState<AnomalyKind>(ANOMALY_KIND.Stockout);
  const [severity, setSeverity] = useState<AnomalySeverity>(ANOMALY_SEVERITY.High);

  return (
    <form
      className="flex flex-col gap-2 rounded-md border border-dashed border-line p-2"
      aria-label={t("anomaly.simulate.title")}
      onSubmit={(event) => {
        event.preventDefault();
        simulateAnomaly(product, kind, severity, contextVersion);
      }}
    >
      <p className="text-xs text-default-500">{t("anomaly.simulate.hint")}</p>
      <div className="flex gap-2">
        <select
          className="text-field min-w-0 flex-1"
          aria-label={t("anomaly.simulate.kind")}
          value={kind}
          onChange={(event) => setKind(event.target.value as AnomalyKind)}
        >
          {ANOMALY_KINDS.map((value) => (
            <option key={value} value={value}>
              {t(`anomaly.kind.${value}`)}
            </option>
          ))}
        </select>
        <select
          className="text-field min-w-0 flex-1"
          aria-label={t("anomaly.simulate.severity")}
          value={severity}
          onChange={(event) => setSeverity(event.target.value as AnomalySeverity)}
        >
          {ANOMALY_SEVERITIES.map((value) => (
            <option key={value} value={value}>
              {t(`anomaly.severity.${value}`)}
            </option>
          ))}
        </select>
      </div>
      <div className="flex gap-2">
        <Button type="submit" size="sm" radius="sm" color="warning" variant="flat" className="flex-1 cursor-pointer font-semibold">
          {t("anomaly.simulate.raise")}
        </Button>
        <Button
          size="sm"
          radius="sm"
          variant="light"
          isDisabled={!hasAnomalies}
          className="flex-1 cursor-pointer"
          onPress={() => resolveAnomalies(product.sku)}
        >
          {t("anomaly.simulate.resolve")}
        </Button>
      </div>
    </form>
  );
}
