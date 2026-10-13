# Decision Context Guard (DCG)

Deterministic enforcement layer between a `Decision` and the Live Twin. See [ADR 0014](../../../../../docs/adr/0014-guard-each-decision-with-deterministic-gates.md).

```python
from retailtwin_api.guard.decision_context_guard import DecisionContextGuard, GuardPolicy

guard = DecisionContextGuard(live_twin_repository, GuardPolicy.from_env())
result = guard.evaluate(decision)  # DCGVerdictResult
```

Gates run in order and the first failure decides:

| # | Gate | Fails with |
| --- | --- | --- |
| 1 | decision integrity: one store, one correlation id, timezone-aware timestamps not in the future | `DENY INVALID_DECISION` |
| 2 | evidence sufficient and consistent | `DENY INSUFFICIENT_EVIDENCE` / `CONFLICTING_EVIDENCE` |
| 3 | context version of each touched SKU | `REFRESH_REQUIRED VERSION_STALE`; `DENY MISSING_CONTEXT_VERSION` / `UNKNOWN_ENTITY` |
| 4 | context freshness | `REFRESH_REQUIRED CONTEXT_EXPIRED` |
| 5 | physical feasibility (backroom, facings limit, slots) | `DENY INFEASIBLE_ACTION` |
| 6 | autonomous policy | `HUMAN_REVIEW POLICY_THRESHOLD`; `DENY ACTION_NOT_ALLOWED` |

A Live Twin read failure is `DENY TWIN_UNAVAILABLE`. Only `ALLOW` may lead to a commit authorization.

Possible outcomes:
- ALLOW
- DENY
- REFRESH_REQUIRED
- HUMAN_REVIEW

| Variable | Default |
| --- | --- |
| `RETAILTWIN_DCG_FRESHNESS_SECONDS` | 120 |
| `RETAILTWIN_DCG_MAX_FACINGS` | 12 |
| `RETAILTWIN_DCG_MAX_ACTIONS` | 5 |
| `RETAILTWIN_DCG_MAX_REPLENISH_UNITS` | 200 |

The guard reads the Live Twin, never writes it, and imports no model SDK.

`contract.schema.json` is the JSON shape of a `RetailTwinDecision`.

Core invariant: **No stale decision may commit to live state.**
