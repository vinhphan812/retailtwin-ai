import { describe, expect, it } from "vitest";
import { alertCategory, alertStep, sortAlerts } from "@/core/anomaly/alerts";
import { ALERT_CATEGORY, ALERT_STEP, ANOMALY_KIND, ANOMALY_KINDS, ANOMALY_SEVERITY } from "@/enums/anomaly.enum";
import { anomalyFor } from "@/fixtures/demo/anomalies";
import { demoStoreState } from "@/fixtures/demo/store";
import type { ActivityEntry, ControlStage } from "@/types/agent.type";

const state = demoStoreState();
const product = (sku: string) => state.products.find((item) => item.sku === sku)!;
const p003 = anomalyFor(product("P003"), ANOMALY_KIND.Stockout, ANOMALY_SEVERITY.High, state.context_version);

let seq = 0;
/** A timeline entry of `stage` at second `second`, in run `correlation_id`. */
function entry(stage: ControlStage, second: number, correlation_id = p003.correlation_id): ActivityEntry {
  seq += 1;
  return { id: `e${seq}`, ts: new Date(Date.UTC(2026, 9, 9, 8, 0, second)).toISOString(), stage, summary: stage, correlation_id };
}

describe("alertCategory", () => {
  it("reads a demand surge as an opportunity and every other kind as an alert", () => {
    for (const kind of ANOMALY_KINDS) {
      expect(alertCategory({ kind })).toBe(
        kind === ANOMALY_KIND.DemandSurge ? ALERT_CATEGORY.Opportunity : ALERT_CATEGORY.Alert,
      );
    }
  });
});

describe("alertStep", () => {
  it("is Detected while no entry carries the anomaly's correlation id", () => {
    expect(alertStep(p003, [])).toBe(ALERT_STEP.Detected);
    expect(alertStep(p003, [entry("ACT", 1, "another-run"), { ...entry("VERIFY", 2), correlation_id: undefined }])).toBe(
      ALERT_STEP.Detected,
    );
  });

  it("maps each control stage to its lifecycle step", () => {
    const expected: [ControlStage, string][] = [
      ["OBSERVE", ALERT_STEP.Detected],
      ["DETECT", ALERT_STEP.Detected],
      ["INVESTIGATE", ALERT_STEP.Investigating],
      ["PLAN", ALERT_STEP.Planning],
      ["SIMULATE", ALERT_STEP.Planning],
      ["GUARD", ALERT_STEP.Guarding],
      ["ACT", ALERT_STEP.Acting],
      ["VERIFY", ALERT_STEP.Verifying],
    ];
    for (const [stage, step] of expected) expect(alertStep(p003, [entry(stage, 1)])).toBe(step);
  });

  it("follows the latest correlated entry, whatever order they arrived in", () => {
    const activity = [entry("ACT", 5), entry("INVESTIGATE", 2), entry("VERIFY", 9, "another-run")];
    expect(alertStep(p003, activity)).toBe(ALERT_STEP.Acting);
  });

  it("stays Detected for an anomaly without a correlation id", () => {
    expect(alertStep({ correlation_id: "" }, [{ ...entry("ACT", 1), correlation_id: "" }])).toBe(ALERT_STEP.Detected);
  });
});

describe("sortAlerts", () => {
  it("puts the worst severity first, then the newest, without touching its input", () => {
    const low = anomalyFor(product("P012"), ANOMALY_KIND.SalesDrop, ANOMALY_SEVERITY.Low, "v1");
    const oldHigh = anomalyFor(product("P010"), ANOMALY_KIND.Stockout, ANOMALY_SEVERITY.High, "v1", "2026-10-09T07:00:00Z");
    const newHigh = anomalyFor(product("P003"), ANOMALY_KIND.Stockout, ANOMALY_SEVERITY.High, "v1", "2026-10-09T09:00:00Z");
    const input = [low, oldHigh, newHigh];
    expect(sortAlerts(input)).toEqual([newHigh, oldHigh, low]);
    expect(input).toEqual([low, oldHigh, newHigh]);
  });
});
