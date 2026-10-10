// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EntityInspector } from "@/components/twin/EntityInspector";
import { ProductDetailsDialog } from "@/components/twin/ProductDetailsDialog";
import { ANOMALY_KIND, ANOMALY_SEVERITY } from "@/enums/anomaly.enum";
import { ENTITY_TYPE } from "@/enums/scene.enum";
import { TWIN_STATUS } from "@/enums/twin.enum";
import { LENS } from "@/enums/ui.enum";
import { useAnomalyStore } from "@/state/anomaly.store";
import { usePanelStore } from "@/state/panel.store";
import { useTwinStore } from "@/state/twin.store";
import { selectedProductId, useUiStore } from "@/state/ui.store";
import { stockedStoreState } from "@/test/stockedState";

vi.mock("@/hooks/checkout.hook", () => ({ useCheckoutSummary: () => null, useCheckoutTransactions: () => [] }));
// apps/api serves no promotions yet; the dialog reads them through usePromotions.
vi.mock("@/hooks/commerce.hook", async () => {
  const { PROMOTION_KIND, PROMOTION_STATUS } = await import("@/enums/commerce.enum");
  const promotion = (id: string, name: string, skus: string[]) => ({
    id,
    name,
    status: PROMOTION_STATUS.Active,
    kind: PROMOTION_KIND.PercentOff,
    value: 0.15,
    starts_at: "2026-10-06T00:00:00Z",
    ends_at: "2026-10-13T00:00:00Z",
    skus,
    revenue: 0,
    incremental_revenue: 0,
    discount_cost: 0,
  });
  const summary = {
    store_id: "store-001",
    revenue: 0,
    incremental_revenue: 0,
    discount_cost: 0,
    promotions: [promotion("promo-1", "Pasta night bundle", ["P004", "P007"]), promotion("promo-2", "Breakfast week", ["P001"])],
  };
  return { usePromotions: () => summary };
});

const state = stockedStoreState();
const p004 = state.products.find((product) => product.sku === "P004")!;

beforeEach(() => {
  useTwinStore.setState({ live: state, issues: [], status: TWIN_STATUS.Ready });
  useAnomalyStore.setState({ anomalies: [] });
  useUiStore.setState({ lens: LENS.Operations, detailsSku: null });
  useUiStore.getState().select(null);
  usePanelStore.setState({ open: false });
});

afterEach(cleanup);

function renderPage() {
  return render(
    <>
      <EntityInspector />
      <ProductDetailsDialog />
    </>,
  );
}

describe("product details dialog", () => {
  it("opens from the product card with the twin figures, anomalies, and promotions of the product", async () => {
    useUiStore.getState().select("P004");
    useAnomalyStore.getState().raise({
      anomaly_id: "anm-P004",
      store_id: p004.store_id,
      sku: "P004",
      shelf_id: p004.shelf_id,
      slot_id: p004.slot_id,
      kind: ANOMALY_KIND.LowStock,
      severity: ANOMALY_SEVERITY.Medium,
      detected_at: "2026-10-09T08:00:00Z",
      context_version: state.context_version,
      correlation_id: "run-1",
    });
    renderPage();
    fireEvent.click(within(screen.getByLabelText("Product P004")).getByRole("button", { name: "Details" }));

    const dialog = await screen.findByRole("dialog");
    expect(dialog.textContent).toContain("Product P004");
    expect(dialog.textContent).toContain(`Shelf ${p004.shelf_id} · slot ${p004.slot_id}`);
    const stock = within(dialog).getByRole("region", { name: "In the Digital Twin" });
    expect(stock.textContent).toContain(`${p004.shelf_quantity}of ${p004.facings} facings`);
    expect(stock.textContent).toContain(String(p004.backroom_quantity));
    const anomalies = within(dialog).getByRole("list", { name: "Open anomalies" });
    expect(anomalies.textContent).toContain("Low stock");
    expect(anomalies.textContent).toContain("medium");
    const promotions = within(dialog).getByRole("region", { name: "Promotions" });
    expect(promotions.textContent).toContain("Pasta night bundle");
    expect(promotions.textContent).not.toContain("Breakfast week");
  });

  it("opens from a shelf's product list, and shows the product in the store", async () => {
    useUiStore.getState().select(p004.shelf_id, ENTITY_TYPE.Shelf);
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "Details of P004" }));

    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Show in the store" }));
    expect(selectedProductId(useUiStore.getState())).toBe("P004");
    await waitFor(() => expect(useUiStore.getState().detailsSku).toBeNull());
  });

  it("opens the Promotions lens from a product's promotions", async () => {
    useUiStore.getState().showDetails("P004");
    renderPage();
    fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Open in Promotions" }));
    expect(useUiStore.getState().lens).toBe(LENS.Promotions);
    expect(usePanelStore.getState().open).toBe(true);
  });

  it("says when a product is in no promotion", async () => {
    useUiStore.getState().showDetails("P002");
    renderPage();
    const dialog = await screen.findByRole("dialog");
    expect(dialog.textContent).toContain("Not in any promotion.");
    expect(dialog.textContent).toContain("No open anomalies.");
    expect(within(dialog).queryByRole("button", { name: "Open in Promotions" })).toBeNull();
  });
});

describe("anomaly simulator", () => {
  it("lives in the details dialog, not on the product card", () => {
    useUiStore.getState().select("P004");
    renderPage();
    expect(within(screen.getByLabelText("Product P004")).queryByRole("form", { name: "Simulate an anomaly" })).toBeNull();
  });

  it("raises an anomaly of the chosen kind and severity on the product, then clears it", async () => {
    useUiStore.getState().showDetails("P004");
    renderPage();
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).queryByRole("form", { name: "Simulate an anomaly" })).toBeNull();
    const toggle = within(dialog).getByRole("button", { name: "DEV Simulate" });
    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    const form = within(dialog).getByRole("form", { name: "Simulate an anomaly" });
    expect(within(form).getByRole("button", { name: "Clear" }).hasAttribute("disabled")).toBe(true);
    expect(dialog.textContent).toContain("No open anomalies.");
    expect(within(form).getByRole("radio", { name: "high" }).getAttribute("data-severity")).toBe("high");

    fireEvent.click(within(within(form).getByRole("radiogroup", { name: "Anomaly kind" })).getByRole("radio", { name: "Sales drop" }));
    fireEvent.click(within(within(form).getByRole("radiogroup", { name: "Severity" })).getByRole("radio", { name: "low" }));
    fireEvent.click(within(form).getByRole("button", { name: "Raise" }));

    expect(useAnomalyStore.getState().anomalies).toMatchObject([
      { sku: "P004", kind: ANOMALY_KIND.SalesDrop, severity: ANOMALY_SEVERITY.Low, context_version: state.context_version },
    ]);
    const rows = within(dialog).getByRole("list", { name: "Open anomalies" });
    expect(rows.textContent).toContain("Sales drop");
    expect(rows.textContent).toContain("low");
    expect(dialog.textContent).toContain("1 anomaly");

    fireEvent.click(within(form).getByRole("button", { name: "Clear" }));
    expect(useAnomalyStore.getState().anomalies).toHaveLength(0);
  });
});
