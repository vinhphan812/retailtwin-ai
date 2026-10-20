"""One JSON error envelope for every failed request."""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def error_payload(
    code: str,
    message: str,
    details: list[dict[str, str]] | None = None,
    *,
    path: str | None = None,
    method: str | None = None,
) -> dict[str, object]:
    error: dict[str, object] = {"code": code, "message": message}
    if details:
        error["details"] = details
    if path is not None:
        error["path"] = path
    if method is not None:
        error["method"] = method
    return {"error": error}


def api_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, ApiError):
        raise exc
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(exc.code, exc.message, path=request.url.path, method=request.method),
    )


def http_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):
        raise exc
    message = exc.detail if isinstance(exc.detail, str) else "Request failed."
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload("http_error", message, path=request.url.path, method=request.method),
    )


def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    details: list[dict[str, str]] = []
    # Build a map of field -> expected format for better messages
    field_hints = _build_field_hints(exc)
    for item in exc.errors():
        loc = [str(part) for part in item.get("loc", []) if part != "body"]
        field = ".".join(loc) if loc else "body"
        msg = str(item.get("msg", "Invalid value"))
        # Add hint if available
        hint = field_hints.get(field)
        if hint:
            msg = f"{msg}. {hint}"
        details.append(
            {
                "field": field,
                "message": msg,
                "type": str(item.get("type", "unknown")),
            }
        )
    return JSONResponse(
        status_code=422,
        content=error_payload(
            "validation_error",
            f"Invalid parameters for {request.method} {request.url.path}.",
            details,
            path=request.url.path,
            method=request.method,
        ),
    )


def _build_field_hints(exc: RequestValidationError) -> dict[str, str]:
    """Extract expected formats from validation error context for better messages."""
    hints: dict[str, str] = {}
    for error in exc.errors():
        loc = [str(part) for part in error.get("loc", []) if part != "body"]
        field = ".".join(loc) if loc else "body"
        # Add contextual hints based on the type of validation failure
        error_type = str(error.get("type", ""))
        if "enum" in error_type:
            expected = error.get("ctx", {}).get("expected", "valid values")
            hints[field] = f"Expected one of: {expected}."
        elif "datetime" in error_type or "time" in error_type.lower():
            hints[field] = "Use ISO-8601 format with timezone (e.g., 2024-01-15T00:00:00Z or 2024-01-15T00:00:00+00:00)."
        elif "min_length" in error_type:
            hints[field] = "Must be at least 1 character."
        elif "missing" in error_type:
            hints[field] = "This field is required."
    return hints
