import pytest
from services.llm.factory import LLMRuntimeFactory
from services.llm.types import LLMProvider, LLMRequest, Message, MessageRole

@pytest.mark.anyio
async def test_mock_adapter():
    runtime = LLMRuntimeFactory.get_runtime(LLMProvider.MOCK)
    request = LLMRequest(
        messages=[Message(role=MessageRole.USER, content="Hello")],
        model="test-model",
        correlation_id="corr-123"
    )
    response = await runtime.generate(request)
    assert response.provider == LLMProvider.MOCK
    assert response.content == "Mocked response"
    assert response.correlation_id == "corr-123"

def test_invalid_provider():
    with pytest.raises(ValueError):
        LLMRuntimeFactory.get_runtime("INVALID") # type: ignore
