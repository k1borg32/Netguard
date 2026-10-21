from fastapi import APIRouter

from .get_detection.controller import router as get_detection_router
from .list_detections.controller import router as list_detections_router

router = APIRouter(tags=["detections"])
router.include_router(list_detections_router, prefix="/api/v1/detections")
router.include_router(get_detection_router, prefix="/api/v1/detections")
