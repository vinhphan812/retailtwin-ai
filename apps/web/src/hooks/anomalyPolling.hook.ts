import { useEffect, useRef, useCallback } from "react";
import i18n from "@/i18n";
import { defaultClient } from "@/core/api/client";
import { isDemoMode } from "@/core/twin/demoMode";
import { demoClient } from "@/fixtures/demo/commerce";
import { useAnomalyStore } from "@/state/anomaly.store";
import { notify } from "@/core/notify";

/** Polling interval in milliseconds (30 seconds). */
const POLL_INTERVAL_MS = 30_000;

/**
 * Start/stop state to prevent duplicate pollers.
 * Uses a ref to track if polling is active.
 */
const pollingState = {
  active: false,
  timerId: null as ReturnType<typeof setInterval> | null,
};

/**
 * Anomaly polling hook.
 * 
 * Polls `GET /anomalies` and hydrates the anomaly store.
 * - In demo mode (`?twin=demo`), loads demo anomalies once and stops.
 * - In production mode, polls every 30 seconds.
 * - Pauses polling when the tab is hidden, resumes when visible.
 * - Cleans up on unmount.
 * - Prevents duplicate pollers with a singleton pattern.
 */
export function useAnomalyPolling(): void {
  const setAll = useAnomalyStore((state) => state.setAll);
  const fail = useAnomalyStore((state) => state.fail);
  const client = isDemoMode() ? demoClient : defaultClient;
  
  const isDemo = isDemoMode();
  const pollRef = useRef<() => void>(() => {});

  const doPoll = useCallback(async () => {
    if (pollingState.active) return;
    
    try {
      const response = await client.anomalies();
      setAll(response);
    } catch (error) {
      fail(i18n.t("anomalies.loadFailed"));
      notify.error(i18n.t("anomalies.loadFailed"), error);
    }
  }, [client, setAll, fail]);

  // Store the poll function in ref for the visibility handler
  pollRef.current = doPoll;

  useEffect(() => {
    // Prevent duplicate pollers
    if (pollingState.active) {
      return;
    }

    pollingState.active = true;

    // Initial poll
    doPoll();

    // If demo mode, don't start interval polling
    if (isDemo) {
      return;
    }

    // Start interval polling
    pollingState.timerId = setInterval(doPoll, POLL_INTERVAL_MS);

    // Handle visibility change: pause when hidden, resume when visible
    const handleVisibilityChange = () => {
      if (document.hidden) {
        // Tab is hidden - clear the interval
        if (pollingState.timerId) {
          clearInterval(pollingState.timerId);
          pollingState.timerId = null;
        }
      } else {
        // Tab is visible - resume polling immediately, then set interval
        pollRef.current();
        pollingState.timerId = setInterval(pollRef.current, POLL_INTERVAL_MS);
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);

    // Cleanup on unmount
    return () => {
      pollingState.active = false;
      if (pollingState.timerId) {
        clearInterval(pollingState.timerId);
        pollingState.timerId = null;
      }
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [doPoll, isDemo]);
}
