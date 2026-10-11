from typing import Dict, Type
from services.llm.runtime import LLMRuntime
from services.llm.types import LLMProvider
from services.llm.adapters.openai import OpenAIAdapter
from services.llm.adapters.gemini import GeminiAdapter
from services.llm.adapters.mock import MockAdapter

class LLMRuntimeFactory:
    _adapters: Dict[LLMProvider, Type[LLMRuntime]] = {
        LLMProvider.OPENAI: OpenAIAdapter,
        LLMProvider.GEMINI: GeminiAdapter,
        LLMProvider.MOCK: MockAdapter,
    }

    @classmethod
    def get_runtime(cls, provider: LLMProvider, **kwargs) -> LLMRuntime:
        adapter_class = cls._adapters.get(provider)
        if not adapter_class:
            raise ValueError(f"No adapter found for provider: {provider}")
        return adapter_class(**kwargs)
