from pydantic import BaseModel, Field
from services.llm.types import LLMProvider

class LLMConfig(BaseModel):
    provider: LLMProvider
    model: str = Field(min_length=1)
    endpoint: str | None = None
    timeout_seconds: float = Field(default=30.0, gt=0)
    max_retries: int = Field(default=2, ge=0)

    @classmethod
    def from_mapping(cls, values: dict) -> "LLMConfig":
        if not values.get("provider"):
            raise ValueError("LLM provider is required")
        try:
            return cls.model_validate(values)
        except Exception as exc:
            raise ValueError(f"Invalid LLM configuration: {exc}") from exc
