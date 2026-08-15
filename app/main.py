from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import analytics, applications, health, human_actions, jobs, profile, runs
from app.api.routes import settings as settings_routes
from app.core.config import get_settings
from app.core.logging import bind_correlation_id, clear_context, configure_logging, get_logger
from app.llm.health import check_llm_health
from app.scheduler.service import get_scheduler_service

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

    # Section 36: never let an unreachable/misconfigured LLM stop the app
    # from serving everything else — every route in this app works with
    # zero LLM dependency today, so a failed check here is logged and
    # nothing more.
    try:
        llm_status = await check_llm_health(
            base_url=settings.ollama_base_url, model=settings.ollama_model
        )
        logger.info("llm_health_check", **llm_status.model_dump())
    except Exception as exc:  # defense in depth: this must never abort startup
        logger.warning("llm_health_check_failed_unexpectedly", error=str(exc))

    scheduler = get_scheduler_service()
    scheduler.start()
    yield
    scheduler.shutdown()
    logger.info("app_shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Job Automation Platform",
        description="Local-first multi-agent job discovery, matching, and application automation.",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
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
    app.include_router(runs.router)
    app.include_router(applications.router)
    app.include_router(jobs.router)
    app.include_router(human_actions.router)
    app.include_router(analytics.router)
    app.include_router(settings_routes.router)

    return app


app = create_app()
