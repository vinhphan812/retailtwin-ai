import type { CheckoutSummary, CheckoutTransaction } from "@/types/checkout.type";

/**
 * Today's figures of one checkout, or null while there are none.
 * TODO(BE): apps/api serves no checkouts yet; read them here once the schema
 * (`CheckoutSummary`) is agreed. Until then the checkout card says so.
 */
export function useCheckoutSummary(_checkoutId: string): CheckoutSummary | null {
  return null;
}

/**
 * Today's sales at one checkout, newest first, read only while `enabled` (the dialog is
 * open). TODO(BE): apps/api serves no checkout transactions yet (`CheckoutTransaction`).
 */
export function useCheckoutTransactions(_checkoutId: string, _enabled: boolean): CheckoutTransaction[] {
  return [];
}
