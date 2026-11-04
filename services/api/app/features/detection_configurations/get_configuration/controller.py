from uuid import UUID

from fastapi import APIRouter, Depends

from app.domain.user_role import UserRole
from app.features.auth.common.authentication import require_roles
from app.features.common.dependencies import Database
from app.features.detection_configurations.common.response import DetectionConfigurationResponse

from .handler import GetConfigurationHandler
from .query import GetConfigurationQuery

router = APIRouter()


@router.get(
    "/{id}",
    response_model=DetectionConfigurationResponse,
    dependencies=[Depends(require_roles(UserRole.USER, UserRole.ADMIN))],
    summary="Retrieve detection configuration details",
    description="Returns the stored configuration, complete JSON parameters and active status without modifying it.",
    responses={
        401: {"description": "Authentication required"},
        404: {"description": "Detection configuration not found"},
        422: {"description": "Invalid configuration UUID"},
        503: {"description": "Database storage unavailable"},
    },
)
async def get_configuration(id: UUID, session: Database) -> DetectionConfigurationResponse:
    return await GetConfigurationHandler(session).handle(GetConfigurationQuery(id))
