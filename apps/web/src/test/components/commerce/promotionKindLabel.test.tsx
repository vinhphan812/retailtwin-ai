// @vitest-environment jsdom
import { cleanup, render, screen, within } from "@testing-library/react";
import { MotionGlobalConfig } from "framer-motion";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PromotionCard } from "@/components/promotions/PromotionCard";
import { ProductDetailsDialog } from "@/components/twin/ProductDetailsDialog";
import { PROMOTION_KIND, PROMOTION_STATUS } from "@/enums/commerce.enum";
import { TWIN_STATUS } from "@/enums/twin.enum";
import { LENS } from "@/enums/ui.enum";
import { useAnomalyStore } from "@/state/anomaly.store";
import { usePanelStore } from "@/state/panel.store";
import { useTwinStore } from "@/state/twin.store";
import { useUiStore } from "@/state/ui.store";
import { stockedStoreState } from "@/test/stockedState";
import type { Promotion } from "@/types/promotion.type";

/**
 * The dynamic-key consumers of `promotions.kind.<kind>`.
 *
 * `PromotionCard` and `ProductDetailsDialog` both read the label with
 * `t(\`promotions.kind.${promotion.kind}\`, { value })`, so the copy is only right if the
 * mapped `kind` has a matching translation key. A `BuyXGetY` promotion must render the
 * `buy_x_get_y` copy ("1 free"); a loyalty multiplier must not fall back to the percent-off
 * copy; an unrecognised backend type must not be silently rendered as a percentage either.
 */

const BOGO: Promotion = {
  id: "promo-bogo",
  name: "Two for one on pasta",
  status: PROMOTION_STATUS.Active,
  kind: PROMOTION_KIND.BuyXGetY,
  value: 1,
  starts_at: "2026-10-06T00:00:00Z",
  ends_at: "2026-10-13T00:00:00Z",
  skus: ["P004"],
  revenue: 0,
  incremental_revenue: 0,
  discount_cost: null,
};

const LOYALTY: Promotion = {
  id: "promo-loyalty",
  name: "Double loyalty points",
  status: PROMOTION_STATUS.Active,
  kind: PROMOTION_KIND.LoyaltyMultiplier,
  value: 2.5,
  starts_at: "2026-10-06T00:00:00Z",
  ends_at: "2026-10-13T00:00:00Z",
  skus: ["P004"],
  revenue: 0,
  incremental_revenue: 0,
  discount_cost: null,
};

const UNKNOWN: Promotion = {
  id: "promo-unknown",
  name: "Mystery promo",
  status: PROMOTION_STATUS.Active,
  kind: PROMOTION_KIND.Unknown,
  value: null,
  starts_at: "2026-10-06T00:00:00Z",
  ends_at: "2026-10-13T00:00:00Z",
  skus: ["P004"],
  revenue: 0,
  incremental_revenue: 0,
  discount_cost: null,
};

vi.mock("@/hooks/checkout.hook", () => ({ useCheckoutSummary: () => null, useCheckoutTransactions: () => [] }));
vi.mock("@/hooks/commerce.hook", async () => {
  const { PROMOTION_KIND, PROMOTION_STATUS } = await import("@/enums/commerce.enum");
  const base = {
    status: PROMOTION_STATUS.Active,
    starts_at: "2026-10-06T00:00:00Z",
    ends_at: "2026-10-13T00:00:00Z",
    skus: ["P004"],
    revenue: 0,
    incremental_revenue: 0,
    discount_cost: null,
  };
  const promotions = [
    { ...base, id: "promo-bogo", name: "Two for one on pasta", kind: PROMOTION_KIND.BuyXGetY, value: 1 },
    { ...base, id: "promo-loyalty", name: "Double loyalty points", kind: PROMOTION_KIND.LoyaltyMultiplier, value: 2.5 },
    { ...base, id: "promo-unknown", name: "Mystery promo", kind: PROMOTION_KIND.Unknown, value: null },
  ];
  return {
    usePromotions: () => ({
      store_id: "store-001",
      revenue: 0,
      incremental_revenue: 0,
      discount_cost: 0,
      promotions,
    }),
  };
});

MotionGlobalConfig.skipAnimations = true;

const state = stockedStoreState();

beforeEach(() => {
  useTwinStore.setState({ live: state, issues: [], status: TWIN_STATUS.Ready });
  useAnomalyStore.setState({ anomalies: [] });
  useUiStore.setState({ lens: LENS.Operations, detailsSku: null, focusedPromotionId: null });
  useUiStore.getState().select(null);
  usePanelStore.setState({ open: false });
});

afterEach(cleanup);

describe("promotion kind label on the card", () => {
  it("renders the buy_x_get_y copy for a BOGO promotion", () => {
    render(<PromotionCard promotion={BOGO} />);

    expect(screen.getByText("1 free")).toBeTruthy();
    expect(document.body.textContent).not.toContain("% off");
  });

  it("renders the loyalty multiplier copy instead of the percent-off fallback", () => {
    render(<PromotionCard promotion={LOYALTY} />);

    expect(screen.getByText("2.5x multiplier")).toBeTruthy();
    // The silent fallback this PR removes rendered a percentage here.
    expect(document.body.textContent).not.toContain("% off");
  });

  it("renders the unsupported copy for an unknown kind instead of a percentage", () => {
    render(<PromotionCard promotion={UNKNOWN} />);

    expect(screen.getByText("Unsupported promotion type")).toBeTruthy();
    expect(document.body.textContent).not.toContain("% off");
  });
});

describe("promotion kind label in the product details dialog", () => {
  it("renders every promotion's kind label in the dialog's promotions section", async () => {
    useUiStore.getState().showDetails("P004");
    render(<ProductDetailsDialog />);

    const dialog = await screen.findByRole("dialog");
    const promotions = within(dialog).getByRole("region", { name: "Promotions" });

    expect(promotions.textContent).toContain("Two for one on pasta");
    expect(promotions.textContent).toContain("1 free");
    expect(promotions.textContent).toContain("Double loyalty points");
    expect(promotions.textContent).toContain("2.5x multiplier");
    expect(promotions.textContent).toContain("Mystery promo");
    expect(promotions.textContent).toContain("Unsupported promotion type");

    // None of them may fall back to the percent-off copy.
    expect(promotions.textContent).not.toContain("% off");
  });
});
