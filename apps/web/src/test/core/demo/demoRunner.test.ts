import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApiDemoRunner, timelineEntries, toActivityEntry } from "@/core/demo/demoRunner";
import { useRunStore } from "@/state/run.store";
import type { AgentEvent, FlagshipStatusResponse, RetailTwinClient } from "@/types/api.type";

const POLL = 100;

function event(id: string, stage: AgentEvent["stage"], correlation_id = "run-1", extra: Partial<AgentEvent> = {}): AgentEvent {
  return { id, ts: "2026-10-16T08:00:00Z", stage, status: "ok", correlation_id, summary: `${stage} ${id}`, ...extra };
}

function status(
  phase: FlagshipStatusResponse["phase"],
  error: string | null = null,
  extra: Partial<FlagshipStatusResponse> = {},
): FlagshipStatusResponse {
  return { run_id: "r", phase, correlation_id: "run-1", error, ...extra };
}

/** What the status says before the press: the previous run, finished. */
const PREVIOUS = status("COMPLETE", null, { run_id: "r0", correlation_id: "previous-run" });

/** The runner under test, naming its run "run-1". */
const runner = (client: RetailTwinClient) => createApiDemoRunner(client, POLL, () => "run-1");

/**
 * A client whose feed and status answer from `pages` and `statuses`, one per poll, after
 * `first` (the status read before the press, PREVIOUS by default). Like
 * #41, `POST /flagship/start` answers only when the test calls `finishStart` (or `failStart`).
 */
function fakeClient(pages: AgentEvent[][], polled: FlagshipStatusResponse[], first: FlagshipStatusResponse = PREVIOUS) {
  const statuses = [first, ...polled];
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
    const run = await runner(client).start();
    expect(calls).toEqual(["reset", "start"]);
    expect(client.flagshipStart).toHaveBeenCalledWith("run-1");
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
      const to = Math.max(from, vi.mocked(client.flagshipStatus).mock.calls.length - 2);
      return { events: feed.slice(from, to), cursor: String(to) };
    });
    const starting = runner(client).start();
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
    const starting = runner(client).start();
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
    const starting = runner(client).start();
    const failed = starting.catch((error: Error) => error.message);
    await vi.advanceTimersByTimeAsync(0);
    failStart(new Error("Cannot start from phase RUNNING."));
    await vi.advanceTimersByTimeAsync(POLL);
    await expect(failed).resolves.toBe("Cannot start from phase RUNNING.");
  });

  it("keeps following its run when POST /flagship/start times out but the controller carries on", async () => {
    const { client, calls, failStart } = fakeClient(
      [],
      [
        status("RUNNING", null, { timeline: [{ stage: "investigate", detail: "investigating P017", at: "t1" }] }),
        status("RUNNING", null, { timeline: [{ stage: "investigate", detail: "investigating P017", at: "t1" }, { stage: "plan", detail: "plan", at: "t2" }] }),
        status("COMPLETE", null, {
          timeline: [
            { stage: "investigate", detail: "investigating P017", at: "t1" },
            { stage: "plan", detail: "plan", at: "t2" },
            { stage: "verify", detail: "verified", at: "t3" },
          ],
        }),
      ],
    );
    const run = await runner(client).start();
    failStart(new Error("The request timed out."));
    await vi.advanceTimersByTimeAsync(POLL * 3);
    await expect(run.done).resolves.toBeUndefined();
    expect(useRunStore.getState().activity.map((entry) => entry.stage)).toEqual(["INVESTIGATE", "PLAN", "VERIFY"]);
    // One reset and one start: a timed-out start is never sent again.
    expect(calls).toEqual(["reset", "start"]);
  });

  it("ends in error with start's failure once the status no longer names the run", async () => {
    const { client, failStart } = fakeClient([], [status("RUNNING"), status("IDLE", null, { correlation_id: null })]);
    const run = await runner(client).start();
    const failed = run.done.catch((error: Error) => error.message);
    failStart(new Error("Twin API unreachable."));
    await vi.advanceTimersByTimeAsync(POLL * 2);
    await expect(failed).resolves.toBe("Twin API unreachable.");
  });

  it("fails with the controller's reason when the run ends in ERROR", async () => {
    const { client } = fakeClient([], [status("RUNNING"), status("ERROR", "Planner timed out.")]);
    const run = await runner(client).start();
    const failed = run.done.catch((error: Error) => error.message);
    await vi.advanceTimersByTimeAsync(POLL * 2);
    await expect(failed).resolves.toBe("Planner timed out.");
  });

  it("fails when the controller cannot be reached, before anything is started", async () => {
    const { client } = fakeClient([], []);
    vi.mocked(client.flagshipReset).mockRejectedValue(new Error("Twin API unreachable."));
    await expect(runner(client).start()).rejects.toThrow("Twin API unreachable.");
    expect(client.flagshipStart).not.toHaveBeenCalled();
  });

  it("follows a run that is already RUNNING instead of resetting or starting another", async () => {
    const { client, calls } = fakeClient([[event("a", "PLAN", "other-tab")]], [status("RUNNING", null, { correlation_id: "other-tab" }), status("COMPLETE", null, { correlation_id: "other-tab" })], status("RUNNING", null, { correlation_id: "other-tab" }));
    const run = await runner(client).start();
    expect(calls).toEqual([]);
    expect(run.correlationId).toBe("other-tab");
    await vi.advanceTimersByTimeAsync(POLL);
    await expect(run.done).resolves.toBeUndefined();
    expect(useRunStore.getState().activity.map((entry) => entry.id)).toEqual(["a"]);
  });

  it("never takes an earlier run's entries, even under the controller's default correlation_id", async () => {
    const { client } = fakeClient(
      [[event("old", "VERIFY", "run-weekend-demand-surge-1"), event("a", "PLAN")]],
      [status("RUNNING"), status("COMPLETE")],
      status("COMPLETE", null, { correlation_id: "run-weekend-demand-surge-1" }),
    );
    const run = await runner(client).start();
    await vi.advanceTimersByTimeAsync(POLL * 2);
    await run.done;
    expect(useRunStore.getState().activity.map((entry) => entry.id)).toEqual(["a"]);
  });

  it("reads the stages from the status timeline while the feed serves none for the run, as #202 records them", async () => {
    const step = (stage: string, detail: string) => ({ stage, detail, at: "2026-10-16T08:00:00Z" });
    const timeline = [step("start", "flagship start"), step("event", "sale.completed"), step("investigate", "evidence"), step("plan", "first decision")];
    const { client } = fakeClient([], [
      status("RUNNING", null, { timeline: timeline.slice(0, 3) }),
      status("RUNNING", null, { timeline }),
      status("COMPLETE", null, { timeline: [...timeline, step("simulate", "scored 3"), step("guard", "verdict=ALLOW"), step("replan", "SKIPPED"), step("verify", "status=VERIFIED")] }),
    ]);
    const run = await runner(client).start();
    const stages = () => useRunStore.getState().activity.map((entry) => entry.stage);
    expect(stages()).toEqual(["INVESTIGATE"]);
    await vi.advanceTimersByTimeAsync(POLL);
    expect(stages()).toEqual(["INVESTIGATE", "PLAN"]);
    await vi.advanceTimersByTimeAsync(POLL);
    await run.done;
    expect(stages()).toEqual(["INVESTIGATE", "PLAN", "SIMULATE", "GUARD", "VERIFY"]);
    expect(useRunStore.getState().activity.every((entry) => entry.correlation_id === "run-1")).toBe(true);
  });

  it("ends in error when the status names another run", async () => {
    const { client } = fakeClient([], [status("RUNNING"), status("RUNNING", null, { correlation_id: "someone-else" })]);
    const run = await runner(client).start();
    const failed = run.done.catch((error: Error) => error.message);
    await vi.advanceTimersByTimeAsync(POLL);
    await expect(failed).resolves.toBe("Another flagship run replaced this one.");
  });

  it("gives the failing step's detail when an ERROR run serves no error", async () => {
    const { client } = fakeClient([], [status("RUNNING"), status("ERROR", null, { timeline: [{ stage: "plan", detail: "planner returned no decisions", at: "t" }] })]);
    const run = await runner(client).start();
    const failed = run.done.catch((error: Error) => error.message);
    await vi.advanceTimersByTimeAsync(POLL);
    await expect(failed).resolves.toBe("planner returned no decisions");
  });

  it("ends in error when neither the status nor start's answer names the run in time, and stops reading", async () => {
    const { client } = fakeClient([], [status("IDLE", null, { correlation_id: null })]);
    const starting = createApiDemoRunner(client, POLL, () => "run-1", { identifyTimeoutMs: POLL * 5 }).start();
    const failed = starting.catch((error: Error) => error.message);
    await vi.advanceTimersByTimeAsync(POLL * 5);
    await expect(failed).resolves.toBe("The flagship run did not start within 1 s.");
    const reads = vi.mocked(client.flagshipStatus).mock.calls.length;
    await vi.advanceTimersByTimeAsync(POLL * 10);
    expect(vi.mocked(client.flagshipStatus).mock.calls.length).toBe(reads);
    // The deadline sends nothing of its own: no second start, no reset.
    expect(client.flagshipStart).toHaveBeenCalledTimes(1);
    expect(client.flagshipReset).toHaveBeenCalledTimes(1);
  });

  it("reads the status again after a failed read, waiting longer each time, and finishes the run", async () => {
    const step = (stage: string) => ({ stage, detail: stage, at: "t" });
    const { client, calls } = fakeClient([], [
      status("RUNNING", null, { timeline: [step("investigate")] }),
      status("COMPLETE", null, { timeline: [step("investigate"), step("plan"), step("verify")] }),
    ]);
    const run = await runner(client).start();
    vi.mocked(client.flagshipStatus).mockRejectedValueOnce(new Error("503")).mockRejectedValueOnce(new Error("503"));
    const settled = vi.fn();
    run.done.then(settled);
    // Poll at +100 fails, retry at +200 fails, retry at +400 reads COMPLETE.
    await vi.advanceTimersByTimeAsync(POLL + POLL * 2);
    expect(settled).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(POLL * 4);
    await expect(run.done).resolves.toBeUndefined();
    expect(useRunStore.getState().activity.map((entry) => entry.stage)).toEqual(["INVESTIGATE", "PLAN", "VERIFY"]);
    expect(calls).toEqual(["reset", "start"]);
  });

  it("reads the feed again after a failed read, without losing the run's entries", async () => {
    const { client } = fakeClient([[event("a", "PLAN")], [event("b", "VERIFY")]], [status("RUNNING"), status("RUNNING"), status("COMPLETE")]);
    const run = await runner(client).start();
    vi.mocked(client.agentEvents).mockRejectedValueOnce(new Error("Failed to fetch"));
    await vi.advanceTimersByTimeAsync(POLL * 10);
    await expect(run.done).resolves.toBeUndefined();
    expect(useRunStore.getState().activity.map((entry) => entry.id)).toEqual(["a", "b"]);
  });

  it("counts only failed reads in a row: a good read in between starts the count again", async () => {
    const { client } = fakeClient([], [status("RUNNING"), status("RUNNING"), status("RUNNING"), status("COMPLETE")]);
    const run = await createApiDemoRunner(client, POLL, () => "run-1", { readRetries: 1 }).start();
    const flaky = vi.mocked(client.flagshipStatus);
    flaky.mockRejectedValueOnce(new Error("503"));
    await vi.advanceTimersByTimeAsync(POLL + POLL * 2);
    flaky.mockRejectedValueOnce(new Error("503"));
    await vi.advanceTimersByTimeAsync(POLL * 20);
    await expect(run.done).resolves.toBeUndefined();
  });

  it("ends in error with the last failure once the reads fail more times in a row than it retries, and stops reading", async () => {
    const { client } = fakeClient([], [status("RUNNING")]);
    const run = await createApiDemoRunner(client, POLL, () => "run-1", { readRetries: 2 }).start();
    const failed = run.done.catch((error: Error) => error.message);
    vi.mocked(client.flagshipStatus)
      .mockRejectedValueOnce(new Error("503"))
      .mockRejectedValueOnce(new Error("503"))
      .mockRejectedValueOnce(new Error("Twin API unreachable."));
    // +100, then retries at +200 and +400.
    await vi.advanceTimersByTimeAsync(POLL + POLL * 2 + POLL * 4);
    await expect(failed).resolves.toBe("Twin API unreachable.");
    const reads = vi.mocked(client.flagshipStatus).mock.calls.length;
    await vi.advanceTimersByTimeAsync(POLL * 20);
    expect(vi.mocked(client.flagshipStatus).mock.calls.length).toBe(reads);
  });

  it("stops reading once stopped", async () => {
    const { client } = fakeClient([], [status("RUNNING")]);
    const run = await runner(client).start();
    await vi.advanceTimersByTimeAsync(POLL);
    run.stop();
    const reads = vi.mocked(client.flagshipStatus).mock.calls.length;
    await vi.advanceTimersByTimeAsync(POLL * 5);
    expect(vi.mocked(client.flagshipStatus).mock.calls.length).toBe(reads);
  });
});

describe("timelineEntries", () => {
  it("keeps the agent stages, with the step's own detail, and nothing for a status without a run", () => {
    const timeline = [{ stage: "replan", detail: "status=SKIPPED", at: "t0" }, { stage: "verify", detail: "status=VERIFIED", at: "t1" }];
    expect(timelineEntries(status("COMPLETE", null, { timeline }))).toEqual([
      { id: "r:1", ts: "t1", stage: "VERIFY", summary: "status=VERIFIED", correlation_id: "run-1" },
    ]);
    expect(timelineEntries(status("IDLE", null, { correlation_id: null, timeline }))).toEqual([]);
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
