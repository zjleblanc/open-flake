import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.health import router as health_router
from app.api.snow.attachment import router as attachment_router
from app.api.snow.catalog import router as catalog_router
from app.api.snow.cmdb import router as cmdb_router
from app.api.snow.oauth import router as oauth_router
from app.api.snow.table import router as table_router
from app.api.v1.router import router as v1_router
from app.config import get_settings
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


def create_app() -> FastAPI:
    app = FastAPI(
        title="OpenFlake",
        description="Open-source ServiceNow-compatible ITSM API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(RequestIdMiddleware)
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
    app.include_router(catalog_router)
    app.include_router(v1_router)

    return app


app = create_app()
