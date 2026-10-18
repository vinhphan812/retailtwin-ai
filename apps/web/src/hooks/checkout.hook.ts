import { useEffect, useState } from "react";
import { isDemoMode } from "@/core/twin/demoMode";
import { defaultClient } from "@/core/api/client";
import { demoCheckout, demoTransactions } from "@/fixtures/demo/checkouts";
import type { CheckoutSummary, CheckoutTransaction } from "@/types/checkout.type";

/**
 * Today's figures of one checkout, or null while there are none.
 * In demo mode (`?twin=demo`), returns demo data. Otherwise calls the API.
 */
export function useCheckoutSummary(checkoutId: string): CheckoutSummary | null {
  const [summary, setSummary] = useState<CheckoutSummary | null>(null);

  useEffect(() => {
    if (isDemoMode()) {
      setSummary(demoCheckout(checkoutId));
      return;
    }

    defaultClient
      .checkout(checkoutId)
      .then((response) => setSummary(response.summary))
      .catch(() => setSummary(null));
  }, [checkoutId]);

  return summary;
}

/**
 * Today's sales at one checkout, newest first, read only while `enabled` (the dialog is
 * open). In demo mode (`?twin=demo`), returns demo sales. Otherwise calls the API.
 */
export function useCheckoutTransactions(checkoutId: string, enabled: boolean): CheckoutTransaction[] {
  const [transactions, setTransactions] = useState<CheckoutTransaction[]>([]);

  useEffect(() => {
    if (!enabled) {
      setTransactions([]);
      return;
    }

    if (isDemoMode()) {
      setTransactions(demoTransactions(checkoutId));
      return;
    }

    defaultClient
      .checkout(checkoutId)
      .then((response) => setTransactions(response.transactions))
      .catch(() => setTransactions([]));
  }, [checkoutId, enabled]);

  return transactions;
}
