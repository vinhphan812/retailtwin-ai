"""Tests for the provider-neutral LLM contracts and adapters."""

import asyncio

import httpx
import pytest
from pydantic import ValidationError

from retailtwin_api.llm.contracts import (
    ConfigurationError,
    LlmError,
    LlmMessage,
    LlmRequest,
    LlmResponse,
    LlmTool,
    ProviderError,
    RequestCancelled,
    RequestTimeout,
    StructuredOutput,
)
from retailtwin_api.llm.factory import LlmConfig, create_provider
from retailtwin_api.llm.openai_compatible import OpenAiCompatibleProvider
from retailtwin_api.llm.vertex import VertexProvider


class MockResponse:
    """Minimal successful OpenAI-compatible response."""

    def json(self) -> dict[str, object]:
        return {
            "id": "chatcmpl-123",
            "model": "gpt-4",
            "choices": [
                {
                    "message": {
                        "content": "Hello!",
                        "tool_calls": [
                            {
                                "id": "call-1",
                                "function": {
                                    "name": "get_inventory",
                                    "arguments": {"sku": "P017"},
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
            },
        }

    def raise_for_status(self) -> None:
        return None


class MockClient:
    """Async httpx client replacement with observable request data."""

    def __init__(self, response: MockResponse | Exception) -> None:
        self.response = response
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    async def __aenter__(self) -> "MockClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def post(self, *args: object, **kwargs: object) -> MockResponse:
        self.calls.append((args, kwargs))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def request() -> LlmRequest:
    return LlmRequest(
        model="gpt-4",
        messages=[LlmMessage(role="user", content="Hi")],
    )


def test_openai_adapter_success_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MockClient(MockResponse())
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)
    provider = create_provider(
        LlmConfig(
            provider="openai",
            model="gpt-4",
            api_key="test-key",
            base_url="https://example.test/v1/",
        )
    )

    response = asyncio.run(provider.complete(request()))

    assert isinstance(provider, OpenAiCompatibleProvider)
    assert response.content == "Hello!"
    assert response.usage.total_tokens == 2
    assert response.tool_calls[0].name == "get_inventory"
    assert response.tool_calls[0].arguments == {"sku": "P017"}
    assert client.calls[0][0] == ("https://example.test/v1/chat/completions",)
    assert client.calls[0][1]["headers"] == {"Authorization": "Bearer test-key"}


def test_openai_adapter_normalizes_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MockClient(httpx.TimeoutException("timed out"))
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)
    provider = OpenAiCompatibleProvider(
        base_url="https://example.test/v1",
        api_key="test-key",
        model="gpt-4",
        timeout=1,
    )

    with pytest.raises(RequestTimeout) as error:
        asyncio.run(provider.complete(request()))

    assert error.value.retryable is True


def test_openai_adapter_normalizes_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MockClient(httpx.ConnectError("unavailable"))
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)
    provider = OpenAiCompatibleProvider(
        base_url="https://example.test/v1",
        api_key="test-key",
        model="gpt-4",
        timeout=1,
    )

    with pytest.raises(ProviderError, match="unavailable"):
        asyncio.run(provider.complete(request()))


def test_vertex_requires_project_id() -> None:
    with pytest.raises(ConfigurationError, match="project_id"):
        create_provider(LlmConfig(provider="vertex", model="gemini-2.5-flash"))


def test_vertex_is_adc_boundary() -> None:
    provider = create_provider(
        LlmConfig(
            provider="vertex",
            model="gemini-2.5-flash",
            project_id="retailtwin-ai-511002",
        )
    )

    assert isinstance(provider, VertexProvider)
    assert provider.location == "us-central1"
    with pytest.raises(ProviderError, match="not implemented"):
        asyncio.run(provider.complete(request()))


@pytest.mark.parametrize(
    "config",
    [
        {"provider": "openai", "model": ""},
        {"provider": "openai", "model": "gpt-4", "timeout": 0},
    ],
)
def test_config_rejects_invalid_values(config: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        LlmConfig.model_validate(config)


# ─── contracts: LlmTool ───────────────────────────────────────────────────────

def test_llm_tool_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        LlmTool.model_validate(
            {"name": "test_tool", "description": None, "unknown_field": True}
        )


def test_llm_tool_empty_name_rejected() -> None:
    with pytest.raises(ValidationError):
        LlmTool.model_validate({"name": ""})


def test_llm_tool_minimal_valid() -> None:
    tool = LlmTool(name="get_store_state")
    assert tool.name == "get_store_state"
    assert tool.description is None


# ─── contracts: StructuredOutput ──────────────────────────────────────────────


def test_structured_output_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        StructuredOutput.model_validate(
            {"name": "Decision", "schema": {"type": "object"}, "strict": True, "x": 1}
        )


def test_structured_output_empty_name_rejected() -> None:
    with pytest.raises(ValidationError):
        StructuredOutput.model_validate({"name": "", "schema": {}})


# ─── contracts: LlmMessage ────────────────────────────────────────────────────


def test_llm_message_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        LlmMessage.model_validate(
            {"role": "user", "content": "hello", "extra": "ignored"}
        )


def test_llm_message_role_validation() -> None:
    LlmMessage(role="system", content="system prompt")
    LlmMessage(role="user", content="hello")
    LlmMessage(role="assistant", content="I am helpful")
    LlmMessage(role="tool", content="result", tool_call_id="call-1", name="get_store")


def test_llm_message_content_none_is_valid() -> None:
    msg = LlmMessage(role="assistant")
    assert msg.content is None


# ─── contracts: LlmRequest ─────────────────────────────────────────────────────


def test_llm_request_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        LlmRequest.model_validate(
            {
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "hi"}],
                "temperature": 0.5,
                "unknown": True,
            }
        )


def test_llm_request_temperature_bounds() -> None:
    LlmRequest.model_validate(
        {"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}], "temperature": 0.0}
    )
    LlmRequest.model_validate(
        {"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}], "temperature": 2.0}
    )
    with pytest.raises(ValidationError):
        LlmRequest.model_validate(
            {
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "hi"}],
                "temperature": -0.1,
            }
        )


def test_llm_request_max_tokens_positive() -> None:
    req = LlmRequest.model_validate(
        {"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1}
    )
    assert req.max_tokens == 1
    with pytest.raises(ValidationError):
        LlmRequest.model_validate(
            {
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 0,
            }
        )


# ─── contracts: LlmResponse ───────────────────────────────────────────────────


def test_llm_response_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        LlmResponse.model_validate(
            {
                "id": "resp-1",
                "model": "gpt-4",
                "content": "hello",
                "finish_reason": "stop",
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                "x": 1,
            }
        )


# ─── contracts: LlmError hierarchy ─────────────────────────────────────────────


def test_llm_error_attributes() -> None:
    err = LlmError("validation_error", "bad input")
    assert err.code == "validation_error"
    assert err.message == "bad input"
    assert err.retryable is False
    assert "bad input" in str(err)


def test_llm_error_retryable() -> None:
    err = LlmError("rate_limit", "slow down", retryable=True)
    assert err.retryable is True


def test_configuration_error_code() -> None:
    err = ConfigurationError("missing api_key")
    assert err.code == "configuration_error"
    assert err.retryable is False


def test_provider_error_retryable_false() -> None:
    err = ProviderError("connection refused")
    assert err.code == "provider_error"
    assert err.retryable is False


def test_provider_error_retryable_true() -> None:
    err = ProviderError("transient failure", retryable=True)
    assert err.retryable is True


def test_request_timeout_retryable() -> None:
    err = RequestTimeout()
    assert err.code == "timeout"
    assert err.retryable is True


def test_request_cancelled() -> None:
    err = RequestCancelled()
    assert err.code == "cancelled"
    assert err.retryable is False


# ─── contracts: LlmTransportResponse ─────────────────────────────────────────


def test_llm_transport_response() -> None:
    from retailtwin_api.llm.contracts import LlmTransportResponse

    resp = LlmTransportResponse(status_code=200)
    assert resp.status_code == 200
    assert resp.payload == {}

    resp2 = LlmTransportResponse(status_code=500, payload={"error": "server error"})
    assert resp2.status_code == 500
    assert resp2.payload == {"error": "server error"}


# ─── contracts: LlmProvider abstract boundary ─────────────────────────────────


def test_llm_provider_interface_exists() -> None:
    """Verify LlmProvider is importable and has the expected interface contract."""
    from retailtwin_api.llm.contracts import LlmProvider
    assert hasattr(LlmProvider, "complete")
    # concrete subclasses are tested through their own test cases

