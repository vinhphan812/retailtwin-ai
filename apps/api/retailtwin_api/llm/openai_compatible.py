"""OpenAI-compatible adapter."""

import httpx

from .contracts import (
    LlmProvider,
    LlmRequest,
    LlmResponse,
    LlmToolCall,
    ProviderError,
    RequestTimeout,
    TokenUsage,
)

class OpenAiCompatibleProvider(LlmProvider):
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    async def complete(self, request: LlmRequest) -> LlmResponse:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": self.model,
            "messages": [m.model_dump() for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
            except httpx.TimeoutException:
                raise RequestTimeout()
            except httpx.HTTPError as e:
                raise ProviderError(str(e))

        data = response.json()
        choice = data["choices"][0]

        return LlmResponse(
            id=data["id"],
            model=data["model"],
            content=choice["message"].get("content"),
            finish_reason=choice["finish_reason"],
            tool_calls=[
                LlmToolCall(id=t["id"], name=t["function"]["name"], arguments=t["function"]["arguments"])
                for t in choice["message"].get("tool_calls", [])
            ],
            usage=TokenUsage(**data["usage"]),
            raw=data,
        )
