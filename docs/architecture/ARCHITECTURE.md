# RetailTwin AI — Technical Architecture

> This document is the **target architecture**. It does not imply every component is already implemented. See `docs/getting-started/CURRENT_STATUS.md` for the current `main` baseline and gate status.

RetailTwin AI must autonomously react to retail events while preserving a strict boundary between AI reasoning and live operational state.

## 1. High-Level Architecture

```mermaid
flowchart TB
    subgraph Input["INPUT"]
        POS[POS / Inventory<br/>Promotion / Demo]
    end

    subgraph Processing["PROCESSING"]
        PUB[Pub/Sub]
        OBS[Observer]
        INV[Investigator]
        PLN[Planner]
        SIM[Simulation]
        KPI[KPI Evaluator]
        DCG[Decision Context Guard]
        EXE[Executor]
    end

    subgraph Output["OUTPUT"]
        LIVE[Live Twin]
        VIS[3D Visualization]
        VER[Verifier]
    end

    POS --> PUB
    PUB --> OBS
    OBS --> INV
    INV --> PLN
    PLN --> SIM
    SIM --> KPI
    KPI --> DCG
    DCG -->|ALLOW| EXE
    DCG -->|REFRESH| PLN
    DCG -->|DENY| F[Fail Closed]
    EXE --> LIVE
    LIVE --> VIS
    VIS --> VER
```

## 2. End-to-End Flow (Planned vs Implemented)

```mermaid
flowchart LR
    subgraph Events ["Events"]
        E[Store events<br/>POS / inventory / promotion]
        PS[Pub/Sub]
    end

    E --> PS
    PS --> O[Observer]
    O --> I[Investigator]
    I --> P[Gemini planner]
    P --> S[Simulation Twin]
    S --> K[KPI evaluator]
    K --> G[Decision Context Guard]

    G -- "ALLOW + authorization" --> X[Executor]
    G -- REFRESH_REQUIRED --> P
    G -- DENY --> F[Fail closed]
    G -- HUMAN_REVIEW --> H[Human review]
    H -.-> P

    X --> L[Live Twin]
    L --> V[3D view]
    V --> Z[Verifier]

    classDef implemented fill:#d9f7e8,stroke:#16794a
    classDef planned fill:#fff2cc,stroke:#9a6700
    classDef event fill:#eaf4fc,stroke:#3772a5
    class E,PS event
    class V implemented
    class O,I,P,S,K,G,X,L,F,H,Z planned
```

> All gates are **pending** — no linked test, deployment, or 20-run evidence available.

## 3. Control Loop

```mermaid
flowchart LR
    OBS[OBSERVE] --> DET[DETECT]
    DET --> INV[INVESTIGATE]
    INV --> PLN[PLAN]
    PLN --> SIM[SIMULATE]
    SIM --> GRD[GUARD]
    GRD -->|ALLOW| ACT[ACT]
    GRD -->|REFRESH| PLN
    GRD -->|DENY| END[End]
    ACT --> VFY[VERIFY]
    VFY --> OBS
```

## 4. Technology Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React + TypeScript, React Three Fiber / Three.js + Drei, GLB/glTF assets |
| **Backend** | Python, FastAPI, Cloud Run |
| **AI** | Gemini on Vertex AI (structured tool calling) |
| **Database** | Firestore (Live Twin), BigQuery (Analytics) |
| **Events** | Pub/Sub |
| **Storage** | Cloud Storage (3D assets) |
| **Security** | Secret Manager, Cloud Logging, Firebase Auth |

## 5. Component Responsibilities

| Component | Description |
|-----------|-------------|
| **Observer** | Consumes normalized store events, deduplicates, starts investigation |
| **Investigator** | Collects bounded, versioned evidence |
| **Planner** | Uses Gemini to produce structured candidate plans |
| **Simulation Service** | Clones live state, applies candidate actions |
| **KPI Evaluator** | Computes deterministic business/operational effects |
| **DCG** | Deterministic validation before live commit |
| **Executor** | Only component that performs authorized live mutations |
| **Verifier** | Reads post-action state, compares expected vs observed |
| **3D Twin** | State-driven operational interface |

## 6. Decision Context Guard (DCG)

### 6.1 Decision Structure

```json
{
  "decision_id": "RT-D-1027",
  "agent_id": "retailtwin-orchestrator",
  "context_version": "store-001:v23871",
  "context_timestamp": "2026-10-07T08:00:00Z",
  "evidence": [],
  "proposed_actions": [],
  "simulation_id": "SIM-204",
  "expected_impact": {}
}
```

### 6.2 Five Validation Gates

```mermaid
flowchart TB
    subgraph Gates["DCG VALIDATION GATES"]
        G1[1. DECISION_INTEGRITY<br/>Required fields<br/>Valid schema]
        G2[2. CONTEXT_VERSION<br/>Decision context<br/>= Current]
        G3[3. FRESHNESS<br/>Evidence < 5min<br/>Decision < 1min]
        G4[4. PHYSICAL_CONSTRAINTS<br/>Inventory available<br/>Capacity ok]
        G5[5. AUTHORIZATION_POLICY<br/>Risk level ok<br/>Permissions]
    end

    subgraph Outcomes["OUTCOMES"]
        ALLOW[ALLOW<br/>Issue token]
        REFRESH[REFRESH_REQUIRED<br/>Refresh & replan]
        DENY[DENY<br/>Do not execute]
        HUMAN[HUMAN_REVIEW<br/>Human approval]
    end

    G1 -->|pass| G2
    G1 -->|fail| DENY
    G2 -->|pass| G3
    G2 -->|stale| REFRESH
    G3 -->|pass| G4
    G3 -->|stale| REFRESH
    G4 -->|pass| G5
    G4 -->|fail| DENY
    G5 -->|pass| ALLOW
    G5 -->|fail| HUMAN
```

### 6.3 No-Stale-Commit Flow

```mermaid
sequenceDiagram
    participant PLN as Planner
    participant SIM as Simulation
    participant DCG as DCG
    participant EXE as Executor
    participant LIVE as Live Twin

    PLN->>SIM: Create decision D1 (context v1)
    SIM-->>PLN: Scenario evaluated

    Note over LIVE,DCG: Context changes to v2

    PLN->>DCG: Submit D1 (context v1)
    DCG->>DCG: Check context version

    alt Context Mismatch
        DCG-->>PLN: REFRESH_REQUIRED
        PLN->>PLN: Refresh evidence
        PLN->>SIM: Create new decision D2 (context v2)
        SIM-->>PLN: Re-evaluated
        PLN->>DCG: Submit D2 (context v2)
    end

    DCG-->>PLN: ALLOW + Token
    PLN->>EXE: Execute with token
    EXE->>LIVE: Apply action
    LIVE-->>EXE: Version v2
```

### 6.4 DCG Outcomes

| Outcome | Description | Action |
|---------|-------------|--------|
| `ALLOW` | All gates passed | Issue authorization token |
| `REFRESH_REQUIRED` | Context/staleness issue | Refresh evidence, retry |
| `DENY` | Critical failure | Do not execute |
| `HUMAN_REVIEW` | High-risk action | Require human approval |

## 7. Commit Authorization

```mermaid
flowchart TB
    subgraph Token["AUTHORIZATION TOKEN"]
        T1[decision_id]
        T2[context_hash<br/>SHA256]
        T3[action_hashes]
        T4[expires_at<br/>60 seconds]
        T5[nonce<br/>UUID]
    end

    subgraph Validation["EXECUTOR VALIDATION"]
        V1{Token<br/>Exists?}
        V2{Not<br/>Expired?}
        V3{Nonce<br/>Unused?}
        V4{Context<br/>Hash Match?}
    end

    subgraph Result["RESULT"]
        OK[✅ Commit]
        FAIL[❌ Reject]
    end

    Token --> Validation
    V1 -->|Yes| V2
    V1 -->|No| FAIL
    V2 -->|Yes| V3
    V2 -->|No| FAIL
    V3 -->|Yes| V4
    V3 -->|No| FAIL
    V4 -->|Yes| OK
    V4 -->|No| FAIL
```

Authorization contains:
- decision ID
- context hash/version
- exact allowed action set
- expiry (60 seconds)
- nonce for replay protection

## 8. State Separation

```mermaid
flowchart LR
    subgraph Live["LIVE TWIN PATH"]
        L1[Load State vN]
        L2[Apply Action]
        L3[Save State vN+1]
        L4[Log to Audit]
    end

    subgraph Simulation["SIMULATION PATH"]
        S1[Clone State vN]
        S2[Apply Candidate]
        S3[Evaluate KPIs]
        S4[Discard or Retain]
    end

    subgraph DCG["DCG VALIDATION"]
        D1[Submit Decision]
        D2[Validate Context]
        D3{Valid?}
    end

    subgraph Executor["EXECUTOR"]
        X1[Authorize Action]
        X2[Call Live Twin]
    end

    L1 --> L2 --> L3 --> L4
    S1 --> S2 --> S3 --> S4
    D1 --> D2 --> D3
    D3 -->|YES| X1
    X1 --> X2
    X2 --> L2
```

**Rule:** Simulation path never mutates Live Twin directly.

## 9. Action Risk Levels

| Level | Actions | Policy |
|-------|---------|--------|
| **L1** | Focus camera, highlight, read/analyze | Automatic |
| **L2** | Move SKU, facings, planogram changes | Automatic (Simulation only) |
| **L3** | Bounded replenishment/layout | Autonomous if DCG passes |
| **High** | Price/promotion changes | `HUMAN_REVIEW` required |

## 10. Reliability Rules

```mermaid
flowchart TB
    subgraph Events["EVENT HANDLING"]
        E1[event_id correlation_id]
        E2[Idempotent consumers]
        E3[Bounded retries]
    end

    subgraph Agent["AGENT BEHAVIOR"]
        A1[Bounded re-planning]
        A2[Visible errors]
        A3[No silent commits]
    end

    subgraph Demo["DEMO"]
        D1[Deterministic reset]
        D2[Reproducible runs]
        D3[Structured logs]
    end
```

- Pub/Sub events carry `event_id` and `correlation_id`
- Consumers are idempotent
- Retries are bounded
- Errors are visible
- Demo reset is deterministic

## 11. Security Rules

```mermaid
flowchart TB
    subgraph Allowed["✅ ALLOWED"]
        A1[Service identities<br/>IAM]
        A2[Secret Manager]
        A3[Server-side validation]
        A4[Audit logging]
    end

    subgraph Forbidden["❌ FORBIDDEN"]
        F1[Keys in Git]
        F2[Raw credentials<br/>to Gemini]
        F3[Public mutation<br/>endpoints]
        F4[Hidden chain-of-thought]
    end
```

- No service-account key or secret in Git
- Use service identities/IAM and Secret Manager
- Frontend cannot bypass backend guard/executor
- Gemini never receives raw database credentials
- Validate all tool arguments server-side
- Audit live decisions/actions

## 12. Repository Ownership

```mermaid
flowchart TB
    subgraph Frontend["FRONTEND"]
        W[apps/web<br/>3D + UX]
    end

    subgraph Backend["BACKEND"]
        A[apps/api<br/>API boundary]
    end

    subgraph Agents["AGENTS"]
        ORCH[orchestrator<br/>state machine]
        OBS[observer<br/>event activation]
        INV[investigator<br/>evidence]
        PLN[planner<br/>structured plans]
        SIM[simulator<br/>orchestration]
        EXE[executor<br/>guarded execution]
        VER[verifier<br/>post-action]
    end

    subgraph Services["SERVICES"]
        TWN[services/twin<br/>canonical access]
        SIM_SVC[services/simulation<br/>clone/apply/evaluate]
        FRCS[services/forecasting<br/>demand/risk]
    end

    subgraph Guard["GUARD"]
        DCG[guard/decision-context-guard<br/>deterministic guard]
    end

    subgraph Data["DATA"]
        SCH[data/schemas<br/>schemas]
        SEED[data/synthetic<br/>scenarios]
        INFRA[infrastructure/gcp<br/>config]
    end

    subgraph Tests["TESTS"]
        T[tests/<br/>unit/integration/E2E]
    end
```

| Directory | Owner |
|----------|-------|
| `apps/web` | 3D + UX |
| `apps/api` | API / Integration |
| `agents/*` | AI / Agent / DCG |
| `services/*` | Data / Cloud |
| `guard/*` | AI / Agent / DCG |
| `data/*` | Data / Cloud |
| `infrastructure/*` | Data / Cloud |
| `tests/*` | All roles |

## 13. Related Documentation

| Document | Description |
|----------|-------------|
| [DOMAIN_AND_DATA_MODEL.md](DOMAIN_AND_DATA_MODEL.md) | Entities, schemas, events, actions |
| [SECURITY.md](SECURITY.md) | Security architecture, DCG, Executor |
| [getting-started/CURRENT_STATUS.md](../getting-started/CURRENT_STATUS.md) | Current implementation status |
