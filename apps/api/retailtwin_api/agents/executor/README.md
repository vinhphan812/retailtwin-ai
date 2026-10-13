# Executor

The guarded Executor is the only code that writes an agent decision to the Live Twin. See [ADR 0016](../../../../../docs/adr/0016-commit-only-through-a-signed-single-use-authorization.md).

```python
service = build_commit_service(live_twin, guard_audit, production=settings.is_production)
outcome = service.approve(decision)  # guard -> signed token -> Executor
```

`GuardedExecutor.commit(decision, token)` changes the Live Twin only when:

1. the token is present, untampered, unexpired, for exactly these actions in order, and unused;
2. No-Stale-Commit still allows the decision on fresh reads;
3. every touched SKU is still at the version the token names.

Each touched SKU is written once, one version ahead, with `expected_version`. Any failed write rolls the earlier ones back at a new version. A commit advances the store `v<N>`. The Executor never sees which model produced the decision.

| Code | Meaning |
| --- | --- |
| `COMMITTED` | All actions applied |
| `MISSING_TOKEN`, `INVALID_SIGNATURE`, `TOKEN_EXPIRED`, `ACTION_MISMATCH`, `TOKEN_REUSED`, `UNKNOWN_TOKEN` | Authorization refused; nothing written |
| `VERSION_STALE` and other guard codes | The context moved; nothing written, or rolled back |
| `EXECUTION_FAILED` | A write or the store version failed; rolled back |
| `ROLLBACK_FAILED` | A rollback write failed; logged at critical |
