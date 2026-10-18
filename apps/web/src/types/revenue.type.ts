import type { BucketSize, RevenueGrain, RevenuePeriod } from "@/enums/commerce.enum";

/** Revenue of one chart bar: an hour of today, or a day of a longer window. */
export type RevenueBucket = {
  /** ISO start of the bucket. */
  start: string;
  revenue: number;
};

export type SkuRevenue = {
  sku: string;
  name: string;
  revenue: number;
  units: number;
  facings: number;
};

export type CategoryRevenue = {
  /** A `scene.stock` category key, such as `packaged`. */
  category: string;
  revenue: number;
};

/** Headline figures of a window; `previous` holds the window before it, for the change badges. */
export type RevenueTotals = {
  revenue: number;
  transactions: number;
  average_basket: number;
  /** 0..1; null when not served (apps/api serves no margin yet). */
  margin_rate: number | null;
};

/**
 * One window of the Revenue lens, as the FE shows it: `GET /revenue` mapped by
 * `toRevenueSummary`, or the demo's report. Money is in `currency`. A figure apps/api does not
 * serve is null and shows as not served, never as 0.
 */
export type RevenueSummary = RevenueTotals & {
  store_id: string;
  /** The lens window, never sent to apps/api as is (`revenueQuery`). */
  period: RevenuePeriod;
  /** The window read: its first moment and its end, ISO. */
  start: string;
  end: string;
  currency: string;
  /** Units sold in the window; null when not served. */
  items_sold: number | null;
  /** Estimated sales lost while a product was out of stock on the shelf; null when not served. */
  lost_to_stockout: number | null;
  /** The window before, for the change badges; null when not served. */
  previous: RevenueTotals | null;
  bucket_size: BucketSize;
  buckets: RevenueBucket[];
  /** Null when not served. */
  categories: CategoryRevenue[] | null;
  /** Null when not served. */
  top_skus: SkuRevenue[] | null;
  /** Low sellers that still hold shelf space; null when not served. */
  slow_skus: SkuRevenue[] | null;
};

/** One bucket of `GET /revenue`, as apps/api serves it (`schemas.py` `RevenueBucket`). */
export type RevenueResponseBucket = {
  /** ISO start of the bucket, cut on UTC hours or days. */
  timestamp: string;
  revenue: number;
  transactions: number;
  items_sold: number;
};

/** `GET /revenue?period=hourly|daily&start&end`, as apps/api serves it (`schemas.py` `RevenueResponse`). */
export type RevenueResponse = {
  store_id: string;
  period: RevenueGrain;
  start: string;
  end: string;
  total_revenue: number;
  total_transactions: number;
  total_items_sold: number;
  avg_transaction_value: number;
  currency: string;
  /** Only the buckets with sales, oldest first. */
  buckets: RevenueResponseBucket[];
};
