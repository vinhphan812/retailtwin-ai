# Test Suite

## Structure

| Directory | Runner | Purpose |
|---|---|---|
| `apps/api/tests/` | pytest | FastAPI boundary: health, store reads, inventory, events |
| `apps/web/src/` | Vitest | React components, API client, scene rendering |

## Running tests locally

### API

```bash
cd apps/api
pip install -e ".[dev]"
pytest
```

With coverage:

```bash
pytest --cov=retailtwin_api --cov-report=term --cov-report=xml --cov-branch
# HTML report: pytest --cov=retailtwin_api --cov-report=html
# Open: apps/api/htmlcov/index.html
```

Coverage thresholds (two-step):
1. **Non-regression floor** — measured baseline (no new regressions below this):
   - Line/statement: **89%**
   - Branch: **85%**
2. **Target threshold** — required before Foundation Gate #10:
   - Line/statement: **>= 80%**
   - Branch: **>= 75%**

See `apps/api/pyproject.toml` `[tool.coverage.run]` for the full omit/include list.
Key exclusions: `.venv/`, `__pycache__/`, `.pytest_cache/`, `__main__.py`.

### Web

```bash
cd apps/web
npm ci
npm test
```

With coverage:

```bash
npm run test:coverage
# Coverage reports: apps/web/coverage/
#   coverage/lcov-report/index.html -- HTML
#   coverage/lcov.info -- LCOV
#   coverage/cobertura-coverage.xml -- Cobertura XML
```

Coverage thresholds (two-step):
1. **Non-regression floor** -- measured baseline:
   - Statements/lines: **91%**
   - Branches: **91%**
2. **Target threshold** -- required before Foundation Gate #10:
   - Statements/lines: **>= 80%**
   - Branches: **>= 75%**

The Vitest config (`apps/web/vite.config.ts`) excludes:
- `src/**/*.d.ts` -- type declarations
- `src/**/types.ts` -- type-only modules
- `src/*-env.d.ts` -- ambient environment declarations

### Critical-path modules (future)

When the following modules are implemented, they are subject to elevated thresholds
(line >= 90%, branch >= 85%):

- `guard/decision-context-guard/` -- Decision Context Guard
- `services/executor/` -- Executor
- `services/twin/` -- Digital Twin mutation paths
- `services/simulation/` -- Simulation Twin
- `services/verifier/` -- Verifier
- Event idempotency (`apps/api/retailtwin_api/events.py`)

Until those modules exist, the non-regression floor applies to `apps/api` as a whole.

## CI

Coverage runs in GitHub Actions on every push to `main` and on every pull request
touching the respective application directory:

- `.github/workflows/api.yml` -- Python API
- `.github/workflows/web.yml` -- TypeScript web

Artifacts:
- `api-coverage` -- `coverage.xml` from pytest-cov
- `web-coverage` -- full `coverage/` directory from Vitest

## Policy

- All PRs must keep coverage at or above the non-regression floor.
- Coverage may not decrease without a tracked justification in the PR.
- Coverage decrease below floor blocks merge.
- Critical-path threshold applies to any module that implements DCG, Executor,
  authorization, event idempotency, simulation-vs-live isolation, verifier, or
  rollback logic.
