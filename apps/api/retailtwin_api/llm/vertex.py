"""Vertex AI adapter."""

from .contracts import LlmProvider, LlmRequest, LlmResponse

class VertexProvider(LlmProvider):
    def __init__(self, project_id: str, location: str, model: str, timeout: float) -> None:
        self.project_id = project_id
        self.location = location
        self.model = model
        self.timeout = timeout

    async def complete(self, request: LlmRequest) -> LlmResponse:
        # TODO: Implement Vertex AI SDK integration (ADC)
        raise NotImplementedError("Vertex provider not yet implemented.")
