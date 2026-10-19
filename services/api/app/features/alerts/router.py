from fastapi import APIRouter

from .acknowledge.controller import router as acknowledge_router
from .get_alert.controller import router as get_alert_router
from .list_alerts.controller import router as list_alerts_router

PREFIX = "/api/alerts"

# The prefix goes on each include: FastAPI refuses a route with an empty path included without a prefix.
router = APIRouter(tags=["alerts"])
router.include_router(list_alerts_router, prefix=PREFIX)
router.include_router(get_alert_router, prefix=PREFIX)
router.include_router(acknowledge_router, prefix=PREFIX)
