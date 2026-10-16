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

/**
 * A client whose feed and status answer from `pages` and `statuses`, one per poll. Like
 * #41, `POST /flagship/start` answers only when the test calls `finishStart` (or `failStart`).
 */
function fakeClient(pages: AgentEvent[][], statuses: FlagshipStatusResponse[]) {
  const calls: string[] = [];
  let page = 0;
  let poll = 0;
  let finishStart: (correlationId?: string | null) => void = () => {};
  let failStart: (error: Error) => void = () => {};
  const client = {
    flagshipReset: vi.fn(async () => {
      calls.push("reset");
      return {};
    }),
    flagshipStart: vi.fn(() => {
      calls.push("start");
      return new Promise((resolve, reject) => {
        finishStart = (correlation_id = "run-1") => resolve({ run_id: "r", correlation_id, phase: "COMPLETE" as const });
        failStart = reject;
      });
    }),
    flagshipStatus: vi.fn(async () => statuses[Math.min(poll++, statuses.length - 1)]),
    agentEvents: vi.fn(async (since?: string | null) => {
      const events = pages[page] ?? [];
      const cursor = events.length ? String(++page) : (since ?? null);
      return { events, cursor };
    }),
  } as unknown as RetailTwinClient;
  return { client, calls, finishStart: (id?: string | null) => finishStart(id), failStart: (error: Error) => failStart(error) };
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

  it("follows the stages live while POST /flagship/start has not answered yet", async () => {
    const { client, finishStart } = fakeClient([], [status("IDLE"), status("RUNNING"), status("RUNNING"), status("COMPLETE")]);
    // The feed grows as the controller runs: one more stage by each status read.
    const feed = [event("a", "DETECT"), event("b", "SIMULATE"), event("c", "VERIFY")];
    vi.mocked(client.agentEvents).mockImplementation(async (since) => {
      const from = Number(since ?? 0);
      const to = Math.max(from, vi.mocked(client.flagshipStatus).mock.calls.length - 1);
      return { events: feed.slice(from, to), cursor: String(to) };
    });
    const starting = createApiDemoRunner(client, POLL).start();
    await vi.advanceTimersByTimeAsync(0);
    // The reset is still the status: nothing is read before the run is identified.
    expect(client.agentEvents).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(POLL);
    const run = await starting;
    expect(run.correlationId).toBe("run-1");
    expect(useRunStore.getState().activity.map((entry) => entry.id)).toEqual(["a"]);
    await vi.advanceTimersByTimeAsync(POLL);
    expect(useRunStore.getState().activity.map((entry) => entry.id)).toEqual(["a", "b"]);

    const settled = vi.fn();
    run.done.then(settled);
    await vi.advanceTimersByTimeAsync(POLL);
    expect(settled).toHaveBeenCalled();
    expect(useRunStore.getState().activity.map((entry) => entry.id)).toEqual(["a", "b", "c"]);
    expect(client.flagshipStart).toHaveBeenCalledTimes(1);
    finishStart();
  });

  it("is identified by the answer to start when the status has not named the run", async () => {
    const { client, finishStart } = fakeClient([[event("a", "VERIFY")]], [status("IDLE"), status("COMPLETE")]);
    const starting = createApiDemoRunner(client, POLL).start();
    await vi.advanceTimersByTimeAsync(0);
    finishStart("run-1");
    const run = await starting;
    expect(run.correlationId).toBe("run-1");
    await vi.advanceTimersByTimeAsync(POLL);
    await expect(run.done).resolves.toBeUndefined();
    expect(useRunStore.getState().activity.map((entry) => entry.id)).toEqual(["a"]);
  });

  it("fails when POST /flagship/start fails before the run is identified", async () => {
    const { client, failStart } = fakeClient([], [status("IDLE")]);
    const starting = createApiDemoRunner(client, POLL).start();
    const failed = starting.catch((error: Error) => error.message);
    await vi.advanceTimersByTimeAsync(0);
    failStart(new Error("Cannot start from phase RUNNING."));
    await vi.advanceTimersByTimeAsync(POLL);
    await expect(failed).resolves.toBe("Cannot start from phase RUNNING.");
  });

  it("ends the run in error when POST /flagship/start fails after it was identified", async () => {
    const { client, failStart } = fakeClient([], [status("RUNNING")]);
    const run = await createApiDemoRunner(client, POLL).start();
    const failed = run.done.catch((error: Error) => error.message);
    failStart(new Error("Twin API unreachable."));
    await vi.advanceTimersByTimeAsync(0);
    await expect(failed).resolves.toBe("Twin API unreachable.");
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
