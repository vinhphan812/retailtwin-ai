"""Provider-neutral contracts for model inference."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class LlmTool(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class StructuredOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    json_schema: dict[str, Any] = Field(alias="schema")
    strict: bool = True


class LlmMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    tool_call_id: str | None = None
    name: str | None = None


class LlmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str = Field(min_length=1)
    messages: list[LlmMessage] = Field(min_length=1)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, gt=0)
    tools: list[LlmTool] = Field(default_factory=list)
    structured_output: StructuredOutput | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class TokenUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)


class LlmToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    arguments: dict[str, Any]


class LlmResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    model: str
    content: str | None = None
    finish_reason: str | None = None
    tool_calls: list[LlmToolCall] = Field(default_factory=list)
    usage: TokenUsage = Field(default_factory=TokenUsage)
    raw: dict[str, Any] = Field(default_factory=dict)


class LlmError(Exception):
    """Normalized, safe inference error; provider payloads are not exposed."""

    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        self.code = code
        self.message = message
        self.retryable = retryable
        super().__init__(message)


class ConfigurationError(LlmError):
    def __init__(self, message: str) -> None:
        super().__init__("configuration_error", message)


class ProviderError(LlmError):
    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__("provider_error", message, retryable=retryable)


class RequestTimeout(LlmError):
    def __init__(self) -> None:
        super().__init__("timeout", "The model request timed out.", retryable=True)


class RequestCancelled(LlmError):
    def __init__(self) -> None:
        super().__init__("cancelled", "The model request was cancelled.")


class LlmTransportError(Exception):
    """Internal transport failure, normalized by an adapter."""


class LlmTransportResponse(BaseModel):
    status_code: int
    payload: dict[str, Any] = Field(default_factory=dict)


class LlmProvider:
    async def complete(self, request: LlmRequest) -> LlmResponse:
        raise NotImplementedError
