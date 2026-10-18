"""HTTP routes for the Flagship controller.

Three commands:

  POST /flagship/reset  → reseed the Live Twin to the canonical fixture
  POST /flagship/start  → run the autonomous chain end-to-end
  GET  /flagship/status → current phase, last result, timeline

Routes are mounted by ``register_routes`` so the same router can be attached
to any FastAPI app the controller is wired into.

## Idempotent Start Contract

The `/flagship/start` endpoint implements idempotent server start with retry logic:

### Server States
- **NOT_STARTED**: Server has never been started or was stopped
- **STARTING**: Start operation in progress (may include retries)
- **RUNNING**: Server is currently running

### Idempotency Guarantees
1. When a request arrives and server is already RUNNING, return immediately with cached state
2. When a request arrives during STARTING, return immediately with STARTING state
3. When a request arrives during NOT_STARTED, begin start process with retries

### Retry Logic
- Maximum 3 attempts using exponential backoff: 1s, 2s, 4s
- Retry only on transient failures (timeouts, connection errors)
- Non-transient errors fail immediately without retry

### Correlated Status Response
The API response includes a `status` field that frontend can read to coordinate:
- `status: "NOT_STARTED"` - Server not running
- `status: "STARTING"` - Start in progress (may include retry info)
- `status: "RUNNING"` - Server is running
- `status: "ERROR"` - Start failed with error

Response also includes:
- `correlation_id`: Client-provided or server-generated ID to track requests
- `retry_info`: Object with `attempt`, `max_attempts`, `next_retry_at` when retrying
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from enum import Enum
from typing import Any
from dataclasses import dataclass, field

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from retailtwin_api.flagship.controller import (
    FlagshipController,
    FlagshipRequest,
    FlagshipStateError,
    get_controller,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Server state enum and response models
# ---------------------------------------------------------------------


class ServerState(str, Enum):
    """Internal server state for idempotent start tracking.

    This is separate from FlagshipPhase which tracks the run state.
    ServerState tracks whether the server start process itself is in progress.
    """

    NOT_STARTED = "NOT_STARTED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"


@dataclass
class RetryInfo:
    """Information about retry state for frontend coordination."""

    attempt: int = Field(default=1, ge=1, le=3)
    max_attempts: int = Field(default=3, ge=1, le=3)
    next_retry_at: float | None = None
    backoff_delays: list[int] = field(default_factory=lambda: [1, 2, 4])


@dataclass
class IdempotentStartResponse:
    """Response model for idempotent start endpoint.

    The `status` field is the primary field frontend should read:
    - NOT_STARTED: Server not running, start not attempted
    - STARTING: Start in progress (may include retries)
    - RUNNING: Server is running
    - ERROR: Start failed

    The `correlation_id` field allows frontend to correlate requests.
    The `retry_info` field provides retry state when applicable.
    """

    status: ServerState
    correlation_id: str
    server_state: ServerState  # Alias for status (deprecated, use status)
    phase: str  # FlagshipPhase value for compatibility
    retry_info: RetryInfo | None = None
    message: str | None = None
    # Legacy fields for compatibility
    run_id: str | None = None
    error: str | None = None

router = APIRouter(prefix="/flagship", tags=["flagship"])


def _controller(request: Request) -> FlagshipController:
    controller = getattr(request.app.state, "flagship_controller", None)
    if controller is None:
        controller = get_controller()
    return controller


@router.post("/reset")
def reset_route(request: Request) -> dict[str, Any]:
    """Reseed the Live Twin via the controller's reset boundary."""

    controller = _controller(request)
    if not controller.is_configured:
        raise HTTPException(
            status_code=503,
            detail="flagship controller is not configured",
        )
    try:
        return controller.reset()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/start")
async def start_route(
    request: Request,
    body: FlagshipRequest | None = None,
) -> dict[str, Any]:
    """Drive the canonical chain with idempotent start logic.

    This endpoint implements idempotent server start:
    - Tracks server state internally (NOT_STARTED, STARTING, RUNNING)
    - Returns immediately if server is already RUNNING (idempotent)
    - Returns immediately if server is STARTING (prevents duplicate starts)
    - Implements retry with exponential backoff (1s, 2s, 4s) on transient failures

    The response includes a `status` field that frontend can read:
    - NOT_STARTED: Server not running
    - STARTING: Start in progress
    - RUNNING: Server is running

    Response also includes `retry_info` for frontend coordination during retries.
    """
    from retailtwin_api.flagship.controller import FlagshipPhase

    # Get or create the server state manager
    server_state_manager = _get_server_state_manager(request)

    # Check current server state for idempotency
    current_state = server_state_manager.get_state()

    # Idempotency: If already RUNNING, return immediately with cached state
    if current_state == ServerState.RUNNING:
        log.info("flagship.start.idempotent_skip_already_running correlation_id=%s",
                 body.correlation_id if body else None)
        return _build_idempotent_response(
            server_state=ServerState.RUNNING,
            correlation_id=body.correlation_id if body else None,
            phase=FlagshipPhase.COMPLETE.value,
            message="Server already running",
        )

    # Idempotency: If STARTING, return immediately without attempting another start
    if current_state == ServerState.STARTING:
        log.info("flagship.start.idempotent_skip_already_starting correlation_id=%s",
                 body.correlation_id if body else None)
        retry_info = server_state_manager.get_retry_info()
        return _build_idempotent_response(
            server_state=ServerState.STARTING,
            correlation_id=body.correlation_id if body else None,
            phase=FlagshipPhase.RUNNING.value,
            retry_info=retry_info,
            message="Server start already in progress",
        )

    # Server is NOT_STARTED - proceed with start and retries
    controller = _controller(request)
    if not controller.is_configured:
        raise HTTPException(
            status_code=503,
            detail="flagship controller is not configured",
        )

    request_body = body or FlagshipRequest()
    if os.environ.get("APP_ENV") == "production" and request_body.stale_block_enabled:
        # Defence-in-depth: refuse a deterministic stale-block injection
        # on the production wire, even if a caller sends stale_block_enabled: true.
        # The underlying helper raises RuntimeError under APP_ENV=production,
        # but reject it at the boundary instead of round-tripping to the helper.
        request_body = request_body.model_copy(update={"stale_block_enabled": False})
        log.warning("flagship.start.production_stale_block_refused correlation_id=%s", request_body.correlation_id)

    # Mark as STARTING
    correlation_id = request_body.correlation_id or f"run-{int(time.time())}"
    server_state_manager.set_state(ServerState.STARTING, correlation_id=correlation_id)

    # Retry configuration
    max_attempts = 3
    backoff_delays = [1, 2, 4]  # seconds: 1s, 2s, 4s
    last_error: str | None = None

    for attempt in range(1, max_attempts + 1):
        # Update retry info
        server_state_manager.set_retry_info(
            attempt=attempt,
            max_attempts=max_attempts,
            next_retry_at=time.time() + backoff_delays[attempt - 1] if attempt < max_attempts else None,
            backoff_delays=backoff_delays,
        )

        try:
            result = await controller.start(request_body)
            # Success - mark as RUNNING
            server_state_manager.set_state(ServerState.RUNNING, correlation_id=correlation_id)
            log.info("flagship.start.success correlation_id=%s attempt=%d", correlation_id, attempt)
            return _build_idempotent_response(
                server_state=ServerState.RUNNING,
                correlation_id=correlation_id,
                phase=result.phase.value if hasattr(result, 'phase') else FlagshipPhase.COMPLETE.value,
                message="Server started successfully",
                run_id=result.run_id if hasattr(result, 'run_id') else None,
            )
        except FlagshipStateError as exc:
            # Non-transient error - fail immediately without retry
            log.error("flagship.start.non_transient_error correlation_id=%s error=%s", correlation_id, str(exc))
            server_state_manager.set_state(ServerState.NOT_STARTED, correlation_id=correlation_id)
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except Exception as exc:
            # Transient error - check if we have retries left
            last_error = str(exc)
            log.warning("flagship.start.transient_error correlation_id=%s attempt=%d error=%s",
                        correlation_id, attempt, last_error)

            if attempt < max_attempts:
                # Wait with exponential backoff before next attempt
                delay = backoff_delays[attempt - 1]
                log.info("flagship.start.retry correlation_id=%s attempt=%d delay=%ds",
                         correlation_id, attempt + 1, delay)
                await asyncio.sleep(delay)
            else:
                # No retries left - mark as ERROR
                log.error("flagship.start.max_retries_exceeded correlation_id=%s error=%s",
                          correlation_id, last_error)
                server_state_manager.set_state(ServerState.NOT_STARTED, correlation_id=correlation_id)
                return _build_idempotent_response(
                    server_state=ServerState.NOT_STARTED,
                    correlation_id=correlation_id,
                    phase=FlagshipPhase.ERROR.value,
                    message="Server start failed after max retries",
                    error=last_error,
                )

    # Should not reach here, but handle gracefully
    return _build_idempotent_response(
        server_state=ServerState.NOT_STARTED,
        correlation_id=correlation_id,
        phase=FlagshipPhase.ERROR.value,
        message="Server start failed",
        error=last_error,
    )


# ---------------------------------------------------------------------
# Server state management
# ---------------------------------------------------------------------


class _ServerStateManager:
    """Manages server state for idempotent start tracking.

    This class is thread-safe and maintains state at the application level.
    """

    def __init__(self):
        import threading
        self._lock = threading.Lock()
        self._state: ServerState = ServerState.NOT_STARTED
        self._correlation_id: str | None = None
        self._retry_info: RetryInfo | None = None

    def get_state(self) -> ServerState:
        with self._lock:
            return self._state

    def set_state(self, state: ServerState, correlation_id: str | None = None) -> None:
        with self._lock:
            self._state = state
            if correlation_id:
                self._correlation_id = correlation_id

    def get_retry_info(self) -> RetryInfo | None:
        with self._lock:
            return self._retry_info

    def set_retry_info(
        self,
        attempt: int,
        max_attempts: int,
        next_retry_at: float | None,
        backoff_delays: list[int],
    ) -> None:
        with self._lock:
            self._retry_info = RetryInfo(
                attempt=attempt,
                max_attempts=max_attempts,
                next_retry_at=next_retry_at,
                backoff_delays=backoff_delays,
            )

    def reset(self) -> None:
        with self._lock:
            self._state = ServerState.NOT_STARTED
            self._correlation_id = None
            self._retry_info = None


# Global server state manager
_server_state_manager: _ServerStateManager | None = None
_server_state_manager_lock = threading.Lock()


def _get_server_state_manager(request: Request) -> _ServerStateManager:
    """Get or create the server state manager.

    Uses request.app.state for app-level state, or falls back to global singleton.
    """
    global _server_state_manager

    # Try to get from app state first (for proper app isolation)
    if hasattr(request.app, 'state'):
        app_state = getattr(request.app, 'state', None)
        if app_state is not None:
            manager = getattr(app_state, 'flagship_server_state_manager', None)
            if manager is not None:
                return manager

    # Fall back to global singleton
    with _server_state_manager_lock:
        if _server_state_manager is None:
            _server_state_manager = _ServerStateManager()
        return _server_state_manager


def _build_idempotent_response(
    server_state: ServerState,
    correlation_id: str | None,
    phase: str,
    retry_info: RetryInfo | None = None,
    message: str | None = None,
    run_id: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Build an idempotent start response."""
    from dataclasses import asdict

    response: dict[str, Any] = {
        "status": server_state.value,
        "server_state": server_state.value,
        "correlation_id": correlation_id or "",
        "phase": phase,
    }

    if retry_info:
        response["retry_info"] = asdict(retry_info)

    if message:
        response["message"] = message

    if run_id:
        response["run_id"] = run_id

    if error:
        response["error"] = error

    return response


@router.get("/status")
def status_route(request: Request) -> dict[str, Any]:
    """Return the current flagship phase and the last completed run."""

    controller = _controller(request)
    if not controller.is_configured:
        raise HTTPException(
            status_code=503,
            detail="flagship controller is not configured",
        )
    return _serialize(controller.status())


def _serialize(value: Any) -> dict[str, Any]:
    """Convert the dataclasses into JSON-friendly dictionaries."""

    from dataclasses import asdict, is_dataclass

    if is_dataclass(value):
        return asdict(value)  # type: ignore[arg-type]
    return value  # type: ignore[return-value]


def register_routes(app: Any) -> None:
    """Attach the flagship router to a FastAPI app instance.

    Called from ``main.create_app`` after the controller has been registered
    on ``app.state.flagship_controller``.
    """
    app.include_router(router)


# ---------------------------------------------------------------------
# Exports for testing
# ---------------------------------------------------------------------

__all__ = [
    "register_routes",
    "ServerState",
    "RetryInfo",
    "_ServerStateManager",  # Exported for testing
]
