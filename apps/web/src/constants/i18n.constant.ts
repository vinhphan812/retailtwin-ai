/** Locale for numbers, dates, and the UI kit's built-in labels. The app is English only. */
export const LOCALE = "en-US";

/** Currency money is shown in. */
export const CURRENCY = "USD";

/**
 * IANA time zone of the store's business day: where "today" starts and ends, and where a day
 * of the 7- and 30-day windows starts. UTC by default, as apps/api cuts its revenue buckets on
 * UTC hours and days (`TIMESTAMP_TRUNC`). TODO(BE): serve the store's own time zone.
 */
export const STORE_TIME_ZONE: string = import.meta.env.VITE_STORE_TIME_ZONE || "UTC";
