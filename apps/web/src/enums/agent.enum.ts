/** Where a run stands on one stage of the control loop, as its entries show it. */
export const STAGE_STATUS = {
  /** The run has an entry for the stage and has moved on, or has finished. */
  Done: "done",
  /** The stage of the run's latest entry, while the run has not reached VERIFY. */
  Active: "active",
  /** No entry for the stage yet. Never filled in by the UI. */
  Pending: "pending",
} as const;
export type StageStatus = (typeof STAGE_STATUS)[keyof typeof STAGE_STATUS];

/** How the Operations timeline shows the agent's activity. */
export const ACTIVITY_VIEW = {
  /** One card per run, with the control loop as a stepper. */
  Runs: "runs",
  /** Every entry as one line, oldest first. */
  Log: "log",
} as const;
export type ActivityView = (typeof ACTIVITY_VIEW)[keyof typeof ACTIVITY_VIEW];
export const ACTIVITY_VIEWS: readonly ActivityView[] = Object.values(ACTIVITY_VIEW);

/** Where the Live timeline's `GET /agent/events` feed stands. */
export const AGENT_FEED_STATE = {
  /** Nothing reads it: the demo, or a `?twin=` dev twin. */
  Off: "off",
  /** The first read has not answered yet. */
  Loading: "loading",
  /** The last read answered. */
  Ready: "ready",
  /** The last read failed; the timeline keeps the events it had. */
  Failed: "failed",
} as const;
export type AgentFeedState = (typeof AGENT_FEED_STATE)[keyof typeof AGENT_FEED_STATE];

/** Why the timeline is empty, or why it is not moving: shown in its empty state and above it. */
export const TIMELINE_STATE = {
  /** The feed answered and has served no event. */
  NoEvents: "no_events",
  /** The last read of the feed failed. */
  ApiFailed: "agent_api_failed",
  /** The browser is offline, or the Live Twin's feed dropped. */
  Disconnected: "disconnected",
  /** The demo: nothing plays until a replay is started. */
  ReplayIdle: "replay_idle",
  /** Waiting for the feed's first answer. */
  Loading: "loading",
} as const;
export type TimelineState = (typeof TIMELINE_STATE)[keyof typeof TIMELINE_STATE];
