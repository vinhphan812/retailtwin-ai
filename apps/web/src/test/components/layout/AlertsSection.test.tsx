// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MotionGlobalConfig } from "framer-motion";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { AgentActivityPanel } from "@/components/layout/AgentActivityPanel";
import { ANOMALY_KIND, ANOMALY_SEVERITY } from "@/enums/anomaly.enum";
import { ENTITY_TYPE } from "@/enums/scene.enum";
import { TWIN_STATUS } from "@/enums/twin.enum";
import { DEMO_RUN_ID, demoAgentRun } from "@/fixtures/demo/agentRun";
import { anomalyFor, demoAnomalies } from "@/fixtures/demo/anomalies";
import { demoStoreState } from "@/fixtures/demo/store";
import { useAnomalyStore } from "@/state/anomaly.store";
import { usePanelStore } from "@/state/panel.store";
import { useRunStore } from "@/state/run.store";
import { useTwinStore } from "@/state/twin.store";
import { selectedProductId, useUiStore } from "@/state/ui.store";

vi.mock("@/components/status/StoreStatus", () => ({ StoreStatus: () => null }));

MotionGlobalConfig.skipAnimations = true;

const state = demoStoreState();
const product = (sku: string) => state.products.find((item) => item.sku === sku)!;
/** The demo's "publish demand spike": a demand surge raised on P005 with no prompt. */
const surgeOnP005 = () =>
  anomalyFor(product("P005"), ANOMALY_KIND.DemandSurge, ANOMALY_SEVERITY.Medium, state.context_version);
const p003 = () => demoAnomalies(state).anomalies.find((anomaly) => anomaly.sku === "P003")!;

const alertList = () => screen.getByRole("list", { name: "Open alerts and opportunities" });
const alertButton = (name: RegExp) => within(alertList()).getByRole("button", { name });

beforeEach(() => {
  usePanelStore.setState({ open: true });
  useRunStore.getState().reset();
  useAnomalyStore.setState({ anomalies: [] });
  useTwinStore.setState({ live: state, issues: [], status: TWIN_STATUS.Ready });
  useUiStore.getState().select(null);
});

afterEach(cleanup);

describe("Alerts & opportunities", () => {
  test("says so when nothing is open", () => {
    render(<AgentActivityPanel />);
    expect(screen.getByText("No open alerts or opportunities.")).toBeTruthy();
  });

  test("shows a demand surge as an opportunity on its SKU as soon as it is raised", () => {
    render(<AgentActivityPanel />);
    act(() => useAnomalyStore.getState().raise(surgeOnP005()));

    const item = alertButton(/Opportunity: Demand surge on P005/);
    expect(within(item).getByText("P005 · shelf A03")).toBeTruthy();
    expect(within(item).getByText("Agent: Detected")).toBeTruthy();
    expect(item.getAttribute("data-severity")).toBe("medium");
  });

  test("lists the worst first and marks every other kind as an alert", () => {
    useAnomalyStore.getState().setAll(demoAnomalies(state));
    render(<AgentActivityPanel />);
    const items = within(alertList()).getAllByRole("button");
    expect(items).toHaveLength(demoAnomalies(state).anomalies.length);
    expect(items[0].getAttribute("data-severity")).toBe("high");
    expect(items.at(-1)!.getAttribute("data-severity")).toBe("low");
    expect(items.filter((item) => item.getAttribute("data-category") === "opportunity")).toHaveLength(1);
  });

  test("moves through the lifecycle as the correlated agent run goes on, and leaves once resolved", () => {
    useAnomalyStore.getState().raise(p003());
    render(<AgentActivityPanel />);
    const item = () => alertButton(/Alert: Stockout on P003/);
    expect(within(item()).getByText("Agent: Detected")).toBeTruthy();

    const run = demoAgentRun(DEMO_RUN_ID);
    const stepOf = { INVESTIGATE: "Investigating", PLAN: "Planning", GUARD: "Guarding", ACT: "Acting", VERIFY: "Verifying" };
    for (const entry of run) {
      act(() => useRunStore.getState().append(entry));
      const step = stepOf[entry.stage as keyof typeof stepOf];
      if (step) expect(within(item()).getByText(`Agent: ${step}`)).toBeTruthy();
    }

    act(() => useAnomalyStore.getState().resolve(p003().anomaly_id));
    expect(screen.queryByRole("button", { name: /Alert: Stockout on P003/ })).toBeNull();
  });

  test("ignores agent runs of other anomalies", () => {
    useAnomalyStore.getState().raise(surgeOnP005());
    demoAgentRun(DEMO_RUN_ID).forEach((entry) => useRunStore.getState().append(entry));
    render(<AgentActivityPanel />);
    expect(within(alertButton(/Demand surge on P005/)).getByText("Agent: Detected")).toBeTruthy();
  });

  test("picking an alert selects its product, flies to it, and narrows the timeline to its run", async () => {
    useAnomalyStore.getState().raise(p003());
    demoAgentRun(DEMO_RUN_ID).forEach((entry) => useRunStore.getState().append(entry));
    useRunStore.getState().append({ id: "other", ts: new Date().toISOString(), stage: "OBSERVE", summary: "Another run.", correlation_id: "x" });
    render(<AgentActivityPanel />);
    const timeline = () => screen.getByRole("list", { name: "Agent activity timeline" });
    expect(within(timeline()).getByText("Another run.")).toBeTruthy();
    const seq = useUiStore.getState().focusSeq;

    const item = alertButton(/Stockout on P003/);
    fireEvent.click(item);
    const ui = useUiStore.getState();
    expect(selectedProductId(ui)).toBe("P003");
    expect(ui.selectedEntityType).toBe(ENTITY_TYPE.Product);
    expect(ui.focusSeq).toBe(seq + 1);
    expect(item.getAttribute("aria-pressed")).toBe("true");
    await waitFor(() => expect(within(timeline()).queryByText("Another run.")).toBeNull());
    expect(within(timeline()).getAllByRole("listitem")).toHaveLength(demoAgentRun().length);

    fireEvent.click(screen.getByRole("button", { name: "Show all" }));
    expect(within(timeline()).getByText("Another run.")).toBeTruthy();
    expect(selectedProductId(useUiStore.getState())).toBe("P003");
  });

  test("a later selection of the user's own clears the timeline filter", () => {
    useAnomalyStore.getState().raise(p003());
    render(<AgentActivityPanel />);
    fireEvent.click(alertButton(/Stockout on P003/));
    expect(screen.getByText("The agent has not started on this yet.")).toBeTruthy();

    act(() => useUiStore.getState().select("P005"));
    expect(screen.queryByRole("button", { name: "Show all" })).toBeNull();
    expect(useUiStore.getState().focusedCorrelationId).toBeNull();
  });

  test("an alert on a SKU missing from the twin cannot be picked, and says so", () => {
    useTwinStore.setState({ live: { ...state, products: state.products.filter((item) => item.sku !== "P005") } });
    useAnomalyStore.getState().raise(surgeOnP005());
    render(<AgentActivityPanel />);
    const item = alertButton(/Demand surge on P005/) as HTMLButtonElement;
    expect(item.disabled).toBe(true);
    expect(within(item).getByText("Not in the Digital Twin, cannot be shown")).toBeTruthy();
    fireEvent.click(item);
    expect(selectedProductId(useUiStore.getState())).toBeNull();
  });
});
