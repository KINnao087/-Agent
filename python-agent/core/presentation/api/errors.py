from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from core.shared.logging import get_logger

_logger = get_logger("api.errors")


def api_error(
    status_code: int,
    code: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "code": code,
            "message": message,
            "details": details or {},
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def handle_http_exception(
        request: Request,
        exc: HTTPException,
    ) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict):
            code = str(detail.get("code") or f"HTTP_{exc.status_code}")
            message = str(detail.get("message") or "Request failed")
            details = detail.get("details") or {}
        else:
            code = f"HTTP_{exc.status_code}"
            message = str(detail) if detail else "Request failed"
            details = {}

        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(
                status=exc.status_code,
                code=code,
                message=message,
                path=request.url.path,
                details=details,
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_exception(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_error_payload(
                status=422,
                code="VALIDATION_FAILED",
                message="Request validation failed",
                path=request.url.path,
                details={"errors": exc.errors()},
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        _logger.exception("Unhandled API exception: path=%s", request.url.path, exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=_error_payload(
                status=500,
                code="INTERNAL_SERVER_ERROR",
                message="Internal server error",
                path=request.url.path,
                details={},
            ),
        )


def _error_payload(
    *,
    status: int,
    code: str,
    message: str,
    path: str,
    details: dict[str, Any],
) -> dict[str, Any]:
    return {
        "status": status,
        "code": code,
        "message": message,
        "path": path,
        "details": details,
    }
