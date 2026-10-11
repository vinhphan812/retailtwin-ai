RetailTwin AI Agent Guide

Project purpose

RetailTwin AI is a context-guarded autonomous 3D retail digital twin.

The target control loop is:

OBSERVE → DETECT → INVESTIGATE → PLAN → SIMULATE → GUARD → ACT → VERIFY

Current repository maturity matters:

- The React/React Three Fiber store scene is scaffolded.
- The FastAPI boundary provides fixture-backed store reads and in-memory event intake.
- The autonomous agent, Simulation Twin, Decision Context Guard (DCG), guarded Live Twin mutation, Executor, Verifier, and end-to-end release gates are not complete unless current evidence says otherwise.

Before making claims about implementation status, read docs/CURRENT_STATUS.md.

Commands

Run commands from the repository root unless a command says otherwise.

Git and repository checks

bash
git status --short --branch
git fetch origin
git diff --check origin/main...HEAD
git diff --name-status origin/main...HEAD

API

bash
cd apps/api
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -e ".[dev]"
pytest

On non-Windows shells, activate the virtual environment with the platform-appropriate command.

Web application

Requires Node.js >=20.17.

bash
cd apps/web
npm ci
npm test
npm run build

GitNexus code exploration

Use GitNexus before medium- or high-risk executable-code changes.

bash
gitnexus status
gitnexus analyze .
gitnexus query "decision context guard live twin"
gitnexus context <symbol>
gitnexus impact <symbol>

Use direct source inspection only when GitNexus cannot answer a query or reports unknown/incomplete results.

Repository structure

text
apps/api FastAPI application boundary
apps/web React, TypeScript, React Three Fiber UI
agents/ Target autonomous-agent responsibilities
guard/decision-context-guard/ Deterministic safety boundary
services/twin Canonical Digital Twin access
services/simulation Simulation clone/apply/evaluate responsibility
services/forecasting Demand/risk responsibility
services/optimizer Optional deterministic candidate optimizer
data/ Schemas, seed fixtures, synthetic scenarios
infrastructure/ GCP and Firebase setup
docs/ Product, architecture, acceptance, ADRs
tests/ Cross-cutting test guidance

Required reading order

Before modifying product behavior, contracts, architecture, or safety boundaries:

1. docs/PROJECT_CONTEXT.md
2. docs/CURRENT_STATUS.md
3. docs/ARCHITECTURE.md
4. docs/DOMAIN_AND_DATA_MODEL.md
5. docs/IMPLEMENTATION_GUIDE.md
6. docs/DEMO_AND_ACCEPTANCE.md
7. Relevant records under docs/adr/

Read docs/DEVELOPMENT_WORKFLOW.md before preparing a pull request.

Coding conventions

Python

- Use typed Pydantic models at API and contract boundaries.
- Keep FastAPI routes thin; business and safety logic belongs outside route handlers.
- Add tests for valid input, invalid input, and safety/failure paths.
- Preserve correlation IDs, event IDs, decision IDs, simulation IDs, and action IDs in logs and payloads.

TypeScript and React

- Use TypeScript types for API payloads and scene entities.
- Keep UI state derived from typed backend/API state.
- Prefer small focused components and explicit props.
- Test user-visible error, loading, and state-transition behavior.
- Do not represent a visual animation as a successful operational mutation.

Documentation

- Use docs/ for architecture, operational, and user-facing documentation.
- Keep target architecture separate from current implementation status.
- Update docs and ADRs in the same PR when a public schema, state transition, action contract, security invariant, storage boundary, or execution boundary changes.
- Every PR must name its ADR or state ADR: N/A with a rationale.

RetailTwin safety invariants

These rules are non-negotiable:

1. The Digital Twin owns operational truth; an LLM does not.
2. Gemini and browser code must never directly mutate the Live Twin.
3. Simulation state and Live Twin state must use separate mutation paths.
4. Every Live Twin mutation requires deterministic DCG validation and an exact, short-lived authorization.
5. A stale decision must fail closed. Re-read evidence, re-simulate, and re-authorize.
6. An authorization is bound to an exact decision, context, and action set. It cannot authorize altered, expired, or replayed actions.
7. Quantitative KPI values must come from deterministic code or models, never free-form LLM claims.
8. Do not expose hidden chain-of-thought. Show concise evidence, decisions, guard outcomes, actions, and verification results.
9. Do not commit secrets, service-account keys, tokens, .env files, or production credentials.
10. Simulation state and Live Twin state must use separate mutation paths.
11. Every Live Twin mutation requires deterministic DCG validation and an exact, short-lived authorization.
12. A stale decision must fail closed. Re-read evidence, re-simulate, and re-authorize.
13. An authorization is bound to an exact decision, context, and action set. It cannot authorize altered, expired, or replayed actions.
14. Quantitative KPI values must come from deterministic code or models, never free-form LLM claims.
15. Do not expose hidden chain-of-thought. Show concise evidence, decisions, guard outcomes, actions, and verification results.
16. Do not commit secrets, service-account keys, tokens, .env files, or production credentials.
17. Do not claim a release gate has passed without reproducible issue/PR evidence and intentional acceptance.

Testing and verification

For any executable-code change:

1. Run the narrow tests for changed behavior.
2. Run the relevant application suite.
3. Run git diff --check origin/main...HEAD.
4. Review changed files against the intended scope.
5. The Digital Twin owns operational truth; an LLM does not.
6. Gemini and browser code must never directly mutate the Live Twin.
7. Simulation state and Live Twin state must use separate mutation paths.
8. Every Live Twin mutation requires deterministic DCG validation and an exact, short-lived authorization.
9. A stale decision must fail closed. Re-read evidence, re-simulate, and re-authorize.
10. An authorization is bound to an exact decision, context, and action set. It cannot authorize altered, expired, or replayed actions.
11. Quantitative KPI values must come from deterministic code or models, never free-form LLM claims.
12. Do not expose hidden chain-of-thought. Show concise evidence, decisions, guard outcomes, actions, and verification results.
13. Do not commit secrets, service-account keys, tokens, .env files, or production credentials.
14. Do not claim a release gate has passed without reproducible issue/PR evidence and intentional acceptance.

Testing and verification

For any executable-code change:

1. Run the narrow tests for changed behavior.
2. Run the relevant application suite.
3. Run git diff --check origin/main...HEAD.
4. Review changed files against the intended scope.
5. Verify failure paths, not only the happy path.
6. State exactly what was run and what could not be run.

For changes affecting Live Twin, DCG, authorization, event identity, simulation isolation, or execution, add explicit negative-path tests.

Git and GitHub workflow

- Start from current origin/main unless working on an existing approved PR branch.
- Use one issue, one bounded branch, and one PR whenever possible.
- Use Conventional Commit messages.
- Do not overwrite another contributor’s branch.
- Do not force-push without explicit approval.
- Do not merge a PR without explicit approval.
- Read all existing PR comments and reviews before responding with a new commit.
- Report actual GitHub checks. “No checks configured” is not “CI green.”

Boundaries

Never:

- bypass DCG, Executor, or authorization for a Live Twin mutation;
- add a generic public Live Twin write endpoint;
- make the browser write Firestore operational state directly;
- make Gemini own database credentials or direct write tools;
- use mock output as evidence that a cloud integration, guard, or release gate works;
- change unrelated files while resolving a scoped issue;
- stage generated local folders, untracked audit artifacts, or personal tool configuration unless explicitly requested.

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **retailtwin-ai** (693 symbols, 974 relationships, 12 execution flows).

> Index stale? Run `node .gitnexus/run.cjs analyze --index-only` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? Bootstrap with `npx`, `bunx`, or `pnpm dlx` — e.g. `bunx gitnexus@latest analyze` (npm 11 npx crash; #1939).

## Always Do

- **MUST run impact before editing.** Use `impact({target: "symbolName", direction: "upstream"})` or `node .gitnexus/run.cjs impact "symbolName" --direction upstream --repo .`; report callers, processes, and risk. Never substitute grep for graph analysis.
- **MUST analyze graph changes before committing.** Use `detect_changes({scope: "all"})` (MCP) or `node .gitnexus/run.cjs detect-changes --scope all --repo .` (CLI fallback). `partial: true` or `truncated: true` is not a clean check — a zero means unseen, not unaffected; re-run it. For regression review: `detect_changes({scope: "compare", base_ref: "main"})` or `node .gitnexus/run.cjs detect-changes --scope compare --base-ref "main" --repo .`.
- MUST warn on HIGH/CRITICAL `risk` pre-edit; never use `riskSharedAxes` to waive a HIGH/CRITICAL `risk` warning. Compare File/symbol: MCP File omits axes; Graph-RAG expands File.
- **MUST treat `risk: UNKNOWN` as unresolved, not as low.** An empty caller set is not evidence the symbol is unused — it can also mean the callers are not resolvable by the index (plain-object property access, dynamic dispatch, cross-language calls). `impact` pairs `UNKNOWN` with a `riskNote` saying so. Confirm with a text search before treating the symbol as safe to change or delete; do not proceed on the strength of a zero.
- **MUST use `query({search_query: "concept"})` for concepts/flows, `context({name: "symbolName"})` for a named symbol, or `impact` for blast radius, on read-only callers, dependencies, imports, or execution flow.** Graph first; text search only for empty/`UNKNOWN`/literals.
- For security review, `explain({target: "fileOrSymbol"})` lists taint findings (source→sink flows; needs `analyze --pdg`).

## Never Do

- NEVER edit a function, class, or method before MCP/CLI impact analysis.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis, and never read `UNKNOWN` as an all-clear — it means the walk could not answer, which is the one verdict that requires confirming by other means.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit before MCP/CLI graph change analysis.

## Resources

| Resource | Use for |
| --- | --- |
| `gitnexus://repo/retailtwin-ai/context` | Codebase overview, check index freshness |
| `gitnexus://repo/retailtwin-ai/clusters` | All functional areas |
| `gitnexus://repo/retailtwin-ai/processes` | All execution flows |
| `gitnexus://repo/retailtwin-ai/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
| --- | --- |
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
