# Architecture decision log

An architecture decision record (ADR) captures one important architecture decision, the context in which it was made, and the consequences. The log is the set of those records.

Format reference: [architecture-decision-record](https://github.com/architecture-decision-record/architecture-decision-record). Records use the Michael Nygard sections: Status, Context, Decision, Consequences.

`docs/ARCHITECTURE.md` describes the system. This directory records why a choice was made and which pull request adopted it.

## Pull request rule

Every pull request names the ADR it tracks.

- A change that makes a new architecture decision adds the next record in the same pull request.
- A change that replaces an accepted decision adds a new record and marks the previous one `Superseded`. Do not rewrite the accepted history.
- A change that only implements an accepted decision links that record.
- A change with no architectural effect writes `N/A` and one line saying why.

Write a new record when the change affects a public schema, a state transition, a tool or action contract, a security invariant, a storage or execution boundary, or another choice a later reader would otherwise re-open.

Skip a new record when an accepted ADR already covers the choice, or when the change is a small fix with no architectural effect.

## File convention

`NNNN-imperative-verb-phrase.md`

- `0001-record-architecture-decisions-in-pull-requests.md`
- Copy `template.md` for the next record and use the next free number.
- One decision per file.
- Status is `Proposed`, `Accepted`, `Superseded`, or `Deprecated`.

## Index

| ADR                                                                     | Title                                                       | Status   |
| ----------------------------------------------------------------------- | ----------------------------------------------------------- | -------- |
| [0001](0001-record-architecture-decisions-in-pull-requests.md)          | Record architecture decisions in pull requests              | Accepted |
| [0002](0002-render-store-entities-as-named-primitives.md)               | Render store entities as named primitives                   | Accepted |
| [0003](0003-serve-store-reads-through-the-api.md)                       | Serve store reads through the API                           | Accepted |
| [0004](0004-keep-the-cloud-foundation-on-free-tier.md)                  | Keep the cloud foundation on the free tier                  | Accepted |
| [0005](0005-land-each-normalized-store-event-once.md)                   | Land each normalized store event once                       | Accepted |
| [0006](0006-use-heroui-v2-for-app-status-ui.md)                         | Use HeroUI v2 for app status UI                             | Accepted |
| [0007](0007-keep-store-layout-static-until-the-twin-serves-geometry.md) | Keep the store layout static until the twin serves geometry | Accepted |
| [0009-0034](0009-0034-cloud-run-deployment.md)                          | Cloud Run deployment runbook                                | Accepted |
| [0011-0015](0011-0015-agent-orchestrator.md)                            | Agent Orchestrator implementation                           | Accepted |
| [0016-0017](0016-0017-dcg-no-stale-commit.md)                           | Decision Context Guard (DCG) & No-Stale-Commit              | Accepted |
| [0018](0018-guarded-executor.md)                                        | Guarded Executor implementation                             | Accepted |
| [0033](0033-kpi-evaluator.md)                                           | Simulation KPI Evaluator                                    | Accepted |
| [0033](0033-simulation-service.md)                                      | Simulation Service                                          | Accepted |
| [0037](0037-agent-activity-timeline.md)                                 | Agent Activity Timeline Implementation                      | Proposed |
| [0041](0041-demo-controller.md)                                         | Demo Controller Implementation                              | Accepted |
| [Twin](twin-service.md)                                                 | Twin Service (Live & Simulation)                            | Accepted |

## Categories

| Category           | ADRs            |
| ------------------ | --------------- |
| **Foundation**     | 0001-0007       |
| **Infrastructure** | 0009-0034       |
| **Agent/DCG**      | 0011-0018, 0037 |
| **Simulation**     | 0033            |
| **Demo**           | 0041            |
