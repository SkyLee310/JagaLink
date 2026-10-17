from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.errors import install_error_handlers
from app.core.settings import get_settings
from app.routers import health, layout, session


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="JagaLink API",
        version="0.1.0",
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/v1/docs",
        redoc_url=None,
    )
    # D-41: only the deployed frontend may call the API from a browser.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type"],
    )
    install_error_handlers(app)

    api = APIRouter(prefix="/api/v1")
    for module in (health, session, layout):
        api.include_router(module.router)
    app.include_router(api)
    return app


app = create_app()
