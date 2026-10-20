import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.errors import install_error_handlers
from app.core.pipeline import Pipelines
from app.core.settings import get_settings
from app.routers import (
    alerts,
    events,
    health,
    layout,
    rules,
    scenarios,
    session,
    stream,
    tracks,
)
from app.sim.runs import RunManager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Players and the stream hub live on this loop (D-77); routes reach them from worker threads.
    runs: RunManager = app.state.runs
    runs.bind(asyncio.get_running_loop())
    try:
        yield
    finally:
        await runs.shutdown()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="JagaLink API",
        version="0.1.0",
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/v1/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    pipelines = Pipelines(
        settings.track_ttl_s, settings.next_camera_weights, settings.multi_rule_severity
    )
    app.state.runs = RunManager(pipelines=pipelines)
    # D-41: only the deployed frontend may call the API from a browser.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type"],
    )
    install_error_handlers(app)

    api = APIRouter(prefix="/api/v1")
    for module in (health, session, layout, scenarios, events, tracks, rules, alerts, stream):
        api.include_router(module.router)
    app.include_router(api)
    return app


app = create_app()
