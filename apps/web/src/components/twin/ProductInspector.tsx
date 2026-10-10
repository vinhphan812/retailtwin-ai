import { Button, Chip } from "@heroui/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { issueReason } from "@/core/api/validate";
import { canSimulateAnomalies } from "@/core/twin/simulateAnomaly";
import { inspectProduct } from "@/core/twin/twinIssues";
import { INSPECTION_KIND } from "@/enums/twin.enum";
import { useTwinIssues } from "@/hooks/twinIssues.hook";
import { anomaliesOf, useAnomalyStore } from "@/state/anomaly.store";
import { useTwinStore } from "@/state/twin.store";
import { useUiStore } from "@/state/ui.store";
import { AnomalyList } from "./AnomalyList";
import { AnomalySimulator } from "./AnomalySimulator";
import { Figures, InspectorCard } from "./InspectorCard";

/**
 * Twin figures and open anomalies of the selected product. Click an item on a shelf, or
 * open `/?product=P001`. **Details** opens the product's dialog; in development builds,
 * **Simulate anomaly** raises or clears an anomaly on it.
 */
export function ProductInspector({ productId }: { productId: string }) {
  const { t } = useTranslation();
  const live = useTwinStore((state) => state.live);
  const issues = useTwinIssues();
  const inspection = inspectProduct(productId, live, issues);
  const anomalies = anomaliesOf(useAnomalyStore((state) => state.anomalies), productId);
  const showDetails = useUiStore((state) => state.showDetails);
  const [simulating, setSimulating] = useState(false);

  return (
    <InspectorCard title={productId} label={t("inspector.label", { sku: productId })}>
      {inspection.kind === INSPECTION_KIND.Loading ? <p>{t("twin.loading")}</p> : null}
      {inspection.kind === INSPECTION_KIND.Missing ? (
        <Chip color="danger" variant="flat">
          {t("inspector.missing")}
        </Chip>
      ) : null}
      {inspection.kind === INSPECTION_KIND.Invalid ? (
        <div className="flex flex-col gap-2">
          <Chip color="warning" variant="flat">
            {t("inspector.invalid")}
          </Chip>
          <p>{issueReason(inspection.issue)}</p>
        </div>
      ) : null}
      {inspection.kind === INSPECTION_KIND.Ok && live ? (
        <AnomalyList anomalies={anomalies} contextVersion={live.context_version} />
      ) : null}
      {inspection.kind === INSPECTION_KIND.Ok ? (
        <Figures
          rows={[
            [t("inspector.shelfSlot"), `${inspection.product.shelf_id} / ${inspection.product.slot_id}`],
            [t("inspector.facings"), inspection.product.facings],
            [t("inspector.onShelf"), inspection.product.shelf_quantity],
            [t("inspector.backroom"), inspection.product.backroom_quantity],
            [t("inspector.version"), inspection.product.version],
          ]}
        />
      ) : null}
      {inspection.kind === INSPECTION_KIND.Ok && live ? (
        <div className="mt-3 flex flex-col gap-2">
          <div className="flex gap-2">
            <Button
              size="sm"
              radius="sm"
              variant="flat"
              className="flex-1 cursor-pointer font-semibold"
              onPress={() => showDetails(productId)}
            >
              {t("inspector.details")}
            </Button>
            {canSimulateAnomalies() ? (
              <Button
                size="sm"
                radius="sm"
                variant={simulating ? "solid" : "light"}
                aria-expanded={simulating}
                className="flex-1 cursor-pointer"
                onPress={() => setSimulating((open) => !open)}
              >
                {t("anomaly.simulate.toggle")}
              </Button>
            ) : null}
          </div>
          {simulating && canSimulateAnomalies() ? (
            <AnomalySimulator
              product={inspection.product}
              contextVersion={live.context_version}
              hasAnomalies={anomalies.length > 0}
            />
          ) : null}
        </div>
      ) : null}
    </InspectorCard>
  );
}
