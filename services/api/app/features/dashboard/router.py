from fastapi import APIRouter

from .summary.controller import router as summary_router
from .timeseries.controller import router as timeseries_router

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])
router.include_router(summary_router)
router.include_router(timeseries_router)
