import { useCallback, useEffect, useState } from "react";
import { defaultClient } from "@/core/api/client";
import { readFailureOf, type ReadFailure } from "@/core/api/readFailure";
import { isDemoMode } from "@/core/twin/demoMode";
import { demoClient } from "@/fixtures/demo/commerce";
import type { PromotionsSummary } from "@/types/promotion.type";
import type { RevenueSummary } from "@/types/revenue.type";
import type { RetailTwinClient } from "@/types/api.type";
import { REVENUE_PERIOD, type RevenuePeriod } from "@/enums/commerce.enum";
import { READ_STATE, type ReadState } from "@/enums/ui.enum";
import { REVENUE_TODAY_REFRESH_MS } from "@/constants/app.constant";
import type { TimedRead } from "@/core/twin/kpiStrip";
import { storeFixture } from "@/fixtures/storeFixture";
import { useTwinStore } from "@/state/twin.store";

/**
 * The client the lenses read: the demo data under `?twin=demo`, otherwise apps/api.
 * A failed read never falls back to demo data; the lens says it failed.
 */
function commerceClient(): RetailTwinClient {
  return isDemoMode() ? demoClient : defaultClient;
}

/** The store the live twin reports, or the fixture's until it loads. */
function useStoreId() {
  return useTwinStore((state) => state.live?.store_id) ?? storeFixture.storeId;
}

/**
 * One read of a lens: the value once served (null until then, never a report of zeros), how
 * the read stands, why it failed, and `retry` to read again.
 */
export type LensRead<T> = {
  value: T | null;
  state: ReadState;
  failure: ReadFailure | null;
  retry: () => void;
};

type ReadCache = { reads: Map<string, Promise<unknown>>; results: Map<string, unknown> };
let caches = new WeakMap<RetailTwinClient, ReadCache>();

/** Forgets every lens read, so the next mount reads again: a fresh page, as tests need one. */
export function forgetLensReads() {
  caches = new WeakMap();
}

function cacheOf(client: RetailTwinClient): ReadCache {
  let cache = caches.get(client);
  if (!cache) {
    cache = { reads: new Map(), results: new Map() };
    caches.set(client, cache);
  }
  return cache;
}

/**
 * One read per key, shared by every mount, so switching lenses does not call the API again.
 * A failed read is dropped and stays on screen as a failure until Retry, or the next mount,
 * reads again. Without a client nothing is read.
 */
function useCachedRead<T>(
  client: RetailTwinClient | undefined,
  key: string,
  route: string,
  read: (client: RetailTwinClient) => Promise<T>,
): LensRead<T> {
  const cached = () => (client ? ((cacheOf(client).results.get(key) as T | undefined) ?? null) : null);
  const [value, setValue] = useState<T | null>(cached);
  const [failure, setFailure] = useState<ReadFailure | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    setFailure(null);
    if (!client) {
      setValue(null);
      return;
    }
    const { reads, results } = cacheOf(client);
    let cancelled = false;
    let pending = reads.get(key) as Promise<T> | undefined;
    if (!pending) {
      pending = read(client).then(
        (result) => {
          results.set(key, result);
          return result;
        },
        (error: unknown) => {
          reads.delete(key);
          throw error;
        },
      );
      reads.set(key, pending);
    }
    setValue((results.get(key) as T | undefined) ?? null);
    pending.then(
      (result) => !cancelled && setValue(result),
      (error: unknown) => !cancelled && setFailure(readFailureOf(error, route)),
    );
    return () => {
      cancelled = true;
    };
    // `read` and `route` follow from `client` and `key`.
  }, [client, key, attempt]);

  const retry = useCallback(() => {
    if (client) {
      cacheOf(client).reads.delete(key);
      cacheOf(client).results.delete(key);
    }
    setValue(null);
    setAttempt((count) => count + 1);
  }, [client, key]);

  const state = failure ? READ_STATE.Failed : value === null ? READ_STATE.Loading : READ_STATE.Ready;
  return { value: failure ? null : value, state, failure, retry };
}

/** `GET /revenue` for one window, read when the Revenue lens opens. */
export function useRevenue(
  period: RevenuePeriod,
  client: RetailTwinClient | undefined = commerceClient(),
): LensRead<RevenueSummary> {
  const storeId = useStoreId();
  return useCachedRead(client, `revenue:${storeId}:${period}`, "GET /revenue", (api) => api.revenue(period));
}

/**
 * Today's `GET /revenue` for the KPI strip, with the time it landed; null until it has, never
 * a report of zeros. Read again every `REVENUE_TODAY_REFRESH_MS`. A failed read keeps the last
 * good one, which the strip stops showing once it is stale (`revenueToday`), and does not
 * toast: the strip says so itself.
 */
export function useRevenueToday(client: RetailTwinClient | undefined = commerceClient()): TimedRead<RevenueSummary> | null {
  const storeId = useStoreId();
  const [state, setState] = useState<{ read: TimedRead<RevenueSummary> | null; checkedAt: number }>({ read: null, checkedAt: 0 });

  useEffect(() => {
    setState({ read: null, checkedAt: 0 });
    if (!client) return;
    let cancelled = false;
    const load = () =>
      client.revenue(REVENUE_PERIOD.Today).then(
        (value) => !cancelled && setState({ read: { value, readAt: Date.now() }, checkedAt: Date.now() }),
        // Keeps the last good read, and renders again so the strip sees it age.
        () => !cancelled && setState((prev) => ({ ...prev, checkedAt: Date.now() })),
      );
    void load();
    const timer = window.setInterval(load, REVENUE_TODAY_REFRESH_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [client, storeId]);

  return state.read;
}

/** `GET /promotions`, read when the Promotions lens opens. Read only. */
export function usePromotions(client: RetailTwinClient | undefined = commerceClient()): LensRead<PromotionsSummary> {
  const storeId = useStoreId();
  return useCachedRead(client, `promotions:${storeId}`, "GET /promotions", (api) => api.promotions());
}
