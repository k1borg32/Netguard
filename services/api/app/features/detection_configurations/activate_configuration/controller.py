from uuid import UUID

from fastapi import APIRouter, Depends

from app.domain.user_role import UserRole
from app.features.auth.common.authentication import require_roles
from app.features.common.dependencies import Database
from app.features.detection_configurations.common.response import DetectionConfigurationResponse

from .command import ActivateConfigurationCommand
from .handler import ActivateConfigurationHandler

router = APIRouter()


@router.put(
    "/{id}/activate",
    response_model=DetectionConfigurationResponse,
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
    summary="Activate a detection configuration",
    description=(
        "Administrator only. No request body. Atomically sets this configuration's active flag to true. "
        "Repeated and concurrent activation is idempotent. Other configurations remain unchanged; "
        "the current schema allows multiple enabled configurations. This operation persists settings "
        "and does not reload the running processor."
    ),
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Administrator role required"},
        404: {"description": "Detection configuration not found"},
        422: {"description": "Invalid configuration UUID"},
        503: {"description": "Database storage unavailable"},
    },
)
async def activate_configuration(id: UUID, session: Database) -> DetectionConfigurationResponse:
    return await ActivateConfigurationHandler(session).handle(ActivateConfigurationCommand(id))
