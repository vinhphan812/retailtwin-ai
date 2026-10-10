// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test } from "vitest";
import { ViewModeSwitch } from "@/components/layout/ViewModeSwitch";
import { SimulationBanner } from "@/components/twin/SimulationBanner";
import { VIEW_MODE } from "@/enums/ui.enum";
import { demoSimulation } from "@/fixtures/demo/simulation";
import { demoStoreState } from "@/fixtures/demo/store";
import { patchProduct } from "@/core/api/sources/memorySource";
import { useTwinStore } from "@/state/twin.store";
import { useUiStore } from "@/state/ui.store";

function Page() {
  return (
    <>
      <ViewModeSwitch />
      <SimulationBanner />
    </>
  );
}

const live = demoStoreState();

beforeEach(() => {
  useTwinStore.setState({ ...useTwinStore.getInitialState(), live }, true);
  useUiStore.getState().setViewMode(VIEW_MODE.Live);
});

afterEach(cleanup);

test("cannot switch to Simulation while no simulation is open", () => {
  render(<Page />);
  const simulation = screen.getByRole("radio", { name: "Simulation (none open)" });
  expect(simulation).toHaveProperty("disabled", true);
  fireEvent.click(simulation);
  expect(useUiStore.getState().viewMode).toBe(VIEW_MODE.Live);
  expect(screen.queryByRole("status", { name: "Simulation view" })).toBeNull();
});

test("labels the Simulation view with the run, its base, and that it is not executed", () => {
  useTwinStore.getState().setSimulation(demoSimulation(live));
  render(<Page />);
  expect(screen.getByRole("radio", { name: "Live" }).getAttribute("aria-checked")).toBe("true");
  expect(screen.queryByRole("status", { name: "Simulation view" })).toBeNull();

  fireEvent.click(screen.getByRole("radio", { name: "Simulation" }));
  expect(useUiStore.getState().viewMode).toBe(VIEW_MODE.Simulation);
  const banner = screen.getByRole("status", { name: "Simulation view" });
  expect(banner.textContent).toContain("SIMULATION");
  expect(banner.textContent).toContain("Proposed store, not executed");
  expect(banner.textContent).toContain("sim-demo-001 (evaluated)");
  expect(banner.textContent).toContain(`from Live ${live.context_version}`);
  expect(banner.textContent).not.toContain("Live is now");

  fireEvent.click(screen.getByRole("radio", { name: "Live" }));
  expect(screen.queryByRole("status", { name: "Simulation view" })).toBeNull();
});

test("says so when Live has moved on since the simulation started", () => {
  useTwinStore.getState().setSimulation(demoSimulation(live));
  useUiStore.getState().setViewMode(VIEW_MODE.Simulation);
  render(<Page />);
  const newer = { ...patchProduct(live, "P002", { shelf_quantity: 3 }), context_version: "store-001:v2", version: "v2" };
  act(() => useTwinStore.getState().setLive(newer));
  expect(screen.getByRole("status", { name: "Simulation view" }).textContent).toContain("Live is now store-001:v2");
});

test("goes back to Live when the simulation closes", () => {
  useTwinStore.getState().setSimulation(demoSimulation(live));
  useUiStore.getState().setViewMode(VIEW_MODE.Simulation);
  render(<Page />);
  act(() => useTwinStore.getState().setSimulation(null));
  expect(useUiStore.getState().viewMode).toBe(VIEW_MODE.Live);
  expect(screen.queryByRole("status", { name: "Simulation view" })).toBeNull();
});
