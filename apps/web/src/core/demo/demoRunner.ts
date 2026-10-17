import { DEMO_RUN_IDENTIFY_TIMEOUT_MS, DEMO_RUN_POLL_MS, DEMO_RUN_READ_RETRIES } from "@/constants/app.constant";
import { useRunStore } from "@/state/run.store";
import type { ActivityEntry, ControlStage } from "@/types/agent.type";
import type { AgentEvent, FlagshipStatusResponse, RetailTwinClient } from "@/types/api.type";

/**
 * What a Run AI Demo button plays: a `replay` of fixtures/demo on the memory twin, which
 * never calls apps/api, or the real `flagship` run of apps/api. The UI says which.
 */
export const DEMO_RUN_SOURCE = {
  Replay: "replay",
  Flagship: "flagship",
} as const;
export type DemoRunSource = (typeof DEMO_RUN_SOURCE)[keyof typeof DEMO_RUN_SOURCE];

/**
 * One flagship run as it plays: its `correlation_id`, a promise that settles when it ends
 * (rejected, with the reason, when it fails), and `stop` to stop reading it.
 */
export type DemoRun = { correlationId: string; done: Promise<void>; stop: () => void };

/** What the Run AI Demo button runs: resets the store and starts the flagship scenario. */
export type DemoRunner = { source: DemoRunSource; start: () => Promise<DemoRun> };

/** An `AgentEvent` of `GET /agent/events` as a timeline entry; only what the feed served. */
export function toActivityEntry(event: AgentEvent): ActivityEntry {
  return {
    id: event.id,
    ts: event.ts,
    stage: event.stage,
    summary: event.summary ?? event.stage,
    correlation_id: event.correlation_id,
    decision_id: event.decision ?? undefined,
    sku: event.sku ?? undefined,
    shelf_id: event.shelf_id ?? undefined,
    slot_id: event.slot_id ?? undefined,
    simulation_id: event.simulation_id ?? undefined,
  };
}

/** The controller's timeline steps that are agent stages, by name; its other steps (start, event, replan, error) are not. */
const TIMELINE_STAGE: Record<string, ControlStage> = {
  investigate: "INVESTIGATE",
  plan: "PLAN",
  simulate: "SIMULATE",
  guard: "GUARD",
  verify: "VERIFY",
};

/**
 * The agent stages of the run `status` describes, from its `timeline`, as timeline entries:
 * the step's own detail, under the run's `correlation_id`. Nothing is added: a step that is
 * not an agent stage is left out, and an ACT the controller does not record stays absent.
 */
export function timelineEntries(status: FlagshipStatusResponse): ActivityEntry[] {
  if (!status.correlation_id) return [];
  const correlationId = status.correlation_id;
  return (status.timeline ?? []).flatMap((step, index): ActivityEntry[] => {
    const stage = TIMELINE_STAGE[step.stage];
    if (!stage) return [];
    return [{ id: `${status.run_id}:${index}`, ts: step.at, stage, summary: step.detail, correlation_id: correlationId }];
  });
}

/** A fresh `correlation_id` for one flagship run, so its entries never mix with an earlier run's. */
const newCorrelationId = () => `flagship-${crypto.randomUUID()}`;

/**
 * The flagship demo on apps/api (#41). It first reads `GET /flagship/status`: a run already
 * RUNNING (another tab, a second press) is followed, never reset or started again, since a
 * reset would clear it. Otherwise `POST /flagship/reset`, then `POST /flagship/start` under a
 * fresh `correlation_id`. `start` answers only once the whole chain has run, so it is sent and
 * not awaited: every `pollMs` the runner reads the status and this run's stages into the
 * timeline, from `GET /agent/events` when it serves any for the run, else from the status's
 * `timeline` (#202 records its stages there, not in the feed). `start()` resolves as soon as
 * the status or `start`'s answer names the run; the run ends when the status says COMPLETE or
 * ERROR, or when the status names another run. A failed `start` (a timeout on Cloud Run, say)
 * ends it only once the status does not name the run: while the controller carries on, the
 * runner follows it and never sends `start` again. A failed read of the status or the feed
 * (a dropped connection, a 5xx) is read again, waiting longer each time; the run ends in error
 * only after `readRetries` failed reads in a row. If neither the status nor `start`'s answer
 * names the run within `identifyTimeoutMs`, it ends in error and the runner stops reading.
 * It never advances a stage itself: the stages are the controller's.
 * TODO(BE): #41 to answer `start` at once (202) and to record each stage, ACT included, in the feed.
 */
export function createApiDemoRunner(
  client: RetailTwinClient,
  pollMs = DEMO_RUN_POLL_MS,
  correlationIdOf: () => string = newCorrelationId,
  { identifyTimeoutMs = DEMO_RUN_IDENTIFY_TIMEOUT_MS, readRetries = DEMO_RUN_READ_RETRIES } = {},
): DemoRunner {
  return {
    source: DEMO_RUN_SOURCE.Flagship,
    async start() {
      const before = await client.flagshipStatus();
      const joined = before.phase === "RUNNING" && before.correlation_id ? before.correlation_id : null;
      if (!joined) await client.flagshipReset();
      const ours = joined ?? correlationIdOf();
      let identifiedYet = false;
      let feedServed = false;
      let cursor: string | null = null;
      let stopped = false;
      let timer: ReturnType<typeof setTimeout> | undefined;
      let deadline: ReturnType<typeof setTimeout> | undefined;
      let failedReads = 0;
      /** How `POST /flagship/start` answered, once it has; a joined run sends none. */
      let answer: { ok: true } | { ok: false; error: unknown } | null = joined ? { ok: true } : null;

      let identify!: () => void;
      let failStart!: (error: unknown) => void;
      const identified = new Promise<void>((resolve, reject) => {
        identify = () => {
          identifiedYet = true;
          clearTimeout(deadline);
          resolve();
        };
        failStart = reject;
      });

      const append = (entries: ActivityEntry[]) => entries.forEach((entry) => useRunStore.getState().append(entry));

      const readStages = async (status: FlagshipStatusResponse) => {
        for (;;) {
          const page = await client.agentEvents(cursor);
          const own = page.events.filter((event) => event.correlation_id === ours);
          if (own.length) feedServed = true;
          append(own.map(toActivityEntry));
          if (page.cursor === null || page.cursor === cursor) break;
          cursor = page.cursor;
          if (!page.events.length) break;
        }
        if (!feedServed) append(timelineEntries(status));
      };

      const done = new Promise<void>((resolve, reject) => {
        const fail = (error: unknown) => {
          stopped = true;
          clearTimeout(timer);
          clearTimeout(deadline);
          failStart(error);
          reject(error);
        };
        const poll = async () => {
          if (stopped) return;
          try {
            const status = await client.flagshipStatus();
            // IDLE is the reset, before `start` has reached the controller.
            const isOurs = status.phase !== "IDLE" && status.correlation_id === ours;
            if (isOurs) identify();
            // `start` failed and the controller has no run of ours: it never started, or is gone.
            else if (answer && !answer.ok) return fail(answer.error);
            else if (identifiedYet || answer?.ok) return fail(new Error("Another flagship run replaced this one."));
            if (isOurs) await readStages(status);
            failedReads = 0;
            if (stopped) return;
            if (isOurs && status.phase === "COMPLETE") return resolve();
            if (isOurs && status.phase === "ERROR") {
              return fail(new Error(status.error ?? status.timeline?.at(-1)?.detail ?? "The flagship run failed."));
            }
            timer = setTimeout(poll, pollMs);
          } catch (error) {
            if (stopped) return;
            if (++failedReads > readRetries) return fail(error);
            timer = setTimeout(poll, pollMs * 2 ** failedReads);
          }
        };

        deadline = setTimeout(() => {
          if (!identifiedYet) fail(new Error(`The flagship run did not start within ${Math.round(identifyTimeoutMs / 1000)} s.`));
        }, identifyTimeoutMs);

        if (!joined) {
          client.flagshipStart(ours).then(
            () => {
              answer = { ok: true };
              identify();
            },
            // The next poll decides: a run the status still names goes on.
            (error: unknown) => {
              answer = { ok: false, error };
            },
          );
        }
        void poll();
      });
      // A run that fails before it is identified rejects `start()`; nobody waits on `done` then.
      done.catch(() => {});

      await identified;
      return {
        correlationId: ours,
        done,
        stop: () => {
          stopped = true;
          clearTimeout(timer);
        },
      };
    },
  };
}
