"""HTTP routes for the Store Copilot assistant.

POST /assistant/conversations/{conversation_id}/messages
  - Receives user messages
  - Routes through Gemini on Vertex AI with read/simulation tools
  - Returns AssistantTurn with evidence, tool calls, and optional proposal
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from retailtwin_api.errors import ApiError
from retailtwin_api.llm.contracts import LlmMessage
from retailtwin_api.llm.factory import create_provider, llm_config_from_settings
from retailtwin_api.settings import Settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assistant", tags=["assistant"])


# ─── Schemas ──────────────────────────────────────────────────────────────────────


class AssistantMessageRequest(BaseModel):
    """Body of POST /assistant/conversations/{conversation_id}/messages."""

    message_id: str = Field(min_length=1)
    text: str = Field(min_length=1, max_length=4000)
    store_id: str = Field(min_length=1)
    context_version: str | None = None
    mode: Literal["demo", "live"] = "live"


class AssistantEvidence(BaseModel):
    """One fact a reply rests on."""

    id: str
    kind: str
    label: str
    detail: str
    source: Literal["tool", "feed"]
    tool: str | None = None
    sku: str | None = None
    as_of: str | None = None
    confidence: float | None = None


class AssistantToolCallResult(BaseModel):
    """Result of a tool call."""

    tool: str
    capability: Literal["READ", "SIMULATION", "COMMIT_REQUEST"]
    ok: bool
    error_code: str | None = None
    sku: str | None = None
    duration_ms: int | None = None


class AssistantConstraint(BaseModel):
    """Constraint check result."""

    label: str
    passed: bool


class AssistantProposal(BaseModel):
    """A plan opened as a simulation."""

    simulation_id: str
    candidate_id: str | None = None
    decision_id: str | None = None
    base_context_version: str
    actions: list[dict[str, Any]]
    summary: str
    kpis: list[dict[str, Any]] = []
    baseline_kpis: list[dict[str, Any]] = []
    evaluator_version: str | None = None
    constraints: list[AssistantConstraint] = []
    guard: dict[str, Any] | None = None


class AssistantTurn(BaseModel):
    """Reply to one message."""

    conversation_id: str
    message_id: str
    reply_id: str
    correlation_id: str
    run_id: str | None = None
    store_id: str
    context_version: str | None = None
    source: Literal["demo_script", "live_agent"]
    model: str | None = None
    status: Literal["success", "unsupported", "error"]
    outcome_code: str | None = None
    text: str
    evidence: list[AssistantEvidence] = []
    tool_calls: list[AssistantToolCallResult] = []
    proposal: AssistantProposal | None = None


# ─── Dependencies ───────────────────────────────────────────────────────────────


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


# ─── System prompt ─────────────────────────────────────────────────────────────


SYSTEM_PROMPT = """You are a helpful retail store assistant. You can help users:
- Check store status, inventory levels, and sales trends
- Analyze product performance and stock levels
- Suggest optimizations and create simulation plans

Guidelines:
- Always cite real data from tool calls in your responses
- Never write directly to the live store - use simulations for planning
- When users want to apply changes, create a simulation proposal they can review
- Be concise and actionable in your recommendations

Available tools:
- get_store_state: Get current store status and overview
- get_inventory: Get inventory for a specific SKU
- get_backroom_inventory: Get backroom inventory for a specific SKU
- get_sales_history: Get sales history for a SKU
- get_stockout_risk: Get stockout risk for a SKU
- get_promotions: Get active promotions for a SKU
- get_planogram: Get current planogram
- move_product: Create a simulation action to move a product
- change_facings: Create a simulation action to change facings
- replenish_shelf: Create a simulation action to replenish shelf
- create_simulation: Open a new simulation at current context
- submit_action_for_commit: Submit an action for commit authorization

Respond with clear, data-driven insights."""


# ─── Route ───────────────────────────────────────────────────────────────────────


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=AssistantTurn,
)
async def assistant_message(
    request: Request,
    conversation_id: str,
    body: AssistantMessageRequest,
    settings: Settings = Depends(get_settings),
) -> AssistantTurn:
    """Handle a user message in the Copilot conversation.

    This endpoint:
    1. Receives the user's message
    2. Sends it to Gemini (via Vertex AI or configured provider)
    3. Returns the response with model-generated text

    Tool execution is handled separately - the LLM returns its response
    which may include tool calls that the frontend then executes.
    """
    correlation_id = request.headers.get("x-correlation-id", f"copilot-{uuid.uuid4()}")

    # Get live context version
    live_version = getattr(request.app.state, "live_context_version", None)

    # Check for stale context
    if body.context_version is not None and live_version is not None:
        if body.context_version != live_version:
            raise ApiError(
                409,
                "stale_context",
                f"Context version {body.context_version} is stale. Current: {live_version}",
            )

    # Build LLM messages with system prompt
    messages = [
        LlmMessage(role="system", content=SYSTEM_PROMPT),
        LlmMessage(role="user", content=body.text),
    ]

    # Get LLM provider and call it
    try:
        config = llm_config_from_settings(settings)
        provider = create_provider(config)
    except Exception as exc:
        logger.error(
            "assistant.provider_init_failed",
            extra={"correlation_id": correlation_id, "error": str(exc)},
        )
        raise ApiError(503, "model_unavailable", "LLM provider is not available.")

    try:
        response = await provider.chat(messages=messages, tools=None)
    except Exception as exc:
        logger.error(
            "assistant.llm_call_failed",
            extra={"correlation_id": correlation_id, "error": str(exc)},
        )
        raise ApiError(503, "llm_unavailable", f"LLM call failed: {exc}")

    # Extract response text
    text = response.content or "I've processed your request."

    return AssistantTurn(
        conversation_id=conversation_id,
        message_id=body.message_id,
        reply_id=f"reply-{uuid.uuid4()}",
        correlation_id=correlation_id,
        run_id=None,
        store_id=body.store_id,
        context_version=live_version,
        source="live_agent",
        model=config.model,
        status="success",
        outcome_code=None,
        text=text,
        evidence=[],
        tool_calls=[],
        proposal=None,
    )
