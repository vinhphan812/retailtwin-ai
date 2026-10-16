import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApiDemoRunner, toActivityEntry } from "@/core/demo/demoRunner";
import { useRunStore } from "@/state/run.store";
import type { AgentEvent, FlagshipStatusResponse, RetailTwinClient } from "@/types/api.type";

const POLL = 100;

function event(id: string, stage: AgentEvent["stage"], correlation_id = "run-1", extra: Partial<AgentEvent> = {}): AgentEvent {
  return { id, ts: "2026-10-16T08:00:00Z", stage, status: "ok", correlation_id, summary: `${stage} ${id}`, ...extra };
}

function status(phase: FlagshipStatusResponse["phase"], error: string | null = null): FlagshipStatusResponse {
  return { run_id: "r", phase, correlation_id: "run-1", error };
}

/** A client whose feed and status answer from `pages` and `statuses`, one per poll. */
function fakeClient(pages: AgentEvent[][], statuses: FlagshipStatusResponse[]) {
  const calls: string[] = [];
  let page = 0;
  let poll = 0;
  const client = {
    flagshipReset: vi.fn(async () => {
      calls.push("reset");
      return {};
    }),
    flagshipStart: vi.fn(async () => {
      calls.push("start");
      return { run_id: "r", correlation_id: "run-1", phase: "RUNNING" as const };
    }),
    flagshipStatus: vi.fn(async () => statuses[Math.min(poll++, statuses.length - 1)]),
    agentEvents: vi.fn(async (since?: string | null) => {
      const events = pages[page] ?? [];
      const cursor = events.length ? String(++page) : (since ?? null);
      return { events, cursor };
    }),
  } as unknown as RetailTwinClient;
  return { client, calls };
}

beforeEach(() => {
  vi.useFakeTimers();
  useRunStore.getState().reset();
});
afterEach(() => vi.useRealTimers());

describe("createApiDemoRunner", () => {
  it("resets, starts, and reads only this run's entries into the timeline until COMPLETE", async () => {
    const { client, calls } = fakeClient(
      [[event("a", "DETECT"), event("x", "OBSERVE", "other-run")], [event("b", "SIMULATE", "run-1", { simulation_id: "sim-run-1" })], [event("c", "VERIFY")]],
      [status("RUNNING"), status("RUNNING"), status("COMPLETE")],
    );
    const run = await createApiDemoRunner(client, POLL).start();
    expect(calls).toEqual(["reset", "start"]);
    expect(run.correlationId).toBe("run-1");
    const settled = vi.fn();
    run.done.then(settled);

    await vi.advanceTimersByTimeAsync(POLL * 3);
    expect(settled).toHaveBeenCalled();
    expect(useRunStore.getState().activity.map((entry) => entry.id)).toEqual(["a", "b", "c"]);
    expect(useRunStore.getState().activity[1].simulation_id).toBe("sim-run-1");
  });

  it("fails with the controller's reason when the run ends in ERROR", async () => {
    const { client } = fakeClient([], [status("RUNNING"), status("ERROR", "Planner timed out.")]);
    const run = await createApiDemoRunner(client, POLL).start();
    const failed = run.done.catch((error: Error) => error.message);
    await vi.advanceTimersByTimeAsync(POLL * 2);
    await expect(failed).resolves.toBe("Planner timed out.");
  });

  it("fails when the controller cannot be reached, before anything is started", async () => {
    const { client } = fakeClient([], []);
    vi.mocked(client.flagshipReset).mockRejectedValue(new Error("Twin API unreachable."));
    await expect(createApiDemoRunner(client, POLL).start()).rejects.toThrow("Twin API unreachable.");
    expect(client.flagshipStart).not.toHaveBeenCalled();
  });

  it("stops reading once stopped", async () => {
    const { client } = fakeClient([], [status("RUNNING")]);
    const run = await createApiDemoRunner(client, POLL).start();
    await vi.advanceTimersByTimeAsync(POLL);
    run.stop();
    const reads = vi.mocked(client.flagshipStatus).mock.calls.length;
    await vi.advanceTimersByTimeAsync(POLL * 5);
    expect(vi.mocked(client.flagshipStatus).mock.calls.length).toBe(reads);
  });
});

describe("toActivityEntry", () => {
  it("keeps what the feed served and nothing else", () => {
    expect(toActivityEntry(event("e1", "ACT", "run-1", { sku: "P003", shelf_id: "A01", slot_id: null, decision: "d-1" }))).toEqual({
      id: "e1",
      ts: "2026-10-16T08:00:00Z",
      stage: "ACT",
      summary: "ACT e1",
      correlation_id: "run-1",
      decision_id: "d-1",
      sku: "P003",
      shelf_id: "A01",
      slot_id: undefined,
      simulation_id: undefined,
    });
    expect(toActivityEntry(event("e2", "PLAN", "run-1", { summary: null })).summary).toBe("PLAN");
  });
});
