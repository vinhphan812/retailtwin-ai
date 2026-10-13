# 0016. Commit only through a signed single-use authorization

Date: 2026-10-13

## Status

Accepted

## Context

Issue #18 needs a short-lived commit authorization bound to the decision id, the context hash and version, the exact allowed actions and an expiry. The Executor must check the token, the action match and replay before calling the live action service. The test scenario covers a valid, expired, altered-action, reused and missing token, and only the valid one changes the Live Twin.

ADR 0014 supplies the guard and its context hash. ADR 0015 supplies `NoStaleCommit` and its `CommitBinding`. #85 forbids the Executor from knowing the model provider.

The approve route (#127) returned `ALLOW` and `committed` without a guard or a write. The API served a read-only fixture, so no commit could be seen. The Planner (#14) is not on `main`, so no Decision is recorded for a simulation.

Alternatives considered:

- **Opaque nonce with all state on the server.** This would work in one process, but a token copied between processes could not be checked without that store.
- **Building a Decision from `SimulationDetail` at approval time.** This would invent evidence, because the investigator never read it.
- **Applying actions one by one without rollback.** ARCHITECTURE §8 says there is no silent partial commit.

## Decision

### Authorization

`CommitAuthorizer` in `guard/decision_context_guard/authorization.py` issues a `SignedAuthorization` only from a `CommitBinding`. The token fields are:

- decision id and store;
- context hash;
- the SHA-256 of each canonical action, in order;
- the live version of each touched SKU;
- a 128-bit random nonce;
- issue time;
- expiry: `RETAILTWIN_COMMIT_TOKEN_TTL_SECONDS` (default 30), never past the binding's expiry.

The token is signed with HMAC-SHA256 under `RETAILTWIN_COMMIT_SIGNING_KEY`.

- **Production without a key:** nothing is issued, and the approve route returns `503 commit_unavailable`.
- **Outside production without a key:** a random per-process key is generated and a warning is logged.

`redeem(decision, token)` checks the following in order. A failure after the signature check revokes the nonce.

| Check | Refusal |
| --- | --- |
| Token present | `MISSING_TOKEN` |
| Signature valid | `INVALID_SIGNATURE` |
| Not past expiry | `TOKEN_EXPIRED` |
| Same decision id and the same ordered action hashes | `ACTION_MISMATCH` |
| Nonce consumed once in the `AuthorizationLedger` | `TOKEN_REUSED` / `UNKNOWN_TOKEN` |

### Executor

`GuardedExecutor.commit(decision, token)` in `agents/executor/executor.py` is the only production code that calls `upsert_inventory` or `bump_store_version`. An e2e AST test enforces this. It runs these steps in order:

1. Redeem the token.
2. Run `NoStaleCommit.recheck` on fresh reads.
3. Re-read each touched SKU and refuse with `VERSION_STALE` if any is not at the token's version.
4. Write each touched SKU once, one version ahead, with `expected_version` set to the token's version.
5. Advance the store `v<N>`.

Two rules apply to the writes:

- **Rollback.** A `TwinConflict` on any write (`VERSION_STALE`) or any other failure (`EXECUTION_FAILED`) rolls back earlier writes. A rollback restores the previous content at a new version, so nothing built on the rolled-back state looks current. A failed rollback is `ROLLBACK_FAILED` and is logged at critical.
- **Move.** A move changes only `slot_id`. Slot ids are unique, and the layout maps a slot to its shelf.

### Route

`CommitService.approve(decision)` chains authorize, issue and commit.

`POST /simulations/{id}/approve` keeps its version precheck and open-status check. It then reads the Decision from an injected `DecisionSource`.

- Production has none and returns `503 decisions_unavailable`.
- If no decision exists for the simulation, the route returns `DENY DECISION_UNAVAILABLE`.

Only a committed outcome sets the simulation to `committed` and refreshes the live context version. The response adds `detail_code` (the guard or Executor code) and `guard` (the `DCGVerdictResult` with its checks). Refusals map to the existing review reasons:

| Outcome | Review reason |
| --- | --- |
| `REFRESH_REQUIRED` | `VERSION_STALE` |
| `DENY` | `DCG_DENY` |
| `HUMAN_REVIEW` | `DCG_HUMAN_REVIEW` |
| Execution failure | `EXECUTION_FAILED` |

`/reject` never reaches the guard and now records `rejected`.

### Live Twin backend

`LIVE_TWIN_BACKEND` chooses the store the routes read:

- `memory` (default): an `InMemoryTwinRepository` seeded from the fixture, with fixture product versions.
- `firestore`: `FirestoreLiveTwinRepository`.
- `fixture`: the old read-only adapter, with no commit path.

`LiveTwinRepository` gains `bump_store_version`.

## Consequences

A valid approval now changes the Live Twin, the next `GET /store` shows it, and the store version advances. Every refusal path is tested to leave Live unchanged.

Limits and follow-ups:

- **Process memory.** The ledger, guard audit and in-memory twin live in process memory. Several Cloud Run instances would each have their own twin and ledger until the Firestore backend is used. Tokens never leave the process that issued them.
- **No production `DecisionSource`.** It must arrive with the Planner (#14) or orchestrator.
- **Firestore concurrency is not real yet.** The Firestore adapter sends `currentDocument.requireVersion`, which the Firestore REST API does not define; only the fake transport honors it. Until #6 uses an `updateTime` or transaction precondition, `expected_version` is enforced in memory only.
- **Firestore auth does not work on Cloud Run.** The adapter gets tokens from the `gcloud` CLI, which a Cloud Run container does not have.
- **Web contract drift.** The web review contract (`approve`/`reject`, lowercase reasons) still differs from the API (`approved`/`rejected`), as it did before this change.
- **Still to do:** Verifier (#19), re-plan (#20) and the BigQuery audit (#35).

- Pull request: https://github.com/vinhphan812/retailtwin-ai/pull/141
- Issue: #18
- Supersedes:
- Superseded by:
