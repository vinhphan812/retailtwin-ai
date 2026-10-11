from abc import ABC, abstractmethod
from services.llm.types import LLMRequest, LLMResponse

class LLMRuntime(ABC):
    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        pass
