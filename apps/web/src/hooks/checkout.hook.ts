import { useEffect, useState } from "react";
import { defaultClient } from "@/core/api/client";
import { isDemoMode } from "@/core/twin/demoMode";
import { demoCheckout, demoTransactions } from "@/fixtures/demo/checkouts";
import type { CheckoutResponse, CheckoutSummary, CheckoutTransaction } from "@/types/checkout.type";
import { notify } from "@/core/notify";
import i18n from "@/i18n";

/**
 * The client the checkout hooks read: the demo data under `?twin=demo`, otherwise apps/api.
 */
function checkoutClient() {
  return isDemoMode() ? null : defaultClient;
}

/**
 * Today's figures of one checkout, or null while there are none.
 * In demo mode (`?twin=demo`), returns demo figures. In production, calls `GET /checkouts/{checkoutId}`.
 */
export function useCheckoutSummary(checkoutId: string): CheckoutSummary | null {
  const client = checkoutClient();
  const [summary, setSummary] = useState<CheckoutSummary | null>(null);

  useEffect(() => {
    // Demo mode: return demo data immediately
    if (isDemoMode()) {
      setSummary(demoCheckout(checkoutId));
      return;
    }

    // Live mode: fetch from API
    if (!client || !checkoutId) {
      setSummary(null);
      return;
    }

    let cancelled = false;

    client
      .checkout(checkoutId)
      .then((response: CheckoutResponse) => {
        if (!cancelled) {
          setSummary(response.summary);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          notify.error(i18n.t("checkout.loadFailed"), error);
          setSummary(null);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [client, checkoutId]);

  return isDemoMode() ? demoCheckout(checkoutId) : summary;
}

/**
 * Today's sales at one checkout, newest first, read only while `enabled` (the dialog is open).
 * In demo mode (`?twin=demo`), returns demo transactions. In production, calls `GET /checkouts/{checkoutId}`.
 */
export function useCheckoutTransactions(checkoutId: string, enabled: boolean): CheckoutTransaction[] {
  const client = checkoutClient();
  const [transactions, setTransactions] = useState<CheckoutTransaction[]>([]);

  useEffect(() => {
    // Demo mode: return demo data
    if (isDemoMode()) {
      setTransactions(enabled ? demoTransactions(checkoutId) : []);
      return;
    }

    // Live mode: fetch from API
    if (!enabled || !client || !checkoutId) {
      setTransactions([]);
      return;
    }

    let cancelled = false;

    client
      .checkout(checkoutId)
      .then((response: CheckoutResponse) => {
        if (!cancelled) {
          setTransactions(response.transactions);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          notify.error(i18n.t("checkout.loadFailed"), error);
          setTransactions([]);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [client, checkoutId, enabled]);

  return isDemoMode() && enabled ? demoTransactions(checkoutId) : transactions;
}
