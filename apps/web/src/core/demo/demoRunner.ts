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
 * While the run plays, every `pollMs` it reads `GET /agent/events` into the timeline (only
 * this run's entries) and `GET /flagship/status`; the run ends when the status says COMPLETE
 * or ERROR. It never advances a stage itself: the stages are the feed's.
 * TODO(BE): needs #41 to record each stage in the feed and to answer `start` at once.
 */
export function createApiDemoRunner(client: RetailTwinClient, pollMs = DEMO_RUN_POLL_MS): DemoRunner {
  return {
    async start() {
      await client.flagshipReset();
      const started = await client.flagshipStart();
      let correlationId = started.correlation_id;
      let cursor: string | null = null;
      let stopped = false;
      let timer: ReturnType<typeof setTimeout> | undefined;

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
        const poll = async () => {
          if (stopped) return;
          try {
            const status = await client.flagshipStatus();
            correlationId ??= status.correlation_id;
            await readFeed();
            if (stopped) return;
            if (status.phase === "COMPLETE") return resolve();
            if (status.phase === "ERROR") return reject(new Error(status.error ?? "The flagship run failed."));
            timer = setTimeout(poll, pollMs);
          } catch (error) {
            reject(error);
          }
        };
        void poll();
      });

      return {
        get correlationId() {
          return correlationId ?? started.run_id;
        },
        done,
        stop: () => {
          stopped = true;
          clearTimeout(timer);
        },
      };
    },
  };
}
