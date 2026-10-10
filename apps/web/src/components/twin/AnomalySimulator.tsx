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

type ChoiceProps<T extends string> = {
  label: string;
  options: readonly { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
};

/**
 * A row of radio chips. Static, unlike `Segmented`, whose sliding thumb measures its
 * layout and lands off target while the dialog around it scales in.
 */
function Choice<T extends string>({ label, options, value, onChange }: ChoiceProps<T>) {
  return (
    <div className="anomaly-simulator-field">
      <span>{label}</span>
      <div role="radiogroup" aria-label={label} className="anomaly-simulator-choices">
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={option.value === value}
            className="anomaly-simulator-choice"
            onClick={() => onChange(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}

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
      className="anomaly-simulator"
      aria-label={t("anomaly.simulate.title")}
      onSubmit={(event) => {
        event.preventDefault();
        simulateAnomaly(product, kind, severity, contextVersion);
      }}
    >
      <header className="anomaly-simulator-head">
        <span className="anomaly-simulator-badge">{t("anomaly.simulate.dev")}</span>
        <h4>{t("anomaly.simulate.title")}</h4>
      </header>
      <p className="anomaly-simulator-hint">{t("anomaly.simulate.hint")}</p>
      <Choice
        label={t("anomaly.simulate.kind")}
        value={kind}
        onChange={setKind}
        options={ANOMALY_KINDS.map((value) => ({ value, label: t(`anomaly.kind.${value}`) }))}
      />
      <Choice
        label={t("anomaly.simulate.severity")}
        value={severity}
        onChange={setSeverity}
        options={ANOMALY_SEVERITIES.map((value) => ({ value, label: t(`anomaly.severity.${value}`) }))}
      />
      <div className="anomaly-simulator-actions">
        <Button type="submit" size="sm" radius="sm" color="warning" variant="flat" className="cursor-pointer px-4 font-semibold">
          {t("anomaly.simulate.raise")}
        </Button>
        <Button
          size="sm"
          radius="sm"
          variant="light"
          isDisabled={!hasAnomalies}
          className="cursor-pointer"
          onPress={() => resolveAnomalies(product.sku)}
        >
          {t("anomaly.simulate.resolve")}
        </Button>
      </div>
    </form>
  );
}
