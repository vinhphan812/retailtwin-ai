import { useTranslation } from "react-i18next";
import type { AiImpact, ImpactRow } from "@/core/twin/aiImpact";
import { useImpactStore } from "@/state/impact.store";
import { formatKpiValue, formatNumber } from "./CandidatePanel";

/** One KPI as "before → after" and its move, each value as served. */
export function ImpactRowView({ row }: { row: ImpactRow }) {
  const { t } = useTranslation();
  const delta = formatNumber(row.delta, true);
  return (
    <li className="impact-row">
      <span className="impact-kpi">{t(`proposal.kpi.${row.name}`, { defaultValue: row.name })}</span>
      <span className="impact-values">
        <span className="impact-before">{formatKpiValue(row.before.value, row.before.unit)}</span>
        <span aria-hidden="true">→</span>
        <span className="impact-after">{formatKpiValue(row.after.value, row.after.unit)}</span>
      </span>
      <span
        className="impact-delta"
        data-trend={row.trend}
        aria-label={t("impact.delta", { delta, trend: t(`proposal.compare.trend.${row.trend}`) })}
      >
        {delta}
      </span>
    </li>
  );
}

/** Opens the comparison of the run's candidates, as served at the approval. */
export function CompareButton() {
  const { t } = useTranslation();
  const setComparing = useImpactStore((state) => state.setComparing);
  return (
    <button type="button" className="impact-compare" onClick={() => setComparing(true)}>
      {t("impact.compare")}
    </button>
  );
}

/**
 * The AI Impact of an executed approval: each KPI of the baseline (before) next to the
 * accepted candidate's (after), with the move between them. Every value is the evaluator's.
 */
export function AiImpactCard({ impact }: { impact: AiImpact }) {
  const { t } = useTranslation();
  return (
    <div className="impact-card" data-testid="ai-impact" role="region" aria-label={t("impact.title")}>
      <div className="impact-head">
        <span className="impact-title">{t("impact.title")}</span>
        <span className="impact-plan">{t("impact.plan", { id: impact.candidate_id })}</span>
      </div>
      <div className="impact-columns" aria-hidden="true">
        <span>{t("impact.before")}</span>
        <span>{t("impact.after")}</span>
      </div>
      <ul className="impact-rows">
        {impact.rows.map((row) => (
          <ImpactRowView key={row.name} row={row} />
        ))}
      </ul>
      <div className="impact-foot">
        <span className="impact-note">{t("impact.note", { version: impact.evaluator_version })}</span>
        <CompareButton />
      </div>
    </div>
  );
}
