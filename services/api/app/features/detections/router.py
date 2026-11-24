from fastapi import APIRouter, Depends

from app.domain.user_role import UserRole
from app.features.auth.common.authentication import require_roles

from .get_detection.controller import router as get_detection_router
from .get_detection_flows.controller import router as get_detection_flows_router
from .list_detections.controller import router as list_detections_router

router = APIRouter(
    tags=["detections"],
    dependencies=[Depends(require_roles(UserRole.USER, UserRole.ADMIN))],
    responses={401: {"description": "Missing, invalid or expired access token"}},
)
router.include_router(list_detections_router, prefix="/api/v1/detections")
router.include_router(get_detection_router, prefix="/api/v1/detections")
router.include_router(get_detection_flows_router, prefix="/api/v1/detections")
