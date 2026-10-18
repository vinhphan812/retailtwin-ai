import { useEffect, useState } from "react";
import { defaultClient } from "@/core/api/client";
import { isDemoMode } from "@/core/twin/demoMode";
import { demoCheckout, demoTransactions } from "@/fixtures/demo/checkouts";
import type { CheckoutSummary, CheckoutTransaction } from "@/types/checkout.type";
import type { RetailTwinClient } from "@/types/api.type";

/** Client for checkout data: demo data under `?twin=demo`, otherwise apps/api. */
function checkoutClient(): RetailTwinClient {
  return isDemoMode() ? (demoClient as unknown as RetailTwinClient) : defaultClient;
}

const demoClient = {
  checkout: (checkoutId: string) => Promise.resolve(demoCheckout(checkoutId)),
};

/**
 * Today's figures of one checkout, or null while there are none.
 * Returns live data from apps/api via the RetailTwinClient.
 */
export function useCheckoutSummary(checkoutId: string): CheckoutSummary | null {
  const [summary, setSummary] = useState<CheckoutSummary | null>(null);
  const client = checkoutClient();

  useEffect(() => {
    client
      .checkout(checkoutId)
      .then((response) => setSummary(response.summary))
      .catch(() => setSummary(null));
  }, [client, checkoutId]);

  return summary;
}

/**
 * Today's sales at one checkout, newest first, read only while `enabled` (the dialog is
 * open). Returns live data via RetailTwinClient.
 */
export function useCheckoutTransactions(checkoutId: string, enabled: boolean): CheckoutTransaction[] {
  const [transactions, setTransactions] = useState<CheckoutTransaction[]>([]);
  const client = checkoutClient();

  useEffect(() => {
    if (!enabled) {
      setTransactions([]);
      return;
    }
    client
      .checkout(checkoutId)
      .then((response) => setTransactions(response.transactions))
      .catch(() => setTransactions([]));
  }, [client, checkoutId, enabled]);

  return transactions;
}
