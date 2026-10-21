"""Compose auth routes; endpoint implementation stays inside each slice."""

from fastapi import APIRouter

from .login.controller import router as login_router
from .logout.controller import router as logout_router
from .me.controller import router as me_router
from .refresh.controller import router as refresh_router
from .register.controller import router as register_router

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
router.include_router(register_router)
router.include_router(login_router)
router.include_router(refresh_router)
router.include_router(logout_router)
router.include_router(me_router)
