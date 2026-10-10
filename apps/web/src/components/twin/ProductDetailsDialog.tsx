import { Button, Chip, Modal, ModalBody, ModalContent, ModalFooter, ModalHeader } from "@heroui/react";
import { useEffect, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { AlertIcon, PromotionIcon } from "@/components/icons";
import { discountOf } from "@/components/promotions/PromotionCard";
import { stockState } from "@/core/twin/fixtureStock";
import { canSimulateAnomalies } from "@/core/twin/simulateAnomaly";
import { format } from "@/core/utils/format";
import { ENTITY_TYPE } from "@/enums/scene.enum";
import { STOCK_STATE, type StockState } from "@/enums/stock.enum";
import { LENS } from "@/enums/ui.enum";
import { usePromotions } from "@/hooks/commerce.hook";
import { anomaliesOf, useAnomalyStore } from "@/state/anomaly.store";
import { usePanelStore } from "@/state/panel.store";
import { useTwinStore } from "@/state/twin.store";
import { useUiStore } from "@/state/ui.store";
import type { Anomaly } from "@/types/anomaly.type";
import type { ProductInventory } from "@/types/twin.type";
import { AnomalySimulator } from "./AnomalySimulator";
import "@/components/commerce/commerce.css";
import "./ProductDetailsDialog.css";

const STATE_COLOR: Record<StockState, "success" | "warning" | "danger"> = {
  [STOCK_STATE.Ok]: "success",
  [STOCK_STATE.Low]: "warning",
  [STOCK_STATE.Out]: "danger",
};

type SectionProps = { title: string; count?: number; action?: ReactNode; children: ReactNode };

/** One section of the dialog: a small heading, an optional count and action, then its content. */
function Section({ title, count, action, children }: SectionProps) {
  return (
    <section className="details-section" aria-label={title}>
      <div className="details-section-head">
        <h3 className="activity-section-title">
          {title}
          {count === undefined ? null : <span className="activity-count">{count}</span>}
        </h3>
        {action}
      </div>
      {children}
    </section>
  );
}

/** Stock tiles: units on the shelf against facings (with how full the front is), backroom, facings, version. */
function StockTiles({ product, state }: { product: ProductInventory; state: StockState }) {
  const { t } = useTranslation();
  const fill = product.facings ? Math.min(1, product.shelf_quantity / product.facings) : 0;
  return (
    <dl className="details-tiles">
      <div className="details-tile details-tile-wide" data-state={state}>
        <dt>{t("inspector.onShelf")}</dt>
        <dd>
          {format.count(product.shelf_quantity)}
          <small>{t("productDetails.ofFacings", { facings: product.facings })}</small>
        </dd>
        <span className="details-fill" aria-hidden>
          <span style={{ width: `${fill * 100}%` }} />
        </span>
      </div>
      <div className="details-tile">
        <dt>{t("inspector.backroom")}</dt>
        <dd>{format.count(product.backroom_quantity)}</dd>
      </div>
      <div className="details-tile">
        <dt>{t("inspector.facings")}</dt>
        <dd>{format.count(product.facings)}</dd>
      </div>
      <div className="details-tile">
        <dt>{t("inspector.version")}</dt>
        <dd>{product.version}</dd>
      </div>
    </dl>
  );
}

/** Open anomalies as rows marked by severity. One read from an older twin state says so. */
function AnomalyRows({ anomalies, contextVersion }: { anomalies: Anomaly[]; contextVersion: string }) {
  const { t } = useTranslation();
  if (anomalies.length === 0) return <p className="details-empty">{t("productDetails.noAnomalies")}</p>;
  return (
    <ul className="details-anomalies" aria-label={t("anomaly.list")}>
      {anomalies.map((anomaly) => (
        <li key={anomaly.anomaly_id} className="details-anomaly" data-severity={anomaly.severity}>
          <AlertIcon className="details-anomaly-icon" />
          <span className="details-anomaly-kind">{t(`anomaly.kind.${anomaly.kind}`)}</span>
          <span className="details-anomaly-severity">{t(`anomaly.severity.${anomaly.severity}`)}</span>
          <span className="details-anomaly-meta">
            {t("anomaly.detected", { time: format.hour(anomaly.detected_at) })}
            {anomaly.context_version !== contextVersion ? ` · ${t("anomaly.olderState")}` : ""}
          </span>
        </li>
      ))}
    </ul>
  );
}

/**
 * Everything about one product in a centered dialog: its stock in the twin, its open
 * anomalies, and the promotions it is in. Opened by **Details** on the product card or
 * on a shelf's product list (`showDetails`). Every figure comes from the live state, the
 * anomaly store, and `GET /promotions`. In development builds the anomalies section also
 * holds the anomaly simulator.
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
  const [simulating, setSimulating] = useState(false);
  // Each product opens with the simulator folded away.
  useEffect(() => setSimulating(false), [sku]);

  const product = sku ? live?.products.find((candidate) => candidate.sku === sku) : undefined;
  const anomalies = sku ? anomaliesOf(allAnomalies, sku) : [];
  const inPromotions = sku ? promotions.filter((promotion) => promotion.skus.includes(sku)) : [];
  const close = () => showDetails(null);
  const state = product ? stockState({ facings: product.facings, shelfQuantity: product.shelf_quantity }) : null;

  return (
    <Modal
      isOpen={sku !== null}
      onClose={close}
      size="2xl"
      placement="center"
      backdrop="blur"
      scrollBehavior="inside"
      classNames={{ base: "max-h-[min(720px,90dvh)]" }}
    >
      <ModalContent aria-label={sku ? t("inspector.detailsOf", { sku }) : undefined}>
        {sku ? (
          <>
            <ModalHeader className="flex flex-col gap-1 pb-2">
              <span className="flex flex-wrap items-center gap-2">
                <span className="text-xl font-semibold">{t("productDetails.title", { sku })}</span>
                {state ? (
                  <Chip size="sm" variant="flat" color={STATE_COLOR[state]}>
                    {t(`inspector.state.${state}`)}
                  </Chip>
                ) : null}
                {anomalies.length ? (
                  <Chip size="sm" variant="flat" color="danger">
                    {t("productDetails.anomalyCount", { count: anomalies.length })}
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
            <ModalBody className="gap-5 pb-2 text-sm">
              {product && live && state ? (
                <>
                  <Section title={t("productDetails.twin")}>
                    <StockTiles product={product} state={state} />
                  </Section>
                  <Section
                    title={t("productDetails.anomalies")}
                    count={anomalies.length}
                    action={
                      canSimulateAnomalies() ? (
                        <button
                          type="button"
                          className="anomaly-simulator-toggle"
                          aria-expanded={simulating}
                          title={t("anomaly.simulate.hint")}
                          onClick={() => setSimulating((open) => !open)}
                        >
                          <span className="anomaly-simulator-badge">{t("anomaly.simulate.dev")}</span>
                          {t("anomaly.simulate.toggle")}
                        </button>
                      ) : null
                    }
                  >
                    <AnomalyRows anomalies={anomalies} contextVersion={live.context_version} />
                    {simulating && canSimulateAnomalies() ? (
                      <AnomalySimulator
                        product={product}
                        contextVersion={live.context_version}
                        hasAnomalies={anomalies.length > 0}
                      />
                    ) : null}
                  </Section>
                </>
              ) : (
                <Chip color="danger" variant="flat">
                  {t("inspector.missing")}
                </Chip>
              )}
              <Section title={t("productDetails.promotions")} count={inPromotions.length}>
                {inPromotions.length ? (
                  <ul className="details-promotions">
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
                  <p className="details-empty">
                    <PromotionIcon className="h-4 w-4" />
                    {t("productDetails.noPromotions")}
                  </p>
                )}
              </Section>
            </ModalBody>
            <ModalFooter className="border-t border-line">
              {inPromotions.length ? (
                <Button
                  size="sm"
                  radius="sm"
                  variant="light"
                  className="mr-auto cursor-pointer"
                  onPress={() => {
                    setLens(LENS.Promotions);
                    openPanel(true);
                    close();
                  }}
                >
                  {t("productDetails.openPromotions")}
                </Button>
              ) : null}
              <Button size="sm" radius="sm" variant="light" className="cursor-pointer" onPress={close}>
                {t("productDetails.close")}
              </Button>
              {product ? (
                <Button
                  size="sm"
                  radius="sm"
                  className="cursor-pointer bg-accent font-semibold text-canvas data-[hover=true]:bg-accent-hover"
                  onPress={() => {
                    select(sku, ENTITY_TYPE.Product);
                    close();
                  }}
                >
                  {t("productDetails.showInStore")}
                </Button>
              ) : null}
            </ModalFooter>
          </>
        ) : null}
      </ModalContent>
    </Modal>
  );
}
