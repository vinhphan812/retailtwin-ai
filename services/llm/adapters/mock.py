from services.llm.runtime import LLMRuntime
from services.llm.types import LLMRequest, LLMResponse, LLMProvider, LLMUsage

class MockAdapter(LLMRuntime):
    def __init__(self, **kwargs):
        pass

    async def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            content="Mocked response",
            provider=LLMProvider.MOCK,
            model=request.model,
            usage=LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            correlation_id=request.correlation_id
        )
