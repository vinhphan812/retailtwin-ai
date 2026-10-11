# 0008: Implement provider-neutral LLM architecture

Date: 2026-10-11

## Status

Accepted

## Context
The current LLM architecture is tightly coupled to specific providers (e.g., direct Gemini/Vertex SDK calls). We need a provider-neutral request/response architecture to support tool calling, structured output, metadata, and normalized error handling across different LLM providers and runtime environments.

## Decision
We will implement an abstract provider-neutral LLM interface that:
- Defines a request/response structure supporting tool definitions, calls, and results.
- Enforces structured output via JSON schemas (Pydantic-compatible).
- Includes normalized usage, provider, correlation, and run metadata.
- Standardizes error, timeout, retry, and cancellation semantics.

## Consequences
- Implementation will allow swapping or adding LLM providers without changes to the core application logic.
- Increased complexity in the abstraction layer, but improved maintainability and testing.
- Future work will include implementing adapter-specific translations for the defined contracts.

- Pull request: https://github.com/vinhphan812/retailtwin-ai/pull/90
- Issue: #85
