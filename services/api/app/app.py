from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.exception_handlers import app_exception_handler, database_exception_handler, validation_exception_handler
from app.features.auth.router import router as auth_router
from app.features.common.app_exception import AppException
from app.features.health.ping.controller import router as ping_router
from app.infrastructure.database import dispose_engine
from app.infrastructure.persistence.mappings import configure_mappings


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    configure_mappings()
    try:
        yield
    finally:
        await dispose_engine()


def create_app() -> FastAPI:
    configure_mappings()
    application = FastAPI(title="NetGuard API", version="0.1.0", lifespan=lifespan)
    application.add_exception_handler(AppException, app_exception_handler)
    application.add_exception_handler(RequestValidationError, validation_exception_handler)
    application.add_exception_handler(SQLAlchemyError, database_exception_handler)
    application.include_router(auth_router)
    application.include_router(ping_router)
    return application


app = create_app()


if __name__ == "__main__":
    import asyncio
    import sys

    import uvicorn

    # psycopg async connections require a selector event loop on Windows.
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    uvicorn.run(app, host="127.0.0.1", port=8000)
