/**
 * Plays the Run AI Demo against a real apps/api with the button's own runner
 * (`createApiDemoRunner`) and prints what happened: every request, every status poll, every
 * stage the timeline took, and a summary (identity, stages, how many starts were sent).
 *
 *   npm run flagship:capture -- <api-base-url> [--start-timeout-ms N] [--poll-ms N]
 *
 * `--start-timeout-ms` aborts `POST /flagship/start` on the client after N ms, as a Cloud Run
 * timeout would, while the controller carries on. It also presses the button a second time
 * while the run is RUNNING, as another tab would. It resets and starts the flagship run on that
 * API, so point it only at an API whose Live Twin may be reset.
 */
import { createClient } from "../src/core/api/client";
import { createApiDemoRunner } from "../src/core/demo/demoRunner";
import { useRunStore } from "../src/state/run.store";

const args = process.argv.slice(2);
const base = args.find((arg) => !arg.startsWith("--") && !/^\d+$/.test(arg));
const option = (name: string) => {
  const at = args.indexOf(name);
  return at >= 0 ? Number(args[at + 1]) : undefined;
};
if (!base) {
  console.error("usage: npm run flagship:capture -- <api-base-url> [--start-timeout-ms N] [--poll-ms N]");
  process.exit(2);
}
const startTimeoutMs = option("--start-timeout-ms");
const pollMs = option("--poll-ms") ?? 250;

const t0 = Date.now();
const at = () => `+${String(Date.now() - t0).padStart(6)}ms`;
const sent: string[] = [];

/** fetch that logs each request, cuts `POST /flagship/start` short if asked, and prints each status poll. */
const capture: typeof fetch = async (input, init) => {
  const url = new URL(String(input));
  const method = init?.method ?? "GET";
  const label = `${method} ${url.pathname}`;
  sent.push(label);
  let signal = init?.signal;
  if (startTimeoutMs !== undefined && label === "POST /flagship/start") signal = AbortSignal.timeout(startTimeoutMs);
  try {
    const response = await fetch(input, { ...init, signal });
    if (label === "GET /flagship/status") {
      const body = await response.clone().json();
      const steps = (body.timeline ?? []).map((step: { stage: string }) => step.stage).join(",");
      console.log(`${at()} ${label} ${response.status} phase=${body.phase} correlation_id=${body.correlation_id} timeline=[${steps}]`);
    } else {
      console.log(`${at()} ${label} ${response.status}`);
    }
    return response;
  } catch (error) {
    console.log(`${at()} ${label} FAILED ${(error as Error).name}: ${(error as Error).message}`);
    throw error;
  }
};

const client = createClient(base, capture);
let seen = 0;
useRunStore.subscribe((state) => {
  for (const entry of state.activity.slice(seen)) {
    console.log(`${at()}   stage ${entry.stage} correlation_id=${entry.correlation_id} — ${entry.summary}`);
  }
  seen = state.activity.length;
});

const runner = createApiDemoRunner(client, pollMs);
console.log(`${at()} press Run AI Demo against ${base}${startTimeoutMs !== undefined ? ` (start cut at ${startTimeoutMs} ms)` : ""}`);
const run = await runner.start();
console.log(`${at()} identified: correlation_id=${run.correlationId}`);

let second: string | null = null;
if (startTimeoutMs !== undefined) {
  const status = await client.flagshipStatus();
  if (status.phase === "RUNNING") {
    console.log(`${at()} second press while RUNNING`);
    const joined = await createApiDemoRunner(client, pollMs).start();
    joined.stop();
    second = joined.correlationId;
    console.log(`${at()} second press joined correlation_id=${second}`);
  }
}

let outcome = "COMPLETE";
await run.done.catch((error: Error) => {
  outcome = `ERROR: ${error.message}`;
});
const stages = useRunStore.getState().activity;
const final = await client.flagshipStatus();
console.log(`\n── summary`);
console.log(`outcome: ${outcome}`);
console.log(`final status: phase=${final.phase} correlation_id=${final.correlation_id} run_id=${final.run_id}`);
console.log(`identity: runner=${run.correlationId} status=${final.correlation_id} match=${run.correlationId === final.correlation_id}`);
console.log(`stages in the timeline: ${stages.map((entry) => entry.stage).join(" → ") || "none"}`);
console.log(`stages under another correlation_id: ${stages.filter((entry) => entry.correlation_id !== run.correlationId).length}`);
console.log(`POST /flagship/reset sent: ${sent.filter((label) => label === "POST /flagship/reset").length}`);
console.log(`POST /flagship/start sent: ${sent.filter((label) => label === "POST /flagship/start").length}`);
if (second !== null) console.log(`second press: joined ${second}, same run=${second === run.correlationId}`);
process.exit(0);
