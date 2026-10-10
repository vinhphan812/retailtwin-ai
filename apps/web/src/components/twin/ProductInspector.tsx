import { Chip } from "@heroui/react";
import { useTranslation } from "react-i18next";
import { issueReason } from "@/core/api/validate";
import { format } from "@/core/utils/format";
import { ANOMALY_SEVERITY } from "@/enums/anomaly.enum";
import { inspectProduct } from "@/core/twin/twinIssues";
import { INSPECTION_KIND } from "@/enums/twin.enum";
import { useTwinIssues } from "@/hooks/twinIssues.hook";
import { anomaliesOf, useAnomalyStore } from "@/state/anomaly.store";
import { useTwinStore } from "@/state/twin.store";
import type { Anomaly } from "@/types/anomaly.type";
import { Figures, InspectorCard } from "./InspectorCard";

const SEVERITY_COLOR = {
  [ANOMALY_SEVERITY.Low]: "default",
  [ANOMALY_SEVERITY.Medium]: "warning",
  [ANOMALY_SEVERITY.High]: "danger",
} as const;

/** The product's open anomalies. One read from an older twin state says so. */
function Anomalies({ anomalies, contextVersion }: { anomalies: Anomaly[]; contextVersion: string }) {
  const { t } = useTranslation();
  if (anomalies.length === 0) return null;
  return (
    <ul className="flex flex-col gap-1" aria-label={t("anomaly.list")}>
      {anomalies.map((anomaly) => (
        <li key={anomaly.anomaly_id} className="flex flex-wrap items-center gap-2">
          <Chip size="sm" variant="flat" color={SEVERITY_COLOR[anomaly.severity]}>
            {t(`anomaly.kind.${anomaly.kind}`)} · {t(`anomaly.severity.${anomaly.severity}`)}
          </Chip>
          <span className="text-default-500">{t("anomaly.detected", { time: format.hour(anomaly.detected_at) })}</span>
          {anomaly.context_version !== contextVersion ? (
            <span className="text-default-500">{t("anomaly.olderState")}</span>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

/** Twin figures and open anomalies of the selected product. Click an item on a shelf, or open `/?product=P001`. */
export function ProductInspector({ productId }: { productId: string }) {
  const { t } = useTranslation();
  const live = useTwinStore((state) => state.live);
  const issues = useTwinIssues();
  const inspection = inspectProduct(productId, live, issues);
  const anomalies = anomaliesOf(useAnomalyStore((state) => state.anomalies), productId);

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
        <Anomalies anomalies={anomalies} contextVersion={live.context_version} />
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
    </InspectorCard>
  );
}
