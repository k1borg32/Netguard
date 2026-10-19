"""Translate use-case and infrastructure errors at the HTTP boundary."""

import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.features.common.app_exception import AppException

logger = logging.getLogger(__name__)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    headers = {"WWW-Authenticate": "Bearer"} if exc.code == 401 else None
    return JSONResponse(status_code=exc.code, content={"detail": exc.message}, headers=headers)


async def database_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    # SQLAlchemy exceptions can include SQL parameters, including password hashes.
    logger.error("Database operation failed: %s", type(exc).__name__)
    return JSONResponse(status_code=503, content={"detail": "Database storage unavailable"})


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [{"loc": error["loc"], "msg": error["msg"], "type": error["type"]} for error in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})
