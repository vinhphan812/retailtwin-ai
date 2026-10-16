import { DEMO_RUN_POLL_MS } from "@/constants/app.constant";
import { useRunStore } from "@/state/run.store";
import type { ActivityEntry } from "@/types/agent.type";
import type { AgentEvent, RetailTwinClient } from "@/types/api.type";

/**
 * One flagship run as it plays: its `correlation_id`, a promise that settles when it ends
 * (rejected, with the reason, when it fails), and `stop` to stop reading it.
 */
export type DemoRun = { correlationId: string; done: Promise<void>; stop: () => void };

/** What the Run AI Demo button runs: resets the store and starts the flagship scenario. */
export type DemoRunner = { start: () => Promise<DemoRun> };

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

/**
 * The flagship demo on apps/api (#41): `POST /flagship/reset`, then `POST /flagship/start`.
 * `start` answers only once the whole chain has run, so it is sent and not awaited: from the
 * moment it is sent, every `pollMs` the runner reads `GET /flagship/status` and, once the
 * status names the run's `correlation_id`, `GET /agent/events` into the timeline (only this
 * run's entries). `start()` resolves as soon as the run is identified, by the status or by
 * the answer to `start`, whichever comes first; the run ends when the status says COMPLETE
 * or ERROR, or when `start` fails. It never advances a stage itself: the stages are the feed's.
 * TODO(BE): #41 (PR #202) to answer `start` at once (202) and to record each stage in the feed.
 */
export function createApiDemoRunner(client: RetailTwinClient, pollMs = DEMO_RUN_POLL_MS): DemoRunner {
  return {
    async start() {
      await client.flagshipReset();
      let correlationId: string | null = null;
      let cursor: string | null = null;
      let stopped = false;
      let timer: ReturnType<typeof setTimeout> | undefined;
      /** How `POST /flagship/start` answered, once it has. */
      let answer: { ok: true } | { ok: false; error: unknown } | null = null;

      let identify!: (id: string) => void;
      let failStart!: (error: unknown) => void;
      const identified = new Promise<string>((resolve, reject) => {
        identify = resolve;
        failStart = reject;
      });

      const readFeed = async () => {
        if (!correlationId) return;
        for (;;) {
          const page = await client.agentEvents(cursor);
          for (const event of page.events) {
            if (event.correlation_id === correlationId) useRunStore.getState().append(toActivityEntry(event));
          }
          if (page.cursor === null || page.cursor === cursor) return;
          cursor = page.cursor;
          if (!page.events.length) return;
        }
      };

      const done = new Promise<void>((resolve, reject) => {
        const fail = (error: unknown) => {
          failStart(error);
          reject(error);
        };
        const poll = async () => {
          if (stopped) return;
          try {
            if (answer && !answer.ok) return fail(answer.error);
            const status = await client.flagshipStatus();
            // IDLE is the reset, before `start` has reached the controller.
            if (status.phase !== "IDLE") correlationId ??= status.correlation_id;
            if (correlationId) identify(correlationId);
            else if (answer?.ok) return fail(new Error("The flagship run named no correlation_id."));
            await readFeed();
            if (stopped) return;
            if (status.phase === "COMPLETE") return resolve();
            if (status.phase === "ERROR") return fail(new Error(status.error ?? "The flagship run failed."));
            timer = setTimeout(poll, pollMs);
          } catch (error) {
            fail(error);
          }
        };

        client.flagshipStart().then(
          (started) => {
            answer = { ok: true };
            correlationId ??= started.correlation_id;
            if (correlationId) identify(correlationId);
          },
          (error: unknown) => {
            answer = { ok: false, error };
            if (!stopped) fail(error);
          },
        );
        void poll();
      });
      // A run that fails before it is identified rejects `start()`; nobody waits on `done` then.
      done.catch(() => {});

      await identified;
      return {
        correlationId: correlationId!,
        done,
        stop: () => {
          stopped = true;
          clearTimeout(timer);
        },
      };
    },
  };
}
