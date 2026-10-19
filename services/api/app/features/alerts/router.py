from fastapi import APIRouter

from .acknowledge.controller import router as acknowledge_router
from .get_alert.controller import router as get_alert_router
from .list_alerts.controller import router as list_alerts_router

router = APIRouter(prefix="/api/alerts", tags=["alerts"])
router.include_router(list_alerts_router)
router.include_router(get_alert_router)
router.include_router(acknowledge_router)
