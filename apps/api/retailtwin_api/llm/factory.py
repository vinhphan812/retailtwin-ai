"""Configuration and factory for LLM providers."""

from typing import Literal

from pydantic import BaseModel, Field

from .contracts import ConfigurationError, LlmProvider
from .openai_compatible import OpenAiCompatibleProvider
from .vertex import VertexProvider


class LlmConfig(BaseModel):
    """Configuration used to instantiate a provider adapter."""

    provider: Literal["openai", "vertex"]
    model: str = Field(min_length=1)
    base_url: str | None = None
    api_key: str | None = None
    project_id: str | None = None
    location: str = "us-central1"
    timeout: float = Field(default=30.0, gt=0)


def create_provider(config: LlmConfig) -> LlmProvider:
    """Create the configured inference adapter without performing inference."""
    if config.provider == "openai":
        return OpenAiCompatibleProvider(
            base_url=config.base_url or "https://api.openai.com/v1",
            api_key=config.api_key or "",
            model=config.model,
            timeout=config.timeout,
        )

    if not config.project_id:
        raise ConfigurationError("project_id is required for the Vertex provider")

    return VertexProvider(
        project_id=config.project_id,
        location=config.location,
        model=config.model,
        timeout=config.timeout,
    )
