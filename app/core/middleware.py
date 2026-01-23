"""Middleware for request logging, exception handling, and more."""

import time
import uuid
from typing import Callable

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging all incoming requests."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request details and timing."""
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Log request start
        start_time = time.perf_counter()

        logger.info(
            "request_started",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            query_params=str(request.query_params),
            client_ip=request.client.host if request.client else None,
        )

        try:
            response = await call_next(request)

            # Calculate processing time
            process_time = time.perf_counter() - start_time

            # Log request completion
            logger.info(
                "request_completed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                process_time_ms=round(process_time * 1000, 2),
            )

            # Add headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = str(round(process_time * 1000, 2))

            return response

        except Exception as e:
            process_time = time.perf_counter() - start_time
            logger.error(
                "request_failed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                error=str(e),
                process_time_ms=round(process_time * 1000, 2),
            )
            raise


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Placeholder for rate limiting middleware.

    In production, implement with Redis-based rate limiting.
    """

    def __init__(self, app: FastAPI, requests_per_minute: int = 100):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        # In production, use Redis for distributed rate limiting
        self._request_counts: dict = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check rate limit before processing request."""
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        # Get client identifier (IP or user ID)
        client_id = request.client.host if request.client else "unknown"

        # Placeholder: In production, implement Redis-based rate limiting
        # For now, just pass through
        return await call_next(request)


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler for unhandled exceptions."""
    request_id = getattr(request.state, "request_id", "unknown")

    logger.error(
        "unhandled_exception",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        error=str(exc),
        error_type=type(exc).__name__,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": "An internal server error occurred",
            "error_code": "INTERNAL_ERROR",
            "request_id": request_id,
        },
    )


def setup_middleware(app: FastAPI) -> None:
    """Configure all middleware for the application."""

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Process-Time"],
    )

    # Request Logging Middleware
    app.add_middleware(RequestLoggingMiddleware)

    # Rate Limiting Middleware (placeholder)
    if settings.RATE_LIMIT_ENABLED:
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=settings.RATE_LIMIT_REQUESTS,
        )


class HTTPException(Exception):
    """Custom HTTP exception with additional fields."""

    def __init__(
        self,
        status_code: int,
        message: str,
        error_code: str = "ERROR",
        details: dict | None = None,
    ):
        self.status_code = status_code
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handler for custom HTTP exceptions."""
    request_id = getattr(request.state, "request_id", "unknown")

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.message,
            "error_code": exc.error_code,
            "details": exc.details,
            "request_id": request_id,
        },
    )
