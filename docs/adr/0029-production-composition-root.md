# 0029. Production composition root for GCP analytics, Vertex and durable decisions

Date: 2026-10-17

## Status

Proposed (partial — isolated from #231 pipeline)

## Context

Issue [#214](https://github.com/vinhphan812/retailtwin-ai/issues/214)

PR #244 attempted to add a production composition root, but the review found:
1. The PR overlapped with unmerged #231 (durable pipeline)
2. Readiness semantics were incomplete — didn't distinguish configured from operational

This isolated implementation adds only the readiness semantics without the #231 dependency.

## Problem

The current `/ready` endpoint returns basic store status but does NOT expose:
- Which analytics adapters are bound (BigQuery vs unavailable scaffolds)
- AI workflow state (enabled/disabled/misconfigured)
- Backend identities for release-gate verification

This prevents the release-gate from asserting the production adapters are actually bound.

## Decision

Add readiness state fields to `/ready` response:

1. **backend_identities**: dict of adapter bindings (live_twin, analytics, LLM)
   - Values are class names and sources — NEVER credentials
   
2. **ai_state**: tri-state for AI workflow
   - `ai_ready`: AUTONOMY_ENABLED=true AND Vertex provider built
   - `ai_disabled`: AUTONOMY_ENABLED=false by config
   - `ai_unconfigured`: AUTONOMY_ENABLED=true but Vertex build failed

3. **ai_reason**: stable reason code for logs/metrics

4. **analytics_readiness**: BigQuery probe result
   - `not_applicable`: dev/test (no probe)
   - `bigquery_probe_ok`: credentials + IAM + schema verified
   - `bigquery_unreachable`: probe failed

## Scope (this PR)

- [x] Add readiness fields to ReadyResponse schema
- [x] Update /ready endpoint to expose new fields
- [x] Collect backend_identities in create_app
- [x] Emit composition.ready log with identities
- [x] Add contract tests for new fields

## Out of Scope (deferred to #231)

- Full composition factory with get_persistence()
- BigQuery probe implementation
- Durable Firestore adapters
- Production backend enforcement (memory/fixture rejection)

## Implications

The release-gate can now assert:
- `ai_state != "ai_unconfigured"` before promoting to production
- `analytics_readiness.reason == "bigquery_probe_ok"` when BigQuery is expected
- `backend_identities` match expected adapter classes

## Notes

- Analytics readiness is `not_applicable` on main because main uses unavailable scaffolds
- The full BigQuery probe and composition factory require #231's persistence module
- This isolated PR demonstrates the readiness contract without the #231 dependency
