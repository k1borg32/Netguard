from fastapi import APIRouter

from .list_detections.controller import router as list_detections_router

router = APIRouter(tags=["detections"])
router.include_router(list_detections_router, prefix="/api/v1/detections")
