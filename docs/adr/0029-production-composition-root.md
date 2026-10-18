# ADR 0029: Production Composition Root

**Date:** 2026-10-18  
**Status:** Accepted  
**Issue:** [#214](https://github.com/vinhphan812/retailtwin-ai/issues/214)

## Context

The RetailTwin API must run in multiple environments:
- **Development**: In-memory Live Twin, fake LLM provider
- **Testing**: In-memory Live Twin, fake LLM provider  
- **Production (Cloud Run)**: Firestore Live Twin, Vertex AI Gemini

Currently, the application composition is scattered across `main.py` with ad-hoc environment checks. This creates risk of misconfiguration in production (e.g., accidentally using in-memory storage or a fake provider).

## Decision

We will create a unified `build_composition()` factory that wires the entire application based on the `APP_ENV` setting:

1. **Live Twin Repository**
   - Production (`APP_ENV=production`): `FirestoreLiveTwinRepository`
   - Dev/Test: `MemoryLiveTwinRepository`

2. **LLM Provider** (enforced by ADR 0020)
   - Production: Only `vertex_gemini` with ADC, rejects API keys
   - Dev/Test: `fake` or `openai_compatible`

3. **Analytics** (BigQuery)
   - Production: Query BigQuery for anomaly/revenue/promotion data
   - Dev/Test: In-memory stub adapters

4. **Event Pipe**
   - All environments: `MemoryPipe` (Pub/Sub is push-only in production)

The factory returns a `Composition` dataclass containing all wired dependencies. Any configuration error in production raises an exception (fail-closed).

## Consequences

### Positive
- Single source of truth for environment-specific wiring
- Fail-closed in production: misconfiguration raises at startup
- Easier testing: inject mock compositions
- Clear audit trail of what runs in production

### Negative
- Must update all callers of `create_app()` to use the new factory
- Need to ensure all environment variables are validated early

## Implementation

```python
# retailtwin_api/composition.py

@dataclass
class Composition:
    """Wired dependencies for the RetailTwin API."""
    settings: Settings
    store: StoreReader
    live_twin: LiveTwinRepository
    provider: LlmProvider | None
    registry: ToolRegistry
    analytics: AnalyticsRepositories
    event_pipe: EventPipe

def build_composition(settings: Settings) -> Composition:
    """Build the production composition root.
    
    Raises ConfigurationError in production on any misconfiguration.
    """
    # 1. Live Twin
    live_twin = _build_live_twin(settings)
    
    # 2. LLM Provider
    provider = _build_provider(settings)
    
    # 3. Analytics
    analytics = _build_analytics(settings)
    
    # 4. Event Pipe (always MemoryPipe)
    event_pipe = MemoryPipe()
    
    return Composition(...)

def _build_live_twin(settings: Settings) -> LiveTwinRepository:
    if settings.is_production:
        if settings.live_twin_backend != "firestore":
            raise ConfigurationError(
                "production requires LIVE_TWIN_BACKEND=firestore"
            )
        return FirestoreLiveTwinRepository()
    return MemoryLiveTwinRepository()

def _build_provider(settings: Settings) -> LlmProvider | None:
    if not settings.autonomy_enabled:
        return None
    config = llm_config_from_settings(settings)
    return create_provider(config)  # Enforces ADR 0020
```

## References

- ADR 0020: Register LLM providers and require Vertex ADC in production
- ADR 0018: Refresh evidence and replan after a stale rejection
- Issue #214: Production composition root
