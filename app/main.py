from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import health, profile
from app.core.config import get_settings
from app.core.logging import bind_correlation_id, clear_context, configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings)
    logger.info(
        "app_startup",
        app_env=settings.app_env,
        dry_run=settings.automation_dry_run,
        approval_mode=settings.approval_mode,
    )
    yield
    logger.info("app_shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Job Automation Platform",
        description="Local-first multi-agent job discovery, matching, and application automation.",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def correlation_id_middleware(request: Request, call_next):
        correlation_id = request.headers.get("x-correlation-id", str(uuid.uuid4()))
        bind_correlation_id(correlation_id, path=request.url.path, method=request.method)
        try:
            response = await call_next(request)
        finally:
            clear_context()
        response.headers["x-correlation-id"] = correlation_id
        return response

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_exception", error=str(exc), error_type=type(exc).__name__)
        return JSONResponse(status_code=500, content={"detail": "internal_server_error"})

    app.include_router(health.router)
    app.include_router(profile.router)

    return app


app = create_app()
