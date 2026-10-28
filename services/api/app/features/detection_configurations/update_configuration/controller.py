from uuid import UUID

from fastapi import APIRouter, Depends

from app.domain.user_role import UserRole
from app.features.auth.common.authentication import require_roles
from app.features.common.dependencies import Database
from app.features.detection_configurations.common.response import DetectionConfigurationResponse

from .command import UpdateConfigurationCommand
from .handler import UpdateConfigurationHandler
from .request import UpdateConfigurationRequest

router = APIRouter()


@router.patch(
    "/{id}",
    response_model=DetectionConfigurationResponse,
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
    summary="Update detection configuration fields",
    description=(
        "Administrator only. Omitted fields retain their values. A supplied parameters object replaces the entire "
        "stored object; nested keys are not merged. An empty parameters object clears the parameters. "
        "Empty bodies, explicit nulls and unknown fields (including active and configuration_id) are rejected. "
        "Active status is unchanged; activation uses the dedicated PUT endpoint."
    ),
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Administrator role required"},
        404: {"description": "Detection configuration not found"},
        422: {"description": "Invalid configuration UUID or update body"},
        503: {"description": "Database storage unavailable"},
    },
)
async def update_configuration(
    id: UUID, request: UpdateConfigurationRequest, session: Database
) -> DetectionConfigurationResponse:
    return await UpdateConfigurationHandler(session).handle(
        UpdateConfigurationCommand(id, request.model_dump(exclude_unset=True))
    )
