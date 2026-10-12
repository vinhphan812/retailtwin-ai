# RetailTwin AI — Developer & Agent Guide

RetailTwin AI is a context-guarded autonomous 3D retail digital twin built for the Google Cloud AI Builder Cup 2026.

## Target Control Loop

```
OBSERVE → DETECT → INVESTIGATE → PLAN → SIMULATE → GUARD → ACT → VERIFY
```

## Repository Structure

- `apps/api/` — FastAPI backend & demo orchestrator
- `apps/web/` — React 18, TypeScript, React Three Fiber 3D store UI
- `services/twin/` — Canonical Live & Simulation Twin state
- `services/simulation/` — Simulation service & KPI evaluator
- `guard/decision_context_guard/` — Deterministic Decision Context Guard (DCG)
- `agents/` — Autonomous agent responsibilities (Observer, Investigator, Planner, Executor, Verifier)
- `docs/` — Comprehensive documentation (getting-started, architecture, development, api, demo, adr)
- `tests/` — Cross-cutting test guidance & E2E tests

## Commands

### Backend (FastAPI)
```bash
cd apps/api
python -m venv .venv
source .venv/Scripts/activate  # On Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
pytest
```

### Frontend (React + Vite)
```bash
cd apps/web
npm ci
npm test
npm run build
```

## Safety Invariants (Non-Negotiable)

1. **Digital Twin owns truth** — The LLM never owns operational truth.
2. **No direct Live Twin writes** — Gemini and browser code must never directly mutate the Live Twin.
3. **Isolated simulation paths** — Simulation state and Live Twin state use separate mutation paths.
4. **Deterministic DCG validation** — Every Live Twin mutation requires DCG validation and a short-lived authorization token.
5. **Fail closed on stale context** — A stale decision must fail closed; re-read evidence, re-simulate, and re-authorize.
6. **No free-form LLM KPIs** — Quantitative KPI values must come from deterministic code/models, never LLM claims.
7. **No secrets in repository** — Do not commit service-account keys, tokens, or `.env` files.

## Documentation Index

Read `docs/README.md` and `docs/getting-started/PROJECT_DOCUMENTATION.md` for complete project specifications.
