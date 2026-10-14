import { Chip } from "@heroui/react";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { alertCategory, alertStep, sortAlerts } from "@/core/anomaly/alerts";
import { format } from "@/core/utils/format";
import { ALERT_CATEGORY, ALERT_STEPS } from "@/enums/anomaly.enum";
import { useActiveState } from "@/hooks/activeTwin.hook";
import { useAnomalyStore } from "@/state/anomaly.store";
import { useRunStore } from "@/state/run.store";
import { selectedProductId, useUiStore } from "@/state/ui.store";

const CATEGORY_COLOR = {
  [ALERT_CATEGORY.Alert]: "danger",
  [ALERT_CATEGORY.Opportunity]: "success",
} as const;

/**
 * Open alerts and opportunities, worst first, each with how far its agent run has got.
 * They appear as soon as the anomaly store has them, with no prompt. Picking one selects
 * its product, flies the camera there, and narrows the timeline to its run. When a read of the
 * anomalies fails it says so and keeps the last list, which may be out of date.
 */
export function AlertsSection() {
  const { t } = useTranslation();
  const anomalies = useAnomalyStore((state) => state.anomalies);
  const readError = useAnomalyStore((state) => state.readError);
  const activity = useRunStore((state) => state.activity);
  const active = useActiveState();
  const selected = useUiStore(selectedProductId);
  const focusedCorrelationId = useUiStore((state) => state.focusedCorrelationId);
  const focusAlert = useUiStore((state) => state.focusAlert);
  const alerts = useMemo(() => sortAlerts(anomalies), [anomalies]);
  const inTwin = useMemo(() => new Set(active?.products.map((product) => product.sku)), [active]);

  return (
    <section className="activity-section alerts-section">
      <div className="activity-section-head">
        <h2 className="activity-section-title">
          {t("alerts.section")}
          <span className="activity-count">{alerts.length}</span>
        </h2>
      </div>
      {readError ? (
        <p className="alerts-error" role="status">
          {t(alerts.length ? "alerts.readFailedKept" : "alerts.readFailed", { error: readError })}
        </p>
      ) : null}
      {alerts.length ? (
        <ul className="alerts-list" aria-label={t("alerts.list")}>
          {alerts.map((anomaly) => {
            const category = alertCategory(anomaly);
            const step = alertStep(anomaly, activity);
            const stepIndex = ALERT_STEPS.indexOf(step);
            const missing = !inTwin.has(anomaly.sku);
            const pressed = selected === anomaly.sku && focusedCorrelationId === anomaly.correlation_id;
            return (
              <li key={anomaly.anomaly_id}>
                <button
                  type="button"
                  className="alert-item"
                  data-severity={anomaly.severity}
                  data-category={category}
                  disabled={missing}
                  aria-pressed={pressed}
                  aria-label={t("alerts.select", {
                    category: t(`alerts.category.${category}`),
                    kind: t(`anomaly.kind.${anomaly.kind}`),
                    sku: anomaly.sku,
                  })}
                  onClick={() => focusAlert(anomaly.correlation_id, anomaly.sku)}
                >
                  <span className="alert-head">
                    <Chip size="sm" variant="flat" color={CATEGORY_COLOR[category]}>
                      {t(`alerts.category.${category}`)}
                    </Chip>
                    <span className="alert-title">{t(`anomaly.kind.${anomaly.kind}`)}</span>
                    <span className="alert-severity">{t(`anomaly.severity.${anomaly.severity}`)}</span>
                  </span>
                  <span className="alert-meta">
                    <span>{t("alerts.where", { sku: anomaly.sku, shelf: anomaly.shelf_id })}</span>
                    <time dateTime={anomaly.detected_at}>
                      {t("anomaly.detected", { time: format.hour(anomaly.detected_at) })}
                    </time>
                  </span>
                  {missing ? (
                    <span className="alert-missing">{t("alerts.notInTwin")}</span>
                  ) : (
                    <span className="alert-lifecycle">
                      <span className="alert-steps" aria-hidden="true">
                        {ALERT_STEPS.map((each, index) => (
                          <span key={each} className="alert-step" data-done={index <= stepIndex} />
                        ))}
                      </span>
                      <span className="alert-step-label">
                        {t("alerts.step", { step: t(`alerts.steps.${step}`) })}
                      </span>
                    </span>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      ) : readError ? null : (
        <p className="alerts-empty">{t("alerts.empty")}</p>
      )}
    </section>
  );
}
