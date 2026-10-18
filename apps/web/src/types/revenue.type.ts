import type { BucketSize, RevenuePeriod } from "@/enums/commerce.enum";

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
  /** 0..1 */
  margin_rate: number;
};

/**
 * Internal summary shape used by all FE consumers (hooks, store, fixtures).
 * period is always the UI-facing RevenuePeriod value ("today" | "7d" | "30d").
 */
export type RevenueSummary = RevenueTotals & {
  store_id: string;
  period: RevenuePeriod;
  /** Estimated sales lost while a product was out of stock on the shelf. */
  lost_to_stockout: number;
  previous: RevenueTotals;
  bucket_size: BucketSize;
  buckets: RevenueBucket[];
  categories: CategoryRevenue[];
  top_skus: SkuRevenue[];
  /** Low sellers that still hold shelf space. */
  slow_skus: SkuRevenue[];
};

/** Shape returned directly by `GET /revenue` in apps/api (schemas.py). */
export type RevenueResponse = {
  store_id: string;
  period: "hourly" | "daily" | "weekly" | "monthly";
  start: string;
  end: string;
  total_revenue: number;
  total_transactions: number;
  total_items_sold: number;
  avg_transaction_value: number;
  currency: "USD";
  buckets: RevenueBucketResponse[];
};

export type RevenueBucketResponse = {
  timestamp: string;
  revenue: number;
  transactions: number;
  items_sold: number;
};
