import { useEffect, useState } from "react";
import i18n from "@/i18n";
import { defaultClient } from "@/core/api/client";
import { isDemoMode } from "@/core/twin/demoMode";
import { demoClient } from "@/fixtures/demo/commerce";
import { demoCheckout, demoTransactions } from "@/fixtures/demo/checkouts";
import { notify } from "@/core/notify";
import type { CheckoutResponse, CheckoutSummary, CheckoutTransaction } from "@/types/checkout.type";
import type { RetailTwinClient } from "@/types/api.type";

/**
 * The client the lenses read: the demo data under `?twin=demo`, otherwise apps/api.
 * A failed read never falls back to demo data; the lens keeps its empty report.
 */
function checkoutClient(): RetailTwinClient {
  return isDemoMode() ? demoClient : defaultClient;
}

/**
 * Today's figures of one checkout, or null while there are none.
 * In production mode, reads from `GET /checkouts/{checkoutId}`.
 * Under `?twin=demo`, shows demo figures.
 */
export function useCheckoutSummary(checkoutId: string): CheckoutSummary | null {
  const client = checkoutClient();
  const [summary, setSummary] = useState<CheckoutSummary | null>(() => {
    if (isDemoMode()) return demoCheckout(checkoutId);
    return null;
  });
  const [loading, setLoading] = useState(!isDemoMode());

  useEffect(() => {
    if (isDemoMode()) {
      setSummary(demoCheckout(checkoutId));
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);

    client.checkout(checkoutId)
      .then((response: CheckoutResponse) => {
        if (!cancelled) setSummary(response.summary);
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          notify.error(i18n.t("checkout.loadFailed"), error);
          setSummary(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [client, checkoutId]);

  return loading ? null : summary;
}

/**
 * Today's sales at one checkout, newest first, read only while `enabled` (the dialog is open).
 * In production mode, reads from `GET /checkouts/{checkoutId}`.
 * Under `?twin=demo`, shows demo sales.
 */
export function useCheckoutTransactions(checkoutId: string, enabled: boolean): CheckoutTransaction[] {
  const client = checkoutClient();
  const [transactions, setTransactions] = useState<CheckoutTransaction[]>(() => {
    if (isDemoMode() && enabled) return demoTransactions(checkoutId);
    return [];
  });

  useEffect(() => {
    if (!enabled) {
      setTransactions([]);
      return;
    }

    if (isDemoMode()) {
      setTransactions(demoTransactions(checkoutId));
      return;
    }

    let cancelled = false;

    client.checkout(checkoutId)
      .then((response: CheckoutResponse) => {
        if (!cancelled) setTransactions(response.transactions);
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          notify.error(i18n.t("checkout.transactionsLoadFailed"), error);
          setTransactions([]);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [client, checkoutId, enabled]);

  return transactions;
}
