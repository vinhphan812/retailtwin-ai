# API Documentation

## Overview

The RetailTwin AI API is a FastAPI-based backend that provides endpoints for:
- Health checks
- Store state management
- Inventory operations
- Event handling
- Demo controller operations

## Base URL

```
http://127.0.0.1:8000  (Local Development)
https://retailtwin-api-xxxxxxxx-uc.a.run.app  (Production)
```

## Authentication

Currently no authentication required for MVP. Production should use Firebase Auth or API keys.

## Endpoints

### Health Check

#### GET /health

Check API health status.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-10-10T08:00:00Z"
}
```

---

### Store Operations

#### GET /store

Get current store state.

**Response:**
```json
{
  "store_id": "store-001",
  "version": "v23871",
  "products": [
    {
      "product_id": "P017",
      "sku": "SKU-P017",
      "category": "beverages",
      "shelf_id": "A02",
      "slot_id": "A02-S03",
      "position": {"x": 1.2, "y": 1.4, "z": -0.5},
      "facings": 2,
      "shelf_quantity": 8,
      "backroom_quantity": 54,
      "price": 3.5,
      "sales_velocity": 0.8,
      "forecast_demand": 22,
      "stockout_probability": 0.18,
      "version": 981,
      "updated_at": "2026-10-07T08:00:00Z"
    }
  ],
  "updated_at": "2026-10-07T08:00:00Z"
}
```

---

### Inventory Operations

#### GET /inventory/{sku}

Get inventory for a specific SKU.

**Parameters:**
- `sku` (path) - Product SKU identifier

**Response:**
```json
{
  "sku": "P017",
  "shelf_quantity": 8,
  "backroom_quantity": 54,
  "total_available": 62,
  "version": "inv-981",
  "updated_at": "2026-10-07T08:00:00Z"
}
```

---

### Event Operations

#### POST /events

Submit a store event (sale, inventory change, etc.)

**Request:**
```json
{
  "event_id": "evt-000123",
  "correlation_id": "run-20261007-001",
  "event_type": "sale.completed",
  "store_id": "store-001",
  "sku": "P017",
  "quantity": 3,
  "occurred_at": "2026-10-07T08:01:00Z",
  "source": "synthetic-pos"
}
```

**Responses:**
- `200 OK` - Event accepted (or duplicate)
- `409 Conflict` - Event ID conflict with different payload

```json
// 200 OK (duplicate)
{
  "status": "accepted",
  "event_id": "evt-000123",
  "message": "Event already processed"
}

// 409 Conflict
{
  "error": "event_id_conflict",
  "event_id": "evt-000123",
  "message": "Event ID exists with different payload"
}

// 200 OK (new event)
{
  "status": "accepted",
  "event_id": "evt-000123",
  "published": true
}
```

---

### Demo Controller

#### POST /demo/reset

Reset the demo to initial fixtures.

**Response:**
```json
{
  "run_id": "run-20261010-001",
  "phase": "idle",
  "context_version": "store-001:v1",
  "slots_loaded": 5,
  "products_loaded": 20,
  "reset_at": "2026-10-10T08:00:00Z"
}
```

---

#### POST /demo/start

Start the autonomous demo loop.

**Query Parameters:**
- `stale_context_test` (bool, default: false) - Enable stale context rejection test

**Response:**
```json
// Happy path
{
  "run_id": "run-20261010-001",
  "phase": "complete",
  "dcg_verdict": "ALLOW",
  "executor_committed": true,
  "verifier_outcome": "PASS",
  "duration_ms": 1523
}

// Stale context test
{
  "run_id": "run-20261010-002",
  "phase": "stale_blocked",
  "dcg_verdict": "REFRESH_REQUIRED",
  "executor_committed": false,
  "verifier_outcome": "FAIL",
  "reason": "Context version mismatch",
  "duration_ms": 234
}
```

---

#### GET /demo/status

Get current demo status.

**Response:**
```json
{
  "run_id": "run-20261010-001",
  "phase": "complete",
  "context_version": "store-001:v2",
  "dcg_verdict": "ALLOW",
  "executor_committed": true,
  "verifier_outcome": "PASS",
  "current_state": {
    "sku": "P017",
    "facings": 4,
    "shelf_quantity": 20,
    "backroom_quantity": 42
  }
}
```

---

#### GET /demo/timeline

Get full event timeline.

**Response:**
```json
{
  "run_id": "run-20261010-001",
  "events": [
    {
      "timestamp": "2026-10-10T08:00:02Z",
      "phase": "event",
      "type": "TRIGGER",
      "description": "Demand surge detected: P017"
    },
    {
      "timestamp": "2026-10-10T08:00:03Z",
      "phase": "investigate",
      "type": "EVIDENCE",
      "description": "Shelf qty: 8; backroom: 54; velocity: +46%"
    },
    {
      "timestamp": "2026-10-10T08:00:05Z",
      "phase": "investigate",
      "type": "DIAGNOSIS",
      "description": "Shelf allocation likely insufficient"
    },
    {
      "timestamp": "2026-10-10T08:00:07Z",
      "phase": "simulate",
      "type": "SIMULATION",
      "description": "Scenario B: facings 2→4, replenish +12"
    },
    {
      "timestamp": "2026-10-10T08:00:08Z",
      "phase": "simulate",
      "type": "SELECTION",
      "description": "Scenario B selected (score: 78.5)"
    },
    {
      "timestamp": "2026-10-10T08:00:09Z",
      "phase": "dcg",
      "type": "GUARD",
      "description": "ALLOW"
    },
    {
      "timestamp": "2026-10-10T08:00:15Z",
      "phase": "execute",
      "type": "ACTION",
      "description": "Facings 2→4; replenish +12"
    },
    {
      "timestamp": "2026-10-10T08:00:17Z",
      "phase": "verify",
      "type": "VERIFICATION",
      "description": "PASS - Expected state achieved"
    }
  ]
}
```

---

### Agent Operations (Future)

#### POST /agent/decision

Submit a decision for DCG validation.

**Request:**
```json
{
  "decision_id": "RT-D-1027",
  "agent_id": "retailtwin-orchestrator",
  "context_version": "store-001:v23871",
  "evidence": [
    {
      "type": "inventory",
      "entity_id": "P017",
      "version": "981",
      "value": {"shelf_quantity": 8, "backroom_quantity": 54}
    }
  ],
  "proposed_actions": [
    {
      "action_id": "RT-A-1042",
      "action_type": "replenish",
      "sku": "P017",
      "parameters": {"quantity": 12}
    },
    {
      "action_id": "RT-A-1043",
      "action_type": "change_facings",
      "sku": "P017",
      "parameters": {"facings": 4}
    }
  ],
  "simulation_id": "SIM-204"
}
```

**Response:**
```json
{
  "decision_id": "RT-D-1027",
  "outcome": "ALLOW",
  "authorization_id": "auth-xyz-789",
  "expires_at": "2026-10-10T08:01:30Z",
  "allowed_actions": [
    {
      "action_id": "RT-A-1042",
      "action_type": "replenish",
      "sku": "P017",
      "parameters": {"quantity": 12}
    },
    {
      "action_id": "RT-A-1043",
      "action_type": "change_facings",
      "sku": "P017",
      "parameters": {"facings": 4}
    }
  ],
  "validation_details": {
    "DECISION_INTEGRITY": "pass",
    "CONTEXT_VERSION": "pass",
    "FRESHNESS": "pass",
    "PHYSICAL_CONSTRAINTS": "pass",
    "AUTHORIZATION_POLICY": "pass"
  }
}
```

**Outcome Values:**
- `ALLOW` - Decision approved, execute with authorization
- `DENY` - Decision rejected, do not execute
- `REFRESH_REQUIRED` - Context changed, refresh evidence and retry
- `HUMAN_REVIEW` - High-risk action, requires human approval

---

#### POST /agent/execute

Execute authorized actions (called by Executor only).

**Request:**
```json
{
  "authorization_id": "auth-xyz-789",
  "actions": [
    {
      "action_id": "RT-A-1042",
      "action_type": "replenish",
      "sku": "P017",
      "parameters": {"quantity": 12}
    },
    {
      "action_id": "RT-A-1043",
      "action_type": "change_facings",
      "sku": "P017",
      "parameters": {"facings": 4}
    }
  ],
  "correlation_id": "run-20261010-001"
}
```

**Response:**
```json
{
  "execution_id": "exec-abc-123",
  "status": "committed",
  "committed_actions": [
    {
      "action_id": "RT-A-1042",
      "action_type": "replenish",
      "sku": "P017",
      "applied_at": "2026-10-10T08:00:15Z"
    },
    {
      "action_id": "RT-A-1043",
      "action_type": "change_facings",
      "sku": "P017",
      "applied_at": "2026-10-10T08:00:15Z"
    }
  ],
  "failed_actions": [],
  "context_version_before": "store-001:v23871",
  "context_version_after": "store-001:v23872",
  "execution_time_ms": 45,
  "correlation_id": "run-20261010-001"
}
```

**Error Responses:**
- `401 Unauthorized` - Invalid/expired authorization
- `409 Conflict` - Context version mismatch
- `422 Unprocessable Entity` - Invalid action parameters

---

### Simulation Operations (Future)

#### POST /simulation/create

Create a new simulation.

**Request:**
```json
{
  "simulation_id": "SIM-204",
  "from_version": "store-001:v23871",
  "description": "Weekend demand surge scenario"
}
```

**Response:**
```json
{
  "simulation_id": "SIM-204",
  "status": "created",
  "base_version": "store-001:v23871",
  "created_at": "2026-10-10T08:00:00Z"
}
```

---

#### POST /simulation/{simulation_id}/apply

Apply action to simulation.

**Request:**
```json
{
  "action_type": "change_facings",
  "sku": "P017",
  "parameters": {"facings": 4}
}
```

**Response:**
```json
{
  "simulation_id": "SIM-204",
  "action_applied": {
    "action_type": "change_facings",
    "sku": "P017",
    "parameters": {"facings": 4}
  },
  "resulting_state": {
    "sku": "P017",
    "facings": 4,
    "shelf_quantity": 8,
    "backroom_quantity": 54
  }
}
```

---

#### POST /simulation/{simulation_id}/evaluate

Evaluate simulation KPIs.

**Response:**
```json
{
  "simulation_id": "SIM-204",
  "composite_score": {
    "total_score": 78.5,
    "components": {
      "stockout_risk": 23.0,
      "service_level": 18.4,
      "demand_coverage": 12.75,
      "movement_cost": 9.6,
      "facings_score": 9.5,
      "revenue_impact": 5.25
    },
    "recommendation": "IMPLEMENT"
  },
  "kpis": {
    "stockout_probability": 0.12,
    "days_of_supply": 7.8,
    "service_level": 0.92,
    "movement_cost_usd": 8.50,
    "facings_score": 95
  }
}
```

---

## Error Handling

### Standard Error Response

```json
{
  "error": "error_code",
  "message": "Human readable message",
  "details": {},
  "request_id": "req-abc-123"
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `event_id_conflict` | 409 | Event ID exists with different payload |
| `authorization_not_found` | 404 | Authorization token not found |
| `authorization_expired` | 401 | Authorization token expired |
| `authorization_replay` | 401 | Nonce already used (replay attack) |
| `context_stale` | 409 | Context version mismatch |
| `action_not_authorized` | 403 | Action not in authorization |
| `invalid_action_params` | 400 | Invalid action parameters |
| `insufficient_inventory` | 422 | Cannot fulfill action |
| `shelf_capacity_exceeded` | 422 | Action would overflow shelf |
| `simulation_not_found` | 404 | Simulation ID not found |

---

## Rate Limiting

Currently no rate limiting for MVP. Production should implement:
- 100 requests/minute per IP
- 1000 requests/minute per API key

---

## API Client Examples

### Python

```python
import httpx

async def run_demo():
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000") as client:
        # Reset
        reset = await client.post("/demo/reset")
        print(reset.json())
        
        # Start demo
        start = await client.post("/demo/start")
        print(start.json())
        
        # Get status
        status = await client.get("/demo/status")
        print(status.json())
```

### JavaScript/TypeScript

```typescript
const API_BASE = 'http://127.0.0.1:8000';

async function runDemo() {
  // Reset
  const reset = await fetch(`${API_BASE}/demo/reset`, { method: 'POST' });
  console.log(await reset.json());
  
  // Start demo
  const start = await fetch(`${API_BASE}/demo/start`, { method: 'POST' });
  console.log(await start.json());
  
  // Get timeline
  const timeline = await fetch(`${API_BASE}/demo/timeline`);
  console.log(await timeline.json());
}
```

### cURL

```bash
# Reset demo
curl -X POST http://127.0.0.1:8000/demo/reset

# Start demo
curl -X POST http://127.0.0.1:8000/demo/start

# Start with stale context test
curl -X POST "http://127.0.0.1:8000/demo/start?stale_context_test=true"

# Get status
curl http://127.0.0.1:8000/demo/status

# Get timeline
curl http://127.0.0.1:8000/demo/timeline

# Get store state
curl http://127.0.0.1:8000/store

# Get inventory
curl http://127.0.0.1:8000/inventory/P017

# Health check
curl http://127.0.0.1:8000/health
```

---

## OpenAPI Schema

Full OpenAPI specification available at:
- Local: `http://127.0.0.1:8000/docs`
- Production: `https://retailtwin-api-*.a.run.app/docs`
