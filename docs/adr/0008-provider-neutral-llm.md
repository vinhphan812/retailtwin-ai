# ADR-0008: Provider-Neutral LLM Runtime

## Status
Accepted

## Context
RetailTwin AI requires an abstraction layer for LLM interaction to support different providers (e.g., Vertex AI, OpenAI, local models) and improve local development and cost-efficiency.

## Decision
Introduce a provider-neutral interface `LLMProvider` in `services/ai`.

1. **Interface**: Define `LLMProvider` base class implementing a standard request/response contract.
    - Contracts must support: tools, tool definitions, tool results, and structured JSON/schema output.
    - Metadata requirements: must include provider, model, usage, and correlation IDs for all requests/responses.
    - Error handling: normalized error mapping, with explicit support for timeout, retry, and cancellation handling.
2. **Implementation (Future)**:
    - `VertexAIProvider`: Production implementation.
    - `OpenAICompatibleProvider`: Development/Testing implementation.
3. **Configuration**: Aligned to #85. Use `LLM_RUNTIME` settings for provider selection.

## Consequences
- Agents are decoupled from specific SDKs, improving maintainability.
- Development flow is enhanced through provider-neutral mocking/local models.
- Production stability is maintained by conforming to standardized contracts.
- Standardization of error handling, telemetry, and structured outputs ensures consistent behavior across providers.

## Implementation Tasks (Planned)
- [ ] Task 1: Create `services/ai/interface.py` defining `LLMProvider`.
- [ ] Task 2: Create `services/ai/factory.py` for provider initialization.
- [ ] Task 3: Implement `VertexAIProvider` and `OpenAICompatibleProvider` in `services/ai/providers/`.
- [ ] Task 4: Refactor Agents to inject `LLMProvider`.
