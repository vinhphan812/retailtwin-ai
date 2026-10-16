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
 * - `mounted`: whether a component using this hook is currently mounted
 * - `inFlight`: whether a request is currently in progress (prevents duplicate requests)
 */
const pollingState = {
  mounted: false,
  inFlight: false,
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
    // Skip if another request is already in flight
    if (pollingState.inFlight) return;
    // Skip if no component is currently mounted (cleanup ran)
    if (!pollingState.mounted) return;

    pollingState.inFlight = true;

    try {
      const response = await client.anomalies();
      // Check mounted again after async in case component unmounted during request
      if (pollingState.mounted) {
        setAll(response);
      }
    } catch (error) {
      if (pollingState.mounted) {
        fail(i18n.t("anomaly.loadFailed"));
        notify.error(i18n.t("anomaly.loadFailed"), error);
      }
    } finally {
      pollingState.inFlight = false;
    }
  }, [client, setAll, fail]);

  // Store the poll function in ref for the visibility handler
  pollRef.current = doPoll;

  useEffect(() => {
    // Prevent duplicate pollers - if already mounted, skip
    if (pollingState.mounted) {
      return;
    }

    pollingState.mounted = true;

    // Initial poll
    doPoll();

    // If demo mode, still register cleanup (don't return early without cleanup)
    if (isDemo) {
      return () => {
        pollingState.mounted = false;
        if (pollingState.timerId) {
          clearInterval(pollingState.timerId);
          pollingState.timerId = null;
        }
      };
    }

    // Handle visibility change: pause when hidden, resume when visible
    const handleVisibilityChange = () => {
      if (document.hidden) {
        // Tab is hidden - clear the interval
        if (pollingState.timerId) {
          clearInterval(pollingState.timerId);
          pollingState.timerId = null;
        }
      } else {
        // Tab is visible - resume polling immediately if not already polling
        if (!pollingState.timerId && !pollingState.inFlight) {
          pollRef.current();
          pollingState.timerId = setInterval(pollRef.current, POLL_INTERVAL_MS);
        }
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);

    // Start interval polling
    pollingState.timerId = setInterval(doPoll, POLL_INTERVAL_MS);

    // Cleanup on unmount - this ALWAYS runs now, including in demo mode
    return () => {
      pollingState.mounted = false;
      pollingState.inFlight = false;
      if (pollingState.timerId) {
        clearInterval(pollingState.timerId);
        pollingState.timerId = null;
      }
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [doPoll, isDemo]);
}
