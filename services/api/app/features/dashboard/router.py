from fastapi import APIRouter

from .summary.controller import router as summary_router

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
router.include_router(summary_router)
