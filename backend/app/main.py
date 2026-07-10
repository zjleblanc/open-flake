import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.api.flake.attachment import router as attachment_router
from app.api.flake.catalog import router as catalog_router
from app.api.flake.catalog_admin import router as catalog_admin_router
from app.api.flake.cmdb import router as cmdb_router
from app.api.flake.oauth import router as oauth_router
from app.api.flake.schema import router as schema_router
from app.api.flake.table import router as table_router
from app.api.health import router as health_router
from app.api.v1.router import router as v1_router
from app.config import get_settings
from app.domain.errors import InvalidFieldNameError
from app.startup import lifespan

settings = get_settings()

logging.basicConfig(level=settings.log_level)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex)
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class LegacyApiPathMiddleware(BaseHTTPMiddleware):
    """Rewrite ServiceNow-compatible /api/now/* paths to /api/flake/*."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/now/"):
            request.scope["path"] = "/api/flake/" + path[len("/api/now/") :]
        elif path == "/api/now":
            request.scope["path"] = "/api/flake"
        return await call_next(request)


def create_app() -> FastAPI:
    app = FastAPI(
        title="OpenFlake",
        description="Open-source ServiceNow-compatible ITSM API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(LegacyApiPathMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        ProxyHeadersMiddleware,
        trusted_hosts=settings.trusted_proxy_list,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(oauth_router)
    app.include_router(table_router)
    app.include_router(attachment_router)
    app.include_router(cmdb_router)
    app.include_router(schema_router)
    app.include_router(catalog_router)
    app.include_router(catalog_admin_router)
    app.include_router(v1_router)

    @app.exception_handler(InvalidFieldNameError)
    async def invalid_field_name_handler(_request: Request, exc: InvalidFieldNameError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    return app


app = create_app()
