from services.llm.runtime import LLMRuntime
from services.llm.types import LLMRequest, LLMResponse

class GeminiAdapter(LLMRuntime):
    def __init__(self, **kwargs):
        pass

    async def generate(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError("Gemini adapter not implemented yet")
