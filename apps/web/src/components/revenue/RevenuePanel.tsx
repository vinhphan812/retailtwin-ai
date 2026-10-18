import { useState } from "react";
import { useTranslation } from "react-i18next";
import { MetricTile } from "@/components/commerce/MetricTile";
import { Segmented } from "@/components/commerce/Segmented";
import { ReadEmptyCard, ReadFailureCard, ReadSource, ReadingNotice } from "@/components/common/ReadStatus";
import { formatWindow } from "@/core/commerce/revenueWindow";
import { relativeChange } from "@/core/utils/format";
import { BUCKET_SIZE, REVENUE_PERIOD, REVENUE_PERIODS, type RevenuePeriod } from "@/enums/commerce.enum";
import { useRevenue } from "@/hooks/commerce.hook";
import { format as f } from "@/core/utils/format";
import type { RevenueSummary } from "@/types/revenue.type";
import { CategoryShare } from "./CategoryShare";
import { RevenueChart } from "./RevenueChart";
import { SkuList } from "./SkuList";

const ROUTE = "GET /revenue";

/** A section of the report apps/api does not serve: says so, rather than drawing it empty. */
function NotServed() {
  const { t } = useTranslation();
  return <p className="read-not-served">{t("revenue.sectionNotServed")}</p>;
}

/** The report of one window, as served: what it covers and where it comes from, then its figures. */
function Report({ summary, period }: { summary: RevenueSummary; period: RevenuePeriod }) {
  const { t } = useTranslation();
  const { previous } = summary;
  const change = (now: number, before: number | undefined) => (before === undefined ? undefined : relativeChange(now, before));

  return (
    <>
      <p className="read-evidence">
        <ReadSource />
        <span>{summary.store_id}</span>
        <span>{formatWindow(summary.start, summary.end)}</span>
        <span>{summary.currency}</span>
      </p>
      <div className="metric-grid">
        <MetricTile wide label={t("revenue.revenue")} value={summary.revenue} format={f.money} change={change(summary.revenue, previous?.revenue)} />
        <MetricTile
          label={t("revenue.transactions")}
          value={summary.transactions}
          format={f.count}
          change={change(summary.transactions, previous?.transactions)}
        />
        <MetricTile
          label={t("revenue.averageBasket")}
          value={summary.average_basket}
          format={f.money}
          change={change(summary.average_basket, previous?.average_basket)}
        />
        <MetricTile label={t("revenue.marginRate")} value={summary.margin_rate} format={f.percent} />
        <MetricTile
          tone="alert"
          label={t("revenue.lostToStockout")}
          hint={t("revenue.lostHint")}
          value={summary.lost_to_stockout}
          format={f.money}
        />
      </div>

      <section>
        <h2 className="activity-section-title">
          {t(summary.bucket_size === BUCKET_SIZE.Hour ? "revenue.byHour" : "revenue.byDay")}
        </h2>
        <RevenueChart key={period} summary={summary} />
      </section>

      <section>
        <h2 className="activity-section-title">{t("revenue.byCategory")}</h2>
        {summary.categories ? <CategoryShare categories={summary.categories} /> : <NotServed />}
      </section>

      <section>
        <h2 className="activity-section-title">
          {t("revenue.topSkus")}
          {summary.top_skus ? <span className="activity-count">{summary.top_skus.length}</span> : null}
        </h2>
        {summary.top_skus ? <SkuList skus={summary.top_skus} label={t("revenue.topSkus")} /> : <NotServed />}
      </section>

      <section>
        <h2 className="activity-section-title">
          {t("revenue.slowSkus")}
          {summary.slow_skus ? <span className="activity-count">{summary.slow_skus.length}</span> : null}
        </h2>
        {summary.slow_skus ? <SkuList skus={summary.slow_skus} label={t("revenue.slowSkus")} /> : <NotServed />}
      </section>
    </>
  );
}

/**
 * Revenue tab of the side panel: headline figures, the sales curve, categories, and best and
 * worst sellers, of the window picked. Until `GET /revenue` answers it says it is reading; when
 * it fails, or serves no sale, a card says so with a retry, in place of figures of 0.
 */
export function RevenuePanel() {
  const { t } = useTranslation();
  const [period, setPeriod] = useState<RevenuePeriod>(REVENUE_PERIOD.Today);
  const { value: summary, failure, retry } = useRevenue(period);

  return (
    <div className="commerce">
      <Segmented
        label={t("revenue.period.label")}
        layoutId="revenue-period"
        value={period}
        onChange={setPeriod}
        options={REVENUE_PERIODS.map((value) => ({ value, label: t(`revenue.period.${value}`) }))}
      />
      {failure ? (
        <ReadFailureCard title={t("revenue.failed")} failure={failure} onRetry={retry} />
      ) : !summary ? (
        <ReadingNotice route={ROUTE} />
      ) : summary.transactions === 0 && summary.revenue === 0 ? (
        <ReadEmptyCard
          title={t("revenue.emptyTitle")}
          text={t("revenue.emptyText", { store: summary.store_id, window: formatWindow(summary.start, summary.end) })}
          onRetry={retry}
        />
      ) : (
        <Report summary={summary} period={period} />
      )}
    </div>
  );
}
