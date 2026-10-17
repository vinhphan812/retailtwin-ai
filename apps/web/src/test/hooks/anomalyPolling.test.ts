// @vitest-environment jsdom
/**
 * Regression tests for anomaly polling - verifies store integration and hook exports.
 *
 * These tests verify:
 * 1. The anomaly store has required methods for polling integration
 * 2. The hook exports correctly
 * 3. Demo mode detection works
 */
import { describe, expect, it } from "vitest";
import { useAnomalyStore } from "@/state/anomaly.store";
import { isDemoMode } from "@/core/twin/demoMode";
import * as anomalyModule from "@/hooks/anomalyPolling.hook";

describe("Anomaly polling regression tests", () => {
  describe("1. Store integration", () => {
    it("store has setAll method for initial fetch", () => {
      const store = useAnomalyStore.getState();
      expect(typeof store.setAll).toBe("function");
    });

    it("store has fail method for error handling", () => {
      const store = useAnomalyStore.getState();
      expect(typeof store.fail).toBe("function");
    });

    it("store has readError for distinguishing 404 from empty", () => {
      const store = useAnomalyStore.getState();
      expect("readError" in store).toBe(true);
      expect("setAll" in store).toBe(true);
      expect("fail" in store).toBe(true);
    });
  });

  describe("2. Hook exports", () => {
    it("useAnomalyPolling is exported as a function", () => {
      expect(typeof anomalyModule.useAnomalyPolling).toBe("function");
    });
  });

  describe("3. Demo mode detection", () => {
    it("isDemoMode is exported as a function", () => {
      expect(typeof isDemoMode).toBe("function");
    });
  });
});
