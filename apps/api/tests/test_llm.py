"""Tests for LLM contracts and adapters."""

import pytest
from retailtwin_api.llm.contracts import LlmRequest, LlmMessage
from retailtwin_api.llm.factory import LlmConfig, create_provider
from retailtwin_api.llm.openai_compatible import OpenAiCompatibleProvider

@pytest.mark.asyncio
async def test_openai_adapter_success_mock(monkeypatch):
    # Mocking httpx.AsyncClient to avoid actual network calls
    class MockResponse:
        def __init__(self):
            self.status_code = 200
        
        def json(self):
            return {
                "id": "chatcmpl-123",
                "model": "gpt-4",
                "choices": [{"message": {"content": "Hello!"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}
            }
        
        async def __aenter__(self):
            return self
        
        async def __aexit__(self, *args):
            pass
            
        def raise_for_status(self):
            pass

    class MockClient:
        async def post(self, *args, **kwargs):
            return MockResponse()
        
        async def __aenter__(self):
            return self
        
        async def __aexit__(self, *args):
            pass

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: MockClient())

    config = LlmConfig(provider="openai", model="gpt-4", api_key="sk-123")
    provider = create_provider(config)
    assert isinstance(provider, OpenAiCompatibleProvider)
    
    request = LlmRequest(
        model="gpt-4",
        messages=[LlmMessage(role="user", content="Hi")]
    )
    
    response = await provider.complete(request)
    assert response.content == "Hello!"
    assert response.usage.total_tokens == 2
