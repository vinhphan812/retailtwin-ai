"""Vertex AI Gemini adapter — uses Application Default Credentials (ADC).

ADC is supplied automatically by Cloud Run's service identity (no key files).
For local development, authenticate with:
    gcloud auth application-default login
or
    gcloud auth application-default login --impersonate-service-account=<SERVICE-ACCOUNT>

The adapter calls the Vertex AI REST API endpoint:
    POST https://{location}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{location}/publishers/google/models/{model}:rawPredict

Reference:
  https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/inference
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx

from .contracts import (
    AuthenticationError,
    InvalidStructuredOutputError,
    LlmMessage,
    LlmProvider,
    LlmRequest,
    LlmResponse,
    LlmToolCall,
    ProviderError,
    RateLimitError,
    RequestTimeout,
    StructuredOutput,
    TokenUsage,
    ToolCallError,
)

_logger = logging.getLogger(__name__)

# Vertex AI REST API endpoint base
_VERTEX_API_BASE = "https://{location}-aiplatform.googleapis.com/v1"

# Retry configuration
_MAX_RETRIES = 3
_INITIAL_BACKOFF = 1.0  # seconds


def _backoff(attempt: int) -> float:
    """Exponential back-off with jitter cap at 32 s."""
    return min(_INITIAL_BACKOFF * (2 ** attempt), 32.0)


def _vertex_error_to_exception(status_code: int, payload: dict[str, Any]) -> ProviderError:
    """Map Vertex AI error responses to the appropriate typed exception."""
    error_msg = payload.get("error", {}).get("message", str(payload))
    code = payload.get("error", {}).get("code", 0)
    if status_code == 401 or code == "UNAUTHENTICATED":
        return AuthenticationError(error_msg)
    if status_code == 403 or code == "PERMISSION_DENIED":
        return AuthenticationError(f"Permission denied: {error_msg}")
    if status_code == 429 or code == "RESOURCE_EXHAUSTED":
        return RateLimitError(error_msg)
    if status_code == 400 and (
        "function_declaration" in error_msg.lower()
        or "schema" in error_msg.lower()
        or "structured" in error_msg.lower()
    ):
        return InvalidStructuredOutputError(error_msg)
    return ProviderError(error_msg, retryable=status_code >= 500)


def _convert_tools_vertex(tools: list) -> list[dict[str, Any]]:
    """Convert LlmTool definitions to Vertex AI function_declarations format."""
    declarations = []
    for tool in tools:
        declarations.append({
            "name": tool.name,
            "description": tool.description or "",
            "parameters": {
                "type": "object",
                "properties": tool.parameters.get("properties", {}),
                "required": tool.parameters.get("required", []),
            },
        })
    return declarations


def _normalize_vertex_tool_calls(
    candidates: list[dict[str, Any]],
) -> tuple[list[LlmToolCall], str | None]:
    """Extract tool calls from Vertex candidates; return (tool_calls, finish_reason)."""
    tool_calls: list[LlmToolCall] = []
    finish_reason: str | None = None

    for candidate in candidates:
        finish_reason = candidate.get("finishReason", "OTHER")
        content_parts = candidate.get("content", {}).get("parts", [])
        for part in content_parts:
            fc = part.get("functionCall")
            if fc:
                args_raw = fc.get("args", {})
                if isinstance(args_raw, str):
                    try:
                        args: dict[str, Any] = json.loads(args_raw)
                    except json.JSONDecodeError:
                        raise ToolCallError(
                            f"Malformed function_call arguments for '{fc.get('name')}': not valid JSON"
                        )
                elif isinstance(args_raw, dict):
                    args = args_raw
                else:
                    raise ToolCallError(
                        f"Unexpected function_call arguments type for '{fc.get('name')}'"
                    )
                tool_calls.append(
                    LlmToolCall(
                        id=fc.get("name", "unknown"),
                        name=fc["name"],
                        arguments=args,
                    )
                )

    return tool_calls, finish_reason


def _vertex_content_to_text(candidates: list[dict[str, Any]]) -> str | None:
    """Extract text content from Vertex candidates."""
    parts: list[str] = []
    for candidate in candidates:
        for part in candidate.get("content", {}).get("parts", []):
            text = part.get("text")
            if text:
                parts.append(text)
    return "\n".join(parts) or None


class VertexProvider(LlmProvider):
    """Vertex AI Gemini adapter using ADC.

    Supports:
      - Text completions
      - Tool-calling (function_declarations)
      - Structured output (response_schema)
      - Bounded retry with exponential back-off for rate-limit and 5xx errors
    """

    def __init__(
        self,
        project_id: str,
        location: str,
        model: str,
        timeout: float,
    ) -> None:
        self.project_id = project_id
        self.location = location
        self.model = model
        self.timeout = timeout
        self._endpoint = (
            f"{_VERTEX_API_BASE.format(location=location)}"
            f"/projects/{project_id}/locations/{location}"
            f"/publishers/google/models/{model}:rawPredict"
        )

    async def complete(self, request: LlmRequest) -> LlmResponse:
        """Call Vertex AI with bounded retry and response normalisation."""
        payload = self._build_payload(request)
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                return await self._do_request(payload, request)
            except RateLimitError as exc:
                last_exc = exc
                backoff_secs = _backoff(attempt)
                _logger.warning(
                    "Vertex rate-limit attempt %d/%d — sleeping %.1f s",
                    attempt + 1, _MAX_RETRIES, backoff_secs
                )
                await asyncio.sleep(backoff_secs)
            except AuthenticationError:
                raise  # Never retry auth failures
            except InvalidStructuredOutputError:
                raise  # Never retry output format errors
            except ToolCallError:
                raise  # Never retry malformed tool responses
            except RequestTimeout:
                raise  # Already typed correctly
            except ProviderError as exc:
                if exc.retryable and attempt < _MAX_RETRIES - 1:
                    last_exc = exc
                    backoff_secs = _backoff(attempt)
                    _logger.warning(
                        "Vertex retryable error attempt %d/%d — sleeping %.1f s: %s",
                        attempt + 1, _MAX_RETRIES, backoff_secs, exc.message
                    )
                    await asyncio.sleep(backoff_secs)
                else:
                    raise

        raise last_exc or ProviderError("Vertex inference failed after all retries.")

    async def _do_request(
        self,
        payload: dict[str, Any],
        request: LlmRequest,
    ) -> LlmResponse:
        headers = {"Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    self._endpoint,
                    headers=headers,
                    json=payload,
                )
            except httpx.TimeoutException:
                raise RequestTimeout()
            except httpx.HTTPError as e:
                raise ProviderError(str(e))

        if not response.is_success:
            try:
                error_payload_json = response.json()
            except Exception:
                error_payload_json = {}
            exc = _vertex_error_to_exception(response.status_code, error_payload_json)
            raise exc

        data = response.json()
        return self._parse_response(data, request)

    def _build_payload(self, request: LlmRequest) -> dict[str, Any]:
        messages = [_message_to_vertex(m) for m in request.messages]
        payload: dict[str, Any] = {
            "model": f"publishers/google/models/{self.model}",
            "messages": messages,
        }

        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_output_tokens"] = request.max_tokens

        if request.tools:
            payload["tools"] = [{"function_declarations": _convert_tools_vertex(request.tools)}]

        if request.structured_output:
            payload["response_format"] = {
                "name": request.structured_output.name,
                "schema": request.structured_output.schema,
            }

        return payload

    def _parse_response(
        self,
        data: dict[str, Any],
        request: LlmRequest,
    ) -> LlmResponse:
        candidates = data.get("candidates", [])
        if not candidates:
            error_detail = data.get("error", {}).get("message", "No candidates returned")
            raise ProviderError(error_detail)

        content = _vertex_content_to_text(candidates)

        tool_calls: list[LlmToolCall] = []
        finish_reason: str | None = None
        if request.tools or request.structured_output:
            tool_calls, finish_reason = _normalize_vertex_tool_calls(candidates)
        else:
            for c in candidates:
                finish_reason = c.get("finishReason", None)

        if request.structured_output and not tool_calls:
            if content and not request.tools:
                raise InvalidStructuredOutputError(
                    f"Model returned text instead of structured output. "
                    f"Response: {content[:200]}"
                )

        usage_data = data.get("usage", {})
        usage = TokenUsage(
            prompt_tokens=usage_data.get("promptTokens", 0),
            completion_tokens=usage_data.get("candidatesTokens", 0),
            total_tokens=usage_data.get("totalTokens", 0),
        )

        return LlmResponse(
            id=data.get("model", self.model),
            model=data.get("model", self.model),
            content=content,
            finish_reason=finish_reason,
            tool_calls=tool_calls,
            usage=usage,
            raw=data,
        )


def _message_to_vertex(message: LlmMessage) -> dict[str, Any]:
    """Convert an LlmMessage to Vertex AI message format."""
    role_map = {"system": "system", "user": "user", "assistant": "model", "tool": "user"}
    msg: dict[str, Any] = {"role": role_map[message.role]}

    if message.role == "tool":
        msg["content"] = json.dumps({
            "functionResponse": {
                "name": message.name or "unknown",
                "response": {"result": message.content or ""},
            }
        })
    elif message.tool_call_id:
        msg["content"] = json.dumps({
            "functionCall": {
                "id": message.tool_call_id,
                "name": message.name,
                "args": message.content,
            }
        })
    elif message.content:
        msg["content"] = message.content

    return msg
