# RetailTwin AI Agent Guidelines

This file governs autonomous agent behavior and responsibilities within the RetailTwin AI codebase.

## Core Responsibilities

1. **Autonomous Operation** — Operate within the Observe → Detect → Investigate → Plan → Simulate → Guard → Act → Veriy loop.
2. **Safety Enforcement** — Strictly adhere to the Decision Context Guard (DCG) and No-Stale-Commit invariants.
3. **Deterministic Verification** — Ensure all numerical/KPI claims are backed by deterministic model/code calculations.
4. **Clean Code & Testing** — Write typed Pydantic/TypeScript models, maintain high test coverage, and verify failure paths.

## Coding Standards

- **Python:** Use Pydantic V2, keep FastAPI routes thin, preserve correlation IDs and event tracking.
- **TypeScript/React:** Derive UI state from backend/API state, keep components modular and explicit.
- **Git:** Use conventional commits, reference issues/PRs correctly, never commit `.worktrees/`.
