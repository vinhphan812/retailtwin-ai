import { Button, Chip, Modal, ModalBody, ModalContent, ModalFooter, ModalHeader } from "@heroui/react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { discountOf } from "@/components/promotions/PromotionCard";
import { stockState } from "@/core/twin/fixtureStock";
import { format } from "@/core/utils/format";
import { ENTITY_TYPE } from "@/enums/scene.enum";
import { STOCK_STATE, type StockState } from "@/enums/stock.enum";
import { LENS } from "@/enums/ui.enum";
import { usePromotions } from "@/hooks/commerce.hook";
import { anomaliesOf, useAnomalyStore } from "@/state/anomaly.store";
import { usePanelStore } from "@/state/panel.store";
import { useTwinStore } from "@/state/twin.store";
import { useUiStore } from "@/state/ui.store";
import { AnomalyList } from "./AnomalyList";
import "@/components/commerce/commerce.css";
import { Figures } from "./InspectorCard";

const STATE_COLOR: Record<StockState, "success" | "warning" | "danger"> = {
  [STOCK_STATE.Ok]: "success",
  [STOCK_STATE.Low]: "warning",
  [STOCK_STATE.Out]: "danger",
};

/** One section of the dialog: a small heading over its content. */
function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-2" aria-label={title}>
      <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">{title}</h3>
      {children}
    </section>
  );
}

/**
 * Everything about one product in a centered dialog: its twin figures and stock state,
 * its open anomalies, and the promotions it is in. Opened by **Details** on the product
 * card or on a shelf's product list (`showDetails`). Every figure comes from the live
 * state, the anomaly store, and `GET /promotions`.
 */
export function ProductDetailsDialog() {
  const { t } = useTranslation();
  const sku = useUiStore((state) => state.detailsSku);
  const showDetails = useUiStore((state) => state.showDetails);
  const select = useUiStore((state) => state.select);
  const setLens = useUiStore((state) => state.setLens);
  const openPanel = usePanelStore((state) => state.setOpen);
  const live = useTwinStore((state) => state.live);
  const allAnomalies = useAnomalyStore((state) => state.anomalies);
  const { promotions } = usePromotions();

  const product = sku ? live?.products.find((candidate) => candidate.sku === sku) : undefined;
  const anomalies = sku ? anomaliesOf(allAnomalies, sku) : [];
  const inPromotions = sku ? promotions.filter((promotion) => promotion.skus.includes(sku)) : [];
  const close = () => showDetails(null);
  const state = product ? stockState({ facings: product.facings, shelfQuantity: product.shelf_quantity }) : null;

  return (
    <Modal isOpen={sku !== null} onClose={close} size="lg" placement="center" backdrop="blur" scrollBehavior="inside">
      <ModalContent aria-label={sku ? t("inspector.detailsOf", { sku }) : undefined}>
        {sku ? (
          <>
            <ModalHeader className="flex flex-col gap-1">
              <span className="flex flex-wrap items-center gap-2">
                {t("productDetails.title", { sku })}
                {state ? (
                  <Chip size="sm" variant="flat" color={STATE_COLOR[state]}>
                    {t(`inspector.state.${state}`)}
                  </Chip>
                ) : null}
              </span>
              {product && live ? (
                <span className="text-xs font-normal text-ink-muted">
                  {t("productDetails.subtitle", {
                    shelf: product.shelf_id,
                    slot: product.slot_id,
                    contextVersion: live.context_version,
                  })}
                </span>
              ) : null}
            </ModalHeader>
            <ModalBody className="gap-5 text-sm">
              {product && live ? (
                <>
                  <Section title={t("productDetails.twin")}>
                    <Figures
                      rows={[
                        [t("inspector.shelfSlot"), `${product.shelf_id} / ${product.slot_id}`],
                        [t("inspector.facings"), format.count(product.facings)],
                        [t("inspector.onShelf"), format.count(product.shelf_quantity)],
                        [t("inspector.backroom"), format.count(product.backroom_quantity)],
                        [t("productDetails.stockState"), t(`inspector.state.${state!}`)],
                        [t("inspector.version"), product.version],
                      ]}
                    />
                  </Section>
                  <Section title={t("productDetails.anomalies")}>
                    {anomalies.length ? (
                      <AnomalyList anomalies={anomalies} contextVersion={live.context_version} />
                    ) : (
                      <p className="text-default-500">{t("productDetails.noAnomalies")}</p>
                    )}
                  </Section>
                </>
              ) : (
                <Chip color="danger" variant="flat">
                  {t("inspector.missing")}
                </Chip>
              )}
              <Section title={t("productDetails.promotions")}>
                {inPromotions.length ? (
                  <ul className="flex flex-col gap-2">
                    {inPromotions.map((promotion) => (
                      <li key={promotion.id} className="promotion-card" data-status={promotion.status}>
                        <header className="promotion-card-head">
                          <span className="promotion-status">
                            <span className="promotion-status-dot" aria-hidden />
                            {t(`promotions.status.${promotion.status}`)}
                          </span>
                          <span className="promotion-kind">
                            {t(`promotions.kind.${promotion.kind}`, { value: discountOf(promotion) })}
                          </span>
                        </header>
                        <h4 className="promotion-name">{promotion.name}</h4>
                        <p className="promotion-meta">
                          {t("promotions.dates", { start: format.day(promotion.starts_at), end: format.day(promotion.ends_at) })}{" "}
                          · {t("promotions.skus", { count: promotion.skus.length })}
                        </p>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-default-500">{t("productDetails.noPromotions")}</p>
                )}
              </Section>
            </ModalBody>
            <ModalFooter>
              {inPromotions.length ? (
                <Button
                  size="sm"
                  radius="sm"
                  variant="light"
                  className="cursor-pointer"
                  onPress={() => {
                    setLens(LENS.Promotions);
                    openPanel(true);
                    close();
                  }}
                >
                  {t("productDetails.openPromotions")}
                </Button>
              ) : null}
              {product ? (
                <Button
                  size="sm"
                  radius="sm"
                  variant="flat"
                  className="cursor-pointer font-semibold"
                  onPress={() => {
                    select(sku, ENTITY_TYPE.Product);
                    close();
                  }}
                >
                  {t("productDetails.showInStore")}
                </Button>
              ) : null}
              <Button size="sm" radius="sm" variant="light" className="cursor-pointer" onPress={close}>
                {t("productDetails.close")}
              </Button>
            </ModalFooter>
          </>
        ) : null}
      </ModalContent>
    </Modal>
  );
}
