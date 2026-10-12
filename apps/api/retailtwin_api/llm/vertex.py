"""Vertex AI adapter boundary.

Production invocation is intentionally deferred until the Vertex SDK integration is
added. The adapter is configured for Application Default Credentials (ADC), which
Cloud Run supplies through its service identity; it never accepts key files.
"""

from .contracts import ProviderError, LlmProvider, LlmRequest, LlmResponse


class VertexProvider(LlmProvider):
    """Vertex provider configuration using ADC/Cloud Run identity."""

    def __init__(self, project_id: str, location: str, model: str, timeout: float) -> None:
        self.project_id = project_id
        self.location = location
        self.model = model
        self.timeout = timeout

    async def complete(self, request: LlmRequest) -> LlmResponse:
        """Fail closed until a Vertex SDK adapter is implemented and tested."""
        del request
        raise ProviderError("Vertex inference is not implemented.")
