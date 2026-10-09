import { Chip } from "@heroui/react";
import { useTranslation } from "react-i18next";
import { issueReason } from "@/core/api/validate";
import { inspectProduct } from "@/core/twin/twinIssues";
import { INSPECTION_KIND } from "@/enums/twin.enum";
import { useTwinIssues } from "@/hooks/twinIssues.hook";
import { useTwinStore } from "@/state/twin.store";
import { Figures, InspectorCard } from "./InspectorCard";

/** Twin figures of the selected product. Click an item on a shelf, or open `/?product=P001`. */
export function ProductInspector({ productId }: { productId: string }) {
  const { t } = useTranslation();
  const live = useTwinStore((state) => state.live);
  const issues = useTwinIssues();
  const inspection = inspectProduct(productId, live, issues);

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
