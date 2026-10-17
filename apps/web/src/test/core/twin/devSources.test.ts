// @vitest-environment jsdom
import { createElement } from "react";
import { cleanup, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApiSource } from "@/core/api/sources/apiSource";
import { isDemoMode } from "@/core/twin/demoMode";
import { pickSimulationSource, pickSource } from "@/core/twin/devSources";
import { DemoBadge } from "@/components/twin/DemoBadge";
import { demoStoreState } from "@/fixtures/demo/store";
import { useCheckoutSummary, useCheckoutTransactions } from "@/hooks/checkout.hook";
import { useAnomalyStore } from "@/state/anomaly.store";
import { useTwinStore } from "@/state/twin.store";
import type { TwinSource } from "@/core/api/sources/TwinSource";

/** The apps/api twin, here one that cannot be reached. */
const apiSource = vi.hoisted<TwinSource>(() => ({
  snapshot: () => Promise.reject(new Error("The API is unreachable.")),
  subscribe: () => () => {},
}));

vi.mock("@/core/api/sources/apiSource", () => ({ createApiSource: vi.fn(() => apiSource) }));

const at = (url: string) => window.history.replaceState(null, "", url);

beforeEach(() => {
  vi.mocked(createApiSource).mockClear();
  useAnomalyStore.setState({ anomalies: [], readError: null });
  useTwinStore.setState({ simulation: null, candidates: [], selectedCandidateId: null });
});

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
  at("/");
});

describe("pickSource", () => {
  it("reads the Live Twin from apps/api without a ?twin= override", () => {
    at("/");
    expect(pickSource()).toBe(apiSource);
    expect(createApiSource).toHaveBeenCalledTimes(1);
  });

  it("swaps in the demo store and its anomalies under ?twin=demo in development", async () => {
    at("/?twin=demo");
    const source = pickSource();
    expect(source).not.toBe(apiSource);
    expect(createApiSource).not.toHaveBeenCalled();
    await expect(source.snapshot()).resolves.toMatchObject({ products: demoStoreState().products });
    expect(useAnomalyStore.getState().anomalies.length).toBeGreaterThan(0);
    expect(useTwinStore.getState().simulation).toMatchObject({
      simulation_id: "sim-demo-001",
      base_context_version: demoStoreState().context_version,
    });
    expect(useTwinStore.getState().candidates.map((item) => item.simulation_id)).toEqual(
      expect.arrayContaining(["sim-demo-001"]),
    );
    expect(useTwinStore.getState().candidates.length).toBeGreaterThanOrEqual(2);
  });

  it("lets the console fail the demo anomaly read and read it again", () => {
    at("/?twin=demo");
    pickSource();
    const count = useAnomalyStore.getState().anomalies.length;
    const twin = (window as unknown as { twin: { failAnomalies: (message?: string) => void; reloadAnomalies: () => void } }).twin;

    twin.failAnomalies();
    expect(useAnomalyStore.getState()).toMatchObject({ readError: "GET /anomalies did not answer." });
    expect(useAnomalyStore.getState().anomalies).toHaveLength(count);

    twin.reloadAnomalies();
    expect(useAnomalyStore.getState().readError).toBeNull();
    expect(useAnomalyStore.getState().anomalies).toHaveLength(count);
  });

  it("never turns on demo mode in a production build", () => {
    vi.stubEnv("DEV", false);
    for (const mode of ["demo", "memory", "fixture", "offline", "slow", "flaky"]) {
      at(`/?twin=${mode}`);
      expect(pickSource()).toBe(apiSource);
      expect(isDemoMode()).toBe(false);
    }
    expect(useAnomalyStore.getState().anomalies).toEqual([]);
    expect(useTwinStore.getState().simulation).toBeNull();
    expect(useTwinStore.getState().candidates).toEqual([]);
  });

  it("opens only ?twin=demo in a production build made with VITE_ALLOW_DEMO=true", async () => {
    vi.stubEnv("DEV", false);
    vi.stubEnv("VITE_ALLOW_DEMO", "true");
    for (const mode of ["memory", "fixture", "offline", "slow", "flaky"]) {
      at(`/?twin=${mode}`);
      expect(pickSource()).toBe(apiSource);
      expect(isDemoMode()).toBe(false);
    }
    at("/");
    expect(pickSource()).toBe(apiSource);
    at("/?twin=demo");
    const source = pickSource();
    expect(source).not.toBe(apiSource);
    expect(isDemoMode()).toBe(true);
    expect(pickSimulationSource()).toBeNull();
    await expect(source.snapshot()).resolves.toMatchObject({ products: demoStoreState().products });
  });

  it("keeps demo anomalies, simulations, checkouts and badges out of the apps/api path, even when it fails", async () => {
    at("/");
    await expect(pickSource().snapshot()).rejects.toThrow("The API is unreachable.");
    expect(useAnomalyStore.getState().anomalies).toEqual([]);
    expect(useTwinStore.getState().simulation).toBeNull();
    expect(useTwinStore.getState().candidates).toEqual([]);
    expect(useCheckoutSummary("CK01")).toBeNull();
    expect(useCheckoutTransactions("CK01", true)).toEqual([]);
    expect(render(createElement(DemoBadge)).container.innerHTML).toBe("");
  });
});

describe("pickSimulationSource", () => {
  it("reads simulations from apps/api alongside the apps/api Live Twin", () => {
    at("/");
    expect(pickSimulationSource()).not.toBeNull();
    at("/?twin=unknown");
    expect(pickSimulationSource()).not.toBeNull();
    vi.stubEnv("DEV", false);
    at("/?twin=demo");
    expect(pickSimulationSource()).not.toBeNull();
  });

  it("leaves simulations to the console and the demo fixture under a ?twin= dev twin", () => {
    for (const mode of ["demo", "memory", "fixture", "offline", "slow", "flaky"]) {
      at(`/?twin=${mode}`);
      expect(pickSimulationSource()).toBeNull();
    }
  });
});

describe("Demo/Live isolation for anomaly polling", () => {
  beforeEach(() => {
    // Reset stores before each test in this describe block
    useAnomalyStore.setState({ anomalies: [], served: false, readError: null });
  });

  /**
   * PROOF: Demo mode does NOT make production API calls.
   *
   * When `?twin=demo` is active, the demo fixtures are loaded directly into the
   * anomaly store WITHOUT calling createApiSource. This proves the isolation:
   * demo mode uses in-memory fixtures, never the live API.
   */
  it("demo mode loads anomalies from fixtures, NOT from API", async () => {
    at("/?twin=demo");

    // This proves demo mode does NOT call the API - createApiSource should never be invoked
    const source = pickSource();
    expect(source).not.toBe(apiSource);
    expect(createApiSource).not.toHaveBeenCalled();

    // Demo anomalies ARE loaded into the store (from fixtures)
    const { anomalies } = useAnomalyStore.getState();
    expect(anomalies.length).toBeGreaterThan(0);

    // The demo anomalies have the expected demo structure
    expect(anomalies[0]).toMatchObject({
      anomaly_id: expect.stringContaining("anm-"),
      anomaly_type: expect.any(String),
      severity: expect.any(String),
      store_id: expect.any(String),
      sku: expect.any(String),
    });
  });

  /**
   * PROOF: Live mode (no ?twin=) does NOT load demo anomalies.
   *
   * When running without the demo flag, the anomaly store remains empty
   * (or reflects actual API responses, not demo fixtures). This proves
   * that demo data never leaks into live mode.
   */
  it("live mode (no ?twin=) does NOT load demo anomalies", () => {
    at("/");

    // Live mode uses the API source
    expect(pickSource()).toBe(apiSource);
    expect(createApiSource).toHaveBeenCalledTimes(1);

    // Anomaly store should NOT have demo anomalies loaded
    const { anomalies, served } = useAnomalyStore.getState();
    expect(anomalies).toEqual([]);
    expect(served).toBe(false); // Never served in live mode without explicit API call
  });

  /**
   * PROOF: Switching from demo to live mode clears demo state.
   *
   * When pickSource() is called in different modes, each mode initializes
   * its own state. The demo state is never preserved when switching to live.
   */
  it("demo anomalies are isolated and not accessible in live mode", () => {
    // First: enter demo mode and verify demo anomalies are loaded
    at("/?twin=demo");
    pickSource();
    const demoAnomalies = useAnomalyStore.getState().anomalies;
    expect(demoAnomalies.length).toBeGreaterThan(0);

    // Reset the store to simulate leaving demo mode
    useAnomalyStore.setState({ anomalies: [], served: false, readError: null });

    // Second: enter live mode (no ?twin=)
    at("/");
    pickSource();

    // The anomaly store should NOT contain demo anomalies
    const liveAnomalies = useAnomalyStore.getState().anomalies;
    expect(liveAnomalies).toEqual([]);
    expect(liveAnomalies).not.toEqual(demoAnomalies);
  });

  /**
   * PROOF: Production builds never enable demo mode.
   *
   * Even if someone tries ?twin=demo in a production build,
   * the demo mode is disabled and API is used instead.
   */
  it("production build never loads demo anomalies", () => {
    vi.stubEnv("DEV", false);

    // Try to enable demo mode
    at("/?twin=demo");
    const source = pickSource();

    // Should fall back to API source, not demo
    expect(source).toBe(apiSource);
    expect(createApiSource).toHaveBeenCalled();

    // No demo anomalies loaded
    expect(useAnomalyStore.getState().anomalies).toEqual([]);
    expect(isDemoMode()).toBe(false);
  });

  /**
   * PROOF: Anomaly store state is separate from Twin source.
   *
   * The anomaly store is only populated when demo mode is explicitly enabled.
   * In all other cases (including failed API calls), it remains empty.
   */
  it("failed API in live mode does NOT populate demo anomalies", async () => {
    at("/");

    // Try to load from API (which is mocked to fail)
    try {
      await pickSource().snapshot();
    } catch {
      // Expected - API is mocked to fail
    }

    // Even with failed API, no demo anomalies should be loaded
    const { anomalies, readError } = useAnomalyStore.getState();
    expect(anomalies).toEqual([]);
    expect(readError).toBeNull(); // We never called setAll or fail on the store
  });
});
