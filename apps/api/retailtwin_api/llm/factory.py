"""Configuration and factory for LLM providers."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from .contracts import LlmProvider
from .openai_compatible import OpenAiCompatibleProvider
from .vertex import VertexProvider

class LlmConfig(BaseModel):
    provider: Literal["openai", "vertex"]
    model: str
    base_url: str | None = None
    api_key: str | None = None
    project_id: str | None = None
    location: str = "us-central1"
    timeout: float = 30.0

def create_provider(config: LlmConfig) -> LlmProvider:
    if config.provider == "openai":
        return OpenAiCompatibleProvider(
            base_url=config.base_url or "https://api.openai.com/v1",
            api_key=config.api_key or "",
            model=config.model,
            timeout=config.timeout,
        )
    elif config.provider == "vertex":
        if not config.project_id:
            raise ValueError("project_id required for Vertex provider")
        return VertexProvider(
            project_id=config.project_id,
            location=config.location,
            model=config.model,
            timeout=config.timeout,
        )
    raise ValueError(f"Unknown provider: {config.provider}")
