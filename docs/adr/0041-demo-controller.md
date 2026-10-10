# ADR 0041: Demo Controller Implementation

## Status

Accepted

## Context

Live AI/cloud demonstrations are timing-sensitive and non-reproducible by default. The flagship scenario must be reproducible without faking Gemini, Firestore, Simulation, DCG or execution results.

## Problem

Without a deterministic demo controller:

- Demo runs may fail intermittently
- Judges cannot reproduce the scenario
- Stale-context rejection cannot be reliably demonstrated
- Release gates cannot be verified consistently

## Decision

We implement a **deterministic in-process demo controller** for the Weekend Demand Surge flagship scenario that:

1. Uses real components (TwinService, SimulationService, DCG, Executor, Verifier)
2. Controls only event timing and initial state for reproducibility
3. Provides reset/start/status endpoints for automated testing
4. Supports stale-context mutation for G04 verification

## Architecture

```mermaid
flowchart TB
    subgraph DemoController["🎯 DEMO CONTROLLER"]
        subgraph API["API ENDPOINTS"]
            RST[POST /demo/reset]
            STRT[POST /demo/start]
            STAT[GET /demo/status]
            TLINE[GET /demo/timeline]
        end

        subgraph Phases["DEMO PHASES"]
            P1[IDLE]
            P2[RESET]
            P3[EVENT]
            P4[INVESTIGATE]
            P5[SIMULATE]
            P6[DCG]
            P7[EXECUTE]
            P8[VERIFY]
            P9[COMPLETE]
        end

        subgraph Services["SERVICES"]
            TW[TwinService]
            SIM[Simulation]
            DCG[DCG]
            EXE[Executor]
            VER[Verifier]
        end
    end

    RST --> P1
    STRT --> P2
    P2 --> P3 --> P4 --> P5 --> P6 --> P7 --> P8 --> P9
    P9 --> P1

    P4 --> TW
    P5 --> SIM
    P6 --> DCG
    P7 --> EXE
    P8 --> VER
```

## Happy Path Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant API as Demo API
    participant TW as TwinService
    participant SIM as Simulation
    participant DCG as DCG
    participant EXE as Executor
    participant VER as Verifier

    C->>API: POST /demo/reset
    API->>TW: load_fixtures()
    TW-->>API: Initial State

    C->>API: POST /demo/start
    API->>TW: Create demand surge event
    API->>TW: get_inventory(P017)
    TW-->>API: Evidence: qty=8, backroom=54
    Note over API: INVESTIGATE phase

    API->>SIM: create_scenario(A, B, C)
    SIM-->>API: Scenarios created
    Note over API: SIMULATE phase

    API->>DCG: validate(decision)
    DCG-->>API: ALLOW
    Note over API: DCG phase

    API->>EXE: execute(auth, actions)
    EXE->>TW: apply_action(facings 2→4, +12)
    TW-->>EXE: Version v2
    Note over API: EXECUTE phase

    API->>VER: verify(expected, actual)
    VER-->>API: PASS
    Note over API: VERIFY phase

    API-->>C: Response: complete, dcg=ALLOW, verifier=PASS
```

## Stale Context Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant API as Demo API
    participant TW as TwinService
    participant SIM as Simulation
    participant DCG as DCG
    participant EXE as Executor

    C->>API: POST /demo/reset
    API->>TW: load_fixtures()

    C->>API: POST /demo/start?stale_context_test=true

    Note over API,TW: Normal flow until DCG
    API->>TW: Create decision for context v1
    API->>DCG: validate(decision, context v1)

    Note over API,TW: Intentional mutation
    API->>TW: mutate_context()
    Note over TW: context v1 → v2

    DCG-->>API: REFRESH_REQUIRED
    Note over API: STALE BLOCKED

    API->>TW: refresh_evidence()
    API->>TW: create_new_decision(context v2)

    API->>DCG: validate(decision v2, context v2)
    DCG-->>API: ALLOW

    API->>EXE: execute(auth, actions)
    EXE-->>API: Committed

    API-->>C: Response: stale_blocked, dcg=REFRESH_REQUIRED
```

## Demo Phases

```mermaid
stateDiagram-v2
    [*] --> IDLE: Reset

    IDLE --> RESET: POST /demo/start
    RESET --> EVENT: Fixtures loaded

    EVENT --> INVESTIGATE: Event created
    INVESTIGATE --> SIMULATE: Evidence collected

    SIMULATE --> DCG: Scenarios evaluated

    DCG --> EXECUTE: ALLOW
    DCG --> IDLE: DENY

    EXECUTE --> VERIFY: Actions applied

    VERIFY --> COMPLETE: PASS or FAIL
    COMPLETE --> IDLE: Done

    Note right of DCG: stale_context_test=true
    Note right of DCG: REFRESH_REQUIRED triggers<br/>automatic refresh loop
```

## API Endpoints

```mermaid
flowchart LR
    subgraph Endpoints["API ENDPOINTS"]
        E1[POST /demo/reset<br/>Reset to fixtures]
        E2[POST /demo/start<br/>Run autonomous loop]
        E3[GET /demo/status<br/>Current state]
        E4[GET /demo/timeline<br/>Full timeline]
    end

    subgraph Responses["RESPONSES"]
        R1[run_id, phase, version]
        R2[phase, dcg_verdict,<br/>executor_committed,<br/>verifier_outcome]
        R3[Full status]
        R4[Timeline events]
    end

    E1 --> R1
    E2 --> R2
    E3 --> R3
    E4 --> R4
```

### POST /demo/reset

```bash
curl -X POST http://127.0.0.1:8000/demo/reset

# Response:
{
  "run_id": "run-20261010-001",
  "phase": "idle",
  "context_version": "store-001:v1",
  "slots_loaded": 5
}
```

### POST /demo/start

```bash
# Happy path
curl -X POST http://127.0.0.1:8000/demo/start
# Response: {dcg_verdict: "ALLOW", executor_committed: true, verifier_outcome: "PASS"}

# Stale context
curl -X POST "http://127.0.0.1:8000/demo/start?stale_context_test=true"
# Response: {dcg_verdict: "REFRESH_REQUIRED", executor_committed: false}
```

## Timeline Events

```mermaid
flowchart TB
    subgraph Timeline["TIMELINE EVENTS"]
        T1["16:01:02 TRIGGER<br/>Demand surge: P017"]
        T2["16:01:03 EVIDENCE<br/>Shelf qty: 8, Backroom: 54"]
        T3["16:01:05 DIAGNOSIS<br/>Shelf allocation insufficient"]
        T4["16:01:07 SIMULATION<br/>A/B/C evaluated"]
        T5["16:01:08 SELECTION<br/>Scenario B selected"]
        T6["16:01:09 GUARD<br/>REFRESH_REQUIRED"]
        T7["16:01:11 REFRESH<br/>Context refreshed"]
        T8["16:01:14 GUARD<br/>ALLOW"]
        T9["16:01:15 ACTION<br/>Facings 2→4, +12"]
        T10["16:01:17 VERIFY<br/>PASS"]
    end

    T1 --> T2
    T2 --> T3
    T3 --> T4
    T4 --> T5
    T5 --> T6
    T6 --> T7
    T7 --> T8
    T8 --> T9
    T9 --> T10
```

## Demo Fixtures

```mermaid
flowchart TB
    subgraph Initial["INITIAL STATE (P017)"]
        SKU[SKU: P017]
        NAME[Name: Premium Coffee]
        FAC[Facings: 2]
        SHELF[Shelf Qty: 8]
        BACK[Backroom: 54]
        VEL[Velocity: 0.8]
        PRICE[Price: $3.50]
        VER[Version: v1]
    end

    subgraph Event["DEMAND SURGE EVENT"]
        EVT[Type: demand.surge]
        VEL_CHG["Velocity: +46%"]
        SKU2[SKU: P017]
    end

    Initial --> Event
```

## Implementation

```python
class DemoPhase(str, Enum):
    IDLE = "idle"
    RESET = "reset"
    EVENT = "event"
    INVESTIGATE = "investigate"
    SIMULATE = "simulate"
    DCG = "dcg"
    EXECUTE = "execute"
    VERIFY = "verify"
    COMPLETE = "complete"
    STALE_BLOCKED = "stale_blocked"

class DemoOrchestrator:
    """
    Deterministic demo controller for Weekend Demand Surge.
    """

    def __init__(
        self,
        twin_service: TwinService,
        simulation_service: SimulationService,
        dcg: DecisionContextGuard,
        executor: ExecutorAgent,
        verifier: VerifierAgent
    ):
        self.twin = twin_service
        self.simulation = simulation_service
        self.dcg = dcg
        self.executor = executor
        self.verifier = verifier
        self._state = DemoPhase.IDLE
        self._timeline: list[TimelineEvent] = []

    async def reset(self) -> DemoResetResponse:
        """Reset to initial fixtures."""
        await self.twin.load_fixtures()
        self._timeline = []
        self._state = DemoPhase.IDLE
        return DemoResetResponse(...)

    async def start(
        self,
        stale_context_test: bool = False
    ) -> DemoStartResponse:
        """Run the autonomous loop once."""

        # Happy path or stale context test
        if stale_context_test:
            return await self._run_stale_context_test()
        else:
            return await self._run_happy_path()

    async def _run_happy_path(self) -> DemoStartResponse:
        """Normal run with ALLOW verdict."""

        # 1. EVENT
        self._state = DemoPhase.EVENT
        event = self._create_demand_surge_event()

        # 2. INVESTIGATE
        self._state = DemoPhase.INVESTIGATE
        evidence = await self._investigate(event)

        # 3. SIMULATE
        self._state = DemoPhase.SIMULATE
        best = await self._simulate(evidence)

        # 4. DCG
        self._state = DemoPhase.DCG
        decision = await self._create_decision(evidence, best)
        context = await self.twin.get_current_context()
        result = await self.dcg.validate(decision, context, ...)

        if result.outcome == DCGOutcome.ALLOW:
            # 5. EXECUTE
            self._state = DemoPhase.EXECUTE
            auth = self.dcg.issue_authorization(decision, context)
            await self.executor.execute(...)

            # 6. VERIFY
            self._state = DemoPhase.VERIFY
            verifier_result = await self.verifier.verify(...)

            self._state = DemoPhase.COMPLETE
            return DemoStartResponse(
                dcg_verdict="ALLOW",
                executor_committed=True,
                verifier_outcome="PASS"
            )
```

## Testing

```bash
# Run all demo tests
pytest apps/api/tests/test_demo_controller.py -v

# Happy path
pytest apps/api/tests/test_demo_controller.py::test_happy_path -v

# Stale context
pytest apps/api/tests/test_demo_controller.py::test_stale_context -v
```

## Verification Checklist

- [ ] Happy path completes with ALLOW verdict
- [ ] Stale context returns REFRESH_REQUIRED
- [ ] Timeline shows all phases
- [ ] Reset returns to initial fixtures
- [ ] Executor only commits after ALLOW
- [ ] Verifier reports correct outcome
- [ ] No secrets in demo data
- [ ] Reproducible from clean reset

## Related Issues

- #41: Build deterministic flagship demo controller
- #16: Implement Decision Context Guard MVP
- #17: Enforce No-Stale-Commit
- #18: Implement guarded Executor
