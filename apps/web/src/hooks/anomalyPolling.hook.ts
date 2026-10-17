import { useEffect, useRef, useCallback, createContext, useContext, useMemo } from "react";
import i18n from "@/i18n";
import { defaultClient } from "@/core/api/client";
import { isDemoMode } from "@/core/twin/demoMode";
import { demoClient } from "@/fixtures/demo/commerce";
import { useAnomalyStore } from "@/state/anomaly.store";
import { notify } from "@/core/notify";

/** Polling interval in milliseconds (30 seconds). */
const POLL_INTERVAL_MS = 30_000;

/**
 * Shared polling state managed by React Context.
 * This allows multiple components to coordinate polling without
 * the issues of a module-level singleton.
 */
type PollingState = {
  active: boolean;
  timerId: ReturnType<typeof setInterval> | null;
  startPolling: (pollFn: () => void) => void;
  stopPolling: () => void;
  pausePolling: () => void;
  resumePolling: (pollFn: () => void) => void;
};

const PollingContext = createContext<PollingState | null>(null);

/**
 * Module-level singleton for backward compatibility.
 * Used as fallback when PollingProvider is not in the tree.
 */
const singletonState = {
  active: false,
  timerId: null as ReturnType<typeof setInterval> | null,
};

/**
 * Provides shared polling state for anomaly polling.
 * Uses context to ensure only one poller runs at a time across
 * all components using this provider, while properly handling
 * cleanup when components unmount.
 * Falls back to singleton state when no provider is present.
 */
function usePollingState(): PollingState {
  const context = useContext(PollingContext);
  if (context) {
    return context;
  }

  // Fallback to singleton state for backward compatibility (tests, no provider)
  return useMemo<PollingState>(
    () => ({
      get active() {
        return singletonState.active;
      },
      set active(value: boolean) {
        singletonState.active = value;
      },
      get timerId() {
        return singletonState.timerId;
      },
      set timerId(value: ReturnType<typeof setInterval> | null) {
        singletonState.timerId = value;
      },
      startPolling(pollFn: () => void) {
        if (singletonState.timerId) return;
        pollFn();
        singletonState.timerId = setInterval(pollFn, POLL_INTERVAL_MS);
      },
      stopPolling() {
        singletonState.active = false;
        if (singletonState.timerId) {
          clearInterval(singletonState.timerId);
          singletonState.timerId = null;
        }
      },
      pausePolling() {
        if (singletonState.timerId) {
          clearInterval(singletonState.timerId);
          singletonState.timerId = null;
        }
      },
      resumePolling(pollFn: () => void) {
        if (!singletonState.timerId && !singletonState.active) {
          pollFn();
          singletonState.timerId = setInterval(pollFn, POLL_INTERVAL_MS);
        }
      },
    }),
    []
  );
}

/**
 * PollingProvider component that manages shared polling state.
 * Wrap your application with this to enable coordinated polling.
 */
export function PollingProvider({ children }: { children: React.ReactNode }) {
  const stateRef = useRef({
    active: false,
    timerId: null as ReturnType<typeof setInterval> | null,
  });

  const pollingState = useMemo<PollingState>(
    () => ({
      get active() {
        return stateRef.current.active;
      },
      set active(value: boolean) {
        stateRef.current.active = value;
      },
      get timerId() {
        return stateRef.current.timerId;
      },
      set timerId(value: ReturnType<typeof setInterval> | null) {
        stateRef.current.timerId = value;
      },
      startPolling(pollFn: () => void) {
        if (stateRef.current.timerId) return;
        pollFn();
        stateRef.current.timerId = setInterval(pollFn, POLL_INTERVAL_MS);
      },
      stopPolling() {
        stateRef.current.active = false;
        if (stateRef.current.timerId) {
          clearInterval(stateRef.current.timerId);
          stateRef.current.timerId = null;
        }
      },
      pausePolling() {
        if (stateRef.current.timerId) {
          clearInterval(stateRef.current.timerId);
          stateRef.current.timerId = null;
        }
      },
      resumePolling(pollFn: () => void) {
        if (!stateRef.current.timerId && !stateRef.current.active) {
          pollFn();
          stateRef.current.timerId = setInterval(pollFn, POLL_INTERVAL_MS);
        }
      },
    }),
    []
  );

  return (
    <PollingContext.Provider value={pollingState}>{children}</PollingContext.Provider>
  );
}

/**
 * Anomaly polling hook.
 *
 * Polls `GET /anomalies` and hydrates the anomaly store.
 * - In demo mode (`?twin=demo`), loads demo anomalies once and stops.
 * - In production mode, polls every 30 seconds.
 * - Pauses polling when the tab is hidden, resumes when visible.
 * - Cleans up on unmount.
 * - Uses React Context to coordinate polling across multiple components,
 *   preventing conflicts while allowing proper cleanup.
 */
export function useAnomalyPolling(): void {
  const setAll = useAnomalyStore((state) => state.setAll);
  const fail = useAnomalyStore((state) => state.fail);
  const client = isDemoMode() ? demoClient : defaultClient;

  const isDemo = isDemoMode();
  const pollRef = useRef<() => void>(() => {});

  // Use the shared polling state via context
  const pollingState = usePollingState();

  const doPoll = useCallback(async () => {
    try {
      pollingState.active = true;
      const response = await client.anomalies();
      setAll(response);
    } catch (error) {
      fail(i18n.t("anomalies.loadFailed"));
      notify.error(i18n.t("anomalies.loadFailed"), error);
    } finally {
      pollingState.active = false;
    }
  }, [client, setAll, fail, pollingState]);

  // Store the poll function in ref for the visibility handler
  pollRef.current = doPoll;

  useEffect(() => {
    // Initial poll - runs immediately
    doPoll();

    // If demo mode, don't start interval polling
    if (!isDemo) {
      // Use the shared polling state to start interval
      pollingState.startPolling(doPoll);
    }

    // Handle visibility change: pause when hidden, resume when visible
    const handleVisibilityChange = () => {
      if (document.hidden) {
        pollingState.pausePolling();
      } else {
        pollingState.resumePolling(pollRef.current);
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);

    // Cleanup on unmount - use the shared state for cleanup
    return () => {
      pollingState.stopPolling();
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [doPoll, isDemo, pollingState]);
}

/**
 * Export pollingState for backward compatibility with tests.
 * This is the singleton interface that tests expect.
 * Note: When PollingProvider is used, this singleton is NOT used.
 */
export const pollingState = {
  get active() {
    return singletonState.active;
  },
  set active(value: boolean) {
    singletonState.active = value;
  },
  get timerId() {
    return singletonState.timerId;
  },
  set timerId(value: ReturnType<typeof setInterval> | null) {
    singletonState.timerId = value;
  },
};
