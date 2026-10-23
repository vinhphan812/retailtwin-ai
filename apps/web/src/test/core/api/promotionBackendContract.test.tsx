// @vitest-environment jsdom
import { cleanup, render, screen, within } from "@testing-library/react";
import { MotionGlobalConfig } from "framer-motion";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createClient } from "@/core/api/client";
import { PromotionCard } from "@/components/promotions/PromotionCard";
import { ProductDetailsDialog } from "@/components/twin/ProductDetailsDialog";
import { TWIN_STATUS } from "@/enums/twin.enum";
import { LENS } from "@/enums/ui.enum";
import { useAnomalyStore } from "@/state/anomaly.store";
import { usePanelStore } from "@/state/panel.store";
import { useTwinStore } from "@/state/twin.store";
import { useUiStore } from "@/state/ui.store";
import { stockedStoreState } from "@/test/stockedState";

MotionGlobalConfig.skipAnimations = true;

const state = stockedStoreState();

let mockPromotionsResult: any = { store_id: "store-001", revenue: 0, incremental_revenue: 0, discount_cost: 0, promotions: [] };

vi.mock("@/hooks/checkout.hook", () => ({ useCheckoutSummary: () => null, useCheckoutTransactions: () => [] }));
vi.mock("@/hooks/commerce.hook", () => ({
  usePromotions: () => mockPromotionsResult,
  useRevenue: () => ({ revenue: 0, transactions: 0 }),
  useRevenueToday: () => null,
}));

beforeEach(() => {
  useTwinStore.setState({ live: state, issues: [], status: TWIN_STATUS.Ready });
  useAnomalyStore.setState({ anomalies: [] });
  useUiStore.setState({ lens: LENS.Operations, detailsSku: null, focusedPromotionId: null });
  useUiStore.getState().select(null);
  usePanelStore.setState({ open: false });
});

afterEach(cleanup);

describe("promotion backend contract & rendered label integration", () => {
  it("normalizes real backend buy_one_get_one payload and renders '1 free' in both component views", async () => {
    const realBackendPayload = {
      store_id: "store-001",
      revenue: 1250.0,
      incremental_revenue: 320.0,
      discount_cost: 150.0,
      promotions: [
        {
          promotion_id: "promo-be-1",
          name: "Organic Milk 2-for-1 BOGO",
          promotion_type: "buy_one_get_one",
          status: "active",
          store_id: "store-001",
          sku: "P001",
          category: "Dairy",
          discount_value: 1,
          conditions: "Buy 1 get 1 free",
          start_time: "2026-10-01T00:00:00Z",
          end_time: "2026-10-31T23:59:59Z",
          redemption_count: 42,
          revenue: 1250.0,
          incremental_revenue: 320.0,
          discount_cost: 150.0,
        },
      ],
    };

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => realBackendPayload,
    } as Response);

    const client = createClient("http://localhost:8000", mockFetch);
    const summary = await client.promotions();
    mockPromotionsResult = summary;

    expect(summary.promotions).toHaveLength(1);
    const promo = summary.promotions[0];
    expect(promo.kind).toBe("buy_x_get_y");
    expect(promo.value).toBe(1);

    // 1. Render PromotionCard
    const { unmount } = render(<PromotionCard promotion={promo} />);
    expect(screen.getByText("Organic Milk 2-for-1 BOGO")).toBeTruthy();
    expect(screen.getByText("1 free")).toBeTruthy();
    expect(document.body.textContent).not.toContain("promotions.kind.buy_one_get_one");
    unmount();

    // 2. Render ProductDetailsDialog
    useUiStore.getState().showDetails("P001");
    render(<ProductDetailsDialog />);

    const dialog = await screen.findByRole("dialog");
    const promotionsRegion = within(dialog).getByRole("region", { name: "Promotions" });

    expect(promotionsRegion.textContent).toContain("Organic Milk 2-for-1 BOGO");
    expect(promotionsRegion.textContent).toContain("1 free");
    expect(promotionsRegion.textContent).not.toContain("promotions.kind.buy_one_get_one");
  });
});
