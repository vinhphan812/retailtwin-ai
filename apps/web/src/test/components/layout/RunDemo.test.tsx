// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, renderHook, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RunDemoButton } from "@/components/layout/RunDemoButton";
import { createMemoryTwin, type MemoryTwin } from "@/core/api/sources/memorySource";
import type { DemoRunner } from "@/core/demo/demoRunner";
import { createFixtureDemoRunner } from "@/core/demo/fixtureDemoRunner";
import { ENTITY_TYPE } from "@/enums/scene.enum";
import { LENS, VIEW_MODE } from "@/enums/ui.enum";
import { DEMO_RUN_ID } from "@/fixtures/demo/agentRun";
import { demoSimulation } from "@/fixtures/demo/simulation";
import { demoStoreState } from "@/fixtures/demo/store";
import { useAgentFocus } from "@/hooks/agentFocus.hook";
import { useDemoDirector } from "@/hooks/demoDirector.hook";
import { useAnomalyStore } from "@/state/anomaly.store";
import { DEMO_RUN_STATUS, useDemoRunStore } from "@/state/demoRun.store";
import { usePanelStore } from "@/state/panel.store";
import { useRunStore } from "@/state/run.store";
import { useTwinStore } from "@/state/twin.store";
import { useUiStore } from "@/state/ui.store";
import type { ControlStage } from "@/types/agent.type";

vi.mock("@/core/notify", () => ({
  notify: { info: vi.fn(), warning: vi.fn(), error: vi.fn(), success: vi.fn() },
  errorMessage: (error: unknown) => (error instanceof Error ? error.message : String(error)),
}));

const STEP = 1000;
let twin: MemoryTwin;

/** Feeds the memory twin's Live states to `twin.store`, as `useTwinSource` does. */
function feedLive() {
  useTwinStore.getState().setLive(twin.current());
  return twin.source.subscribe((state) => useTwinStore.getState().setLive(state));
}

function mount(runner: DemoRunner) {
  renderHook(() => {
    useDemoDirector();
    useAgentFocus();
  });
  render(<RunDemoButton runner={runner} />);
}

const button = () => screen.getByRole("button", { name: /AI demo|Run AI Demo/ });
const stage = (): ControlStage | undefined => useRunStore.getState().activity.at(-1)?.stage;

/** Plays the demo run up to and including `until`. */
async function playUntil(until: ControlStage) {
  for (let step = 0; step < 10 && stage() !== until; step++) {
    await act(async () => {
      await vi.advanceTimersByTimeAsync(STEP);
    });
  }
  expect(stage()).toBe(until);
}

let unfeed = () => {};
beforeEach(() => {
  vi.useFakeTimers();
  twin = createMemoryTwin(demoStoreState());
  useTwinStore.setState(useTwinStore.getInitialState(), true);
  useUiStore.setState(useUiStore.getInitialState(), true);
  useRunStore.getState().reset();
  useDemoRunStore.setState(useDemoRunStore.getInitialState(), true);
  usePanelStore.setState({ open: false });
  unfeed = feedLive();
});
afterEach(() => {
  unfeed();
  cleanup();
  vi.useRealTimers();
});

describe("Run AI Demo on the demo path", () => {
  it("plays the whole flagship run from one press, following the agent's stages", async () => {
    useUiStore.getState().setLens(LENS.Revenue);
    useUiStore.getState().setFollowAgent(false);
    mount(createFixtureDemoRunner(twin, STEP));

    await act(async () => {
      fireEvent.click(button());
    });
    // Follow agent on, the Operations lens open, and the button busy while the run plays.
    expect(useUiStore.getState()).toMatchObject({ followAgent: true, lens: LENS.Operations, viewMode: VIEW_MODE.Live });
    expect(usePanelStore.getState().open).toBe(true);
    expect(useDemoRunStore.getState()).toMatchObject({ status: DEMO_RUN_STATUS.Running, correlationId: DEMO_RUN_ID });
    expect((button() as HTMLButtonElement).disabled).toBe(true);
    expect(button().textContent).toContain("AI demo running…");

    await playUntil("INVESTIGATE");
    // The camera goes to the problem: the agent selects P003.
    expect(useUiStore.getState()).toMatchObject({ selectedEntityId: "P003", selectedEntityType: ENTITY_TYPE.Product });
    expect(useUiStore.getState().viewMode).toBe(VIEW_MODE.Live);

    await playUntil("PLAN");
    expect(useUiStore.getState().viewMode).toBe(VIEW_MODE.Live);
    await playUntil("SIMULATE");
    expect(useUiStore.getState().viewMode).toBe(VIEW_MODE.Simulation);

    const shelfBefore = twin.current().products.find((product) => product.sku === "P003")!.shelf_quantity;
    await playUntil("ACT");
    expect(useUiStore.getState().viewMode).toBe(VIEW_MODE.Live);
    // The demo controller's stand-in committed the proposal: Live changed, through its feed.
    expect(useTwinStore.getState().live!.products.find((product) => product.sku === "P003")!.shelf_quantity).toBeGreaterThan(
      shelfBefore,
    );

    expect(useAnomalyStore.getState().anomalies.some((anomaly) => anomaly.sku === "P003")).toBe(true);
    await playUntil("VERIFY");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    // Verified: the stockout the run handled is closed, the others stay.
    expect(useAnomalyStore.getState().anomalies.some((anomaly) => anomaly.sku === "P003")).toBe(false);
    expect(useAnomalyStore.getState().anomalies.length).toBeGreaterThan(0);
    expect(useDemoRunStore.getState().status).toBe(DEMO_RUN_STATUS.Done);
    expect((button() as HTMLButtonElement).disabled).toBe(false);
    expect(button().textContent).toContain("Run AI Demo again");
    expect(useUiStore.getState()).toMatchObject({ lens: LENS.Operations, viewMode: VIEW_MODE.Live });
  });

  it("never runs ahead of the agent: only this run's entries move the view", async () => {
    useTwinStore.getState().setSimulation(demoSimulation(twin.current()));
    const runner: DemoRunner = { start: async () => ({ correlationId: "run-1", done: new Promise(() => {}), stop: () => {} }) };
    mount(runner);
    await act(async () => {
      fireEvent.click(button());
    });
    const append = (id: string, stage: ControlStage, correlation_id = "run-1") =>
      act(() => useRunStore.getState().append({ id, ts: new Date().toISOString(), stage, summary: stage, correlation_id }));

    append("1", "PLAN");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(useUiStore.getState().viewMode).toBe(VIEW_MODE.Live);
    // Another run reaching SIMULATE is not this one.
    append("2", "SIMULATE", "run-other");
    expect(useUiStore.getState().viewMode).toBe(VIEW_MODE.Live);
    append("3", "SIMULATE");
    expect(useUiStore.getState().viewMode).toBe(VIEW_MODE.Simulation);
  });

  it("waits at SIMULATE until the simulation the entry names is open", async () => {
    const runner: DemoRunner = { start: async () => ({ correlationId: "run-1", done: new Promise(() => {}), stop: () => {} }) };
    mount(runner);
    await act(async () => {
      fireEvent.click(button());
    });
    const simulation = demoSimulation(twin.current());
    act(() =>
      useRunStore.getState().append({
        id: "s",
        ts: new Date().toISOString(),
        stage: "SIMULATE",
        summary: "Simulated.",
        correlation_id: "run-1",
        simulation_id: simulation.simulation_id,
      }),
    );
    expect(useUiStore.getState().viewMode).toBe(VIEW_MODE.Live);
    act(() => useTwinStore.getState().setSimulation(simulation));
    expect(useUiStore.getState().viewMode).toBe(VIEW_MODE.Simulation);
  });

  it("stops moving the view after Stop following, while the run plays on", async () => {
    mount(createFixtureDemoRunner(twin, STEP));
    await act(async () => {
      fireEvent.click(button());
    });
    await playUntil("DETECT");
    fireEvent.click(screen.getByRole("button", { name: "Stop following" }));
    expect(useUiStore.getState().followAgent).toBe(false);

    await playUntil("SIMULATE");
    expect(useUiStore.getState().viewMode).toBe(VIEW_MODE.Live);
    expect(screen.queryByRole("button", { name: "Stop following" })).toBeNull();
  });

  it("shows the controller's error with Retry, and leaves the store usable", async () => {
    const start = vi
      .fn<DemoRunner["start"]>()
      .mockRejectedValueOnce(new Error("Twin API unreachable."))
      .mockImplementation(() => createFixtureDemoRunner(twin, STEP).start());
    mount({ start });

    await act(async () => {
      fireEvent.click(button());
    });
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("The AI demo could not run: Twin API unreachable.");
    expect(useDemoRunStore.getState().status).toBe(DEMO_RUN_STATUS.Error);
    expect((button() as HTMLButtonElement).disabled).toBe(false);
    expect(useTwinStore.getState().live).not.toBeNull();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    });
    expect(start).toHaveBeenCalledTimes(2);
    expect(useDemoRunStore.getState().status).toBe(DEMO_RUN_STATUS.Running);
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("shows a failed run's reason, with the stages it reached left in the timeline", async () => {
    let fail: (error: Error) => void = () => {};
    const runner: DemoRunner = {
      start: async () => ({
        correlationId: "run-x",
        done: new Promise((_, reject) => (fail = reject)),
        stop: () => {},
      }),
    };
    mount(runner);
    await act(async () => {
      fireEvent.click(button());
    });
    await act(async () => fail(new Error("Planner timed out.")));
    expect(screen.getByRole("alert").textContent).toContain("Planner timed out.");
  });

  it("renders nothing without a runner", () => {
    const { container } = render(<RunDemoButton runner={null} />);
    expect(container.innerHTML).toBe("");
  });
});
