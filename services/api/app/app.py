from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.api.controllers.auth_controller import router as auth_router
from app.api.controllers.health_controller import router as ping_router
from app.api.exception_handlers import app_exception_handler, validation_exception_handler
from app.features.common.app_exception import AppException

app = FastAPI(title="NetGuard API", version="0.1.0")
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.include_router(auth_router)
app.include_router(ping_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
    )
