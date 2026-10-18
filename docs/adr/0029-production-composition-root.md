# 0029. Production composition root for GCP analytics, Vertex and durable decisions

Date: 2026-10-17

## Status

Accepted (rev. 2 — review #244 re-review applied)

## Context

Issue [#214](https://github.com/vinhphan812/retailtwin-ai/issues/214)
audit found that `apps/api/retailtwin_api/main.py` still initialises
analytics with `unavailable_analytics_repositories()` and only
constructs the Vertex provider when `AUTONOMY_ENABLED=true`. Production
falls through to the unavailable adapters and the in-memory LLM
fallback unless every environment variable is correct. The
`scripts/verify-cloud-preflight.sh` checks the runtime matrix; the
release-gate check on Cloud Run has no way to assert that the running
revision is actually using the production adapters instead of the
unavailable ones.

PR #231 (#217 durable pipeline) lands `get_persistence(settings)` for
the durable decision / simulation / agent-activity / activation-LEDger
adapters. The analytics adapters (`BigQueryAnomalyRepository`,
`BigQueryRevenueRepository`, `BigQueryPromotionRepository`) already
exist on main but no factory wires them into `create_app()`. The
Vertex provider is constructed lazily inside `create_app` only when
autonomy is enabled.

Review #244 (re-review on PR head `431c5ee`) raised three contract
gaps the original factory did not close:

1. `/ready` exposed `live_twin=memory`, `analytics_dataset=…`,
   `llm_provider=vertex_gemini` purely as class/identity strings; the
   BigQuery probe actually touched neither the dataset nor the service
   account. The release-gate had no way to distinguish a healthy
   production deploy from one whose ADC silently could not reach
   BigQuery.
2. `LIVE_TWIN_BACKEND=memory` and `LIVE_TWIN_BACKEND=fixture` are
   explicitly accepted for `APP_ENV=production`. The day-0 demo
   backends are in-process and not durable; Cloud Run drains every
   write the moment the revision restarts. Production live-action
   deployments must point at Firestore; review #3 said the factory
   should fail closed.
3. `AUTONOMY_ENABLED=false` skips the Vertex provider and `/ready`
   still reports `ready=true`. The release gate cannot distinguish
   intentional disablement (`ai_disabled`) from a misconfigured
   deploy where the Vertex builder failed (`ai_unconfigured`).

## Decision

A new module `apps/api/retailtwin_api/composition.py` exposes one
factory:

```python
def build_composition(
    settings: Settings,
    *,
    store_view_fn: Callable[[], Any] | None = None,
    activity: Any | None = None,
    runner: _CommandRunnerLike | None = None,
) -> Composition
```

The returned `Composition` dataclass bundles every cross-cutting
adapter the Cloud Run process needs:

- `live_twin_repository` — Firestore-backed
  (`FirestoreLiveTwinRepository`) when `LIVE_TWIN_BACKEND=firestore`.
  `memory` and `fixture` are accepted for `APP_ENV in {development,
  test, staging}` only; production rejects them with
  `CompositionError("'memory' / 'fixture' backend not allowed in
  production")`. The day-0 demo backends are not durable; production
  live-action deployments must point at Firestore. Staging keeps the
  in-process twin so the operator can flip the env var during cutover.
- `analytics_repositories` — `(anomalies, revenue, promotions,
  checkouts)` from the BigQuery-backed factories when
  `app_env in {"production", "staging"}`; the unavailable scaffolds
  otherwise. A BigQuery probe runs ahead of adapter construction;
  any IAM / connect / schema failure surfaces as a
  `CompositionReadiness(reason="bigquery_unreachable")` so `/ready`
  can flag a degraded composition without crashing the process.
- `analytics_readiness` — a `CompositionReadiness` dataclass
  (`ready`, `reason`, `source`, `identity`, `detail`) describing
  outcome of the BigQuery probe. `ready=true` with
  `reason="not_applicable"` outside production/staging.
- `llm_provider` — `vertex_gemini` via ADC when Vertex builds
  successfully; `None` (with `ai_state="ai_disabled"`) when
  `AUTONOMY_ENABLED=false`. The shipped Vertex builder is used
  (ADR 0020); production construction does not fall back to the
  fake provider on builder failure and raises `CompositionError`
  (so the lifespan refuses to start).
- `ai_state` — three-state AI workflow readiness
  (`ai_ready` / `ai_disabled` / `ai_unconfigured`). `ai_ready` —
  Vertex built; `ai_disabled` — `AUTONOMY_ENABLED=false` by config;
  `ai_unconfigured` — `AUTONOMY_ENABLED=true` but the Vertex
  builder raised (`CompositionError` reaches `create_app`, the
  lifespan refuses to start). Misconfiguration is never masked as
  intentional disablement.
- `ai_reason` — stable string the release-gate can match on
  (`vertex_built` / `autonomy_disabled_by_config` /
  `vertex_builder_failed`).
- `durable_adapters` — `get_persistence(settings, ...)` returning the
  Firestore-backed decision / simulation / agent-activity /
  activation-ledger bundle when `LIVE_TWIN_BACKEND=firestore`; the
  in-process adapters otherwise.

The BigQuery probe runs `bq query --nouse_legacy_sql --format=json
SELECT 1 AS ok FROM \`<project>.<dataset>.sales_events\` LIMIT 1`
against each canonical table. The same `SubprocessRunner` (ADC
credentials) is used by the analytics adapter and the probe, so the
probe exercises the exact CLI path the adapter will use at request
time. The factory exposes the runner as an optional `runner`
argument so tests can fake the `bq query` CLI call without invoking
`gcloud`.

`create_app()` calls `build_composition(resolved)` exactly once at
startup, binds every field into `app.state`, and logs a single
structured `composition.ready` event with the backend identities
(never credentials). When the production factory raises
`CompositionError`, the lifespan refuses to start and the Cloud Run
revision reports `503 unhealthy` until the operator fixes the
configuration. The fallback paths that were present in `create_app`
for tests remain, but they require
`app_env not in {"production", "staging"}`.

The factory is the **single source of truth** for which adapter each
environment binds. Routes read from `app.state` and never construct
adapters on their own.

## Consequences

- `main.py` `create_app()` no longer calls
  `unavailable_analytics_repositories()`; it reads
  `composition.analytics_repositories`. The route handlers stay the
  same.
- `main.py` `create_app()` rejects `APP_ENV=production` +
  `LIVE_TWIN_BACKEND in {memory, fixture}`; the lifespan refuses to
  start. Production live-action deployments must set
  `LIVE_TWIN_BACKEND=firestore`.
- New contract tests in `apps/api/tests/test_composition.py`:
  - `test_dev_uses_unavailable_analytics_and_memory_live_twin`
  - `test_production_binds_bigquery_backed_analytics`
  - `test_production_does_not_silently_fall_back_to_fake_provider`
  - `test_production_with_no_autonomy_does_not_construct_provider`
  - `test_production_rejects_memory_backend` (review blocker #3)
  - `test_production_rejects_fixture_backend` (review blocker #3)
  - `test_development_allows_memory_backend` (negative test)
  - `test_staging_allows_memory_backend` (cut-over contract)
  - `test_resolve_bigquery_probe_returns_identity_on_success`
    (review blocker #2)
  - `test_resolve_bigquery_probe_marks_unreachable_on_permission_denied`
    (review blocker #2)
  - `test_composition_build_with_unreachable_bigquery_marks_degraded_not_ready`
    (review blocker #2)
  - `test_autonomy_disabled_marks_ai_disabled_not_unconfigured`
    (review blocker #4)
  - `test_autonomy_enabled_with_vertex_ready_marks_ai_ready`
    (review blocker #4)
  - `test_autonomy_enabled_with_vertex_unavailable_fails_closed`
    (review blocker #4)
  - `test_get_ready_surfaces_ai_state_and_analytics_readiness`
- `GET /ready` is enriched with `composition.backend_identities()`
  plus `ai_state`, `ai_reason`, and `analytics_readiness` so the
  release-gate and Cloud Run readiness probe can assert the
  canonical production adapters are bound AND distinguish
  intentional AI disablement from a misconfigured deploy.
- A new typed `CompositionError` is exported from
  `retailtwin_api.composition` and surfaces as
  `503 composition_unavailable` in routes that need a specific
  adapter.
- The factory is the single place to swap to the day-1
  Terraform-provisioned service accounts and the
  `LIVE_TWIN_BACKEND=firestore` deploy env (issue #143).

- Pull request: <https://github.com/vinhphan812/retailtwin-ai/pull/244>
- Issue: <https://github.com/vinhphan812/retailtwin-ai/issues/214>
- Supersedes:
- Superseded by:
