from fastapi import APIRouter, Depends, Response, status

from app.domain.user_role import UserRole
from app.features.auth.common.authentication import require_roles
from app.features.common.dependencies import Database
from app.features.detection_configurations.common.response import DetectionConfigurationResponse

from .command import CreateConfigurationCommand
from .handler import CreateConfigurationHandler
from .request import CreateConfigurationRequest

router = APIRouter()


@router.post(
    "",
    response_model=DetectionConfigurationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
    summary="Create an inactive detection configuration",
    description=(
        "Administrator only. Provide detection_type, method and a JSON object of parameters. "
        "Identifiers are trimmed and must contain 1-128 characters. "
        "The server generates configuration_id; new configurations are inactive. "
        "Use the activation endpoint to enable a configuration. Unknown fields are rejected."
    ),
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Administrator role required"},
        422: {"description": "Invalid configuration body"},
        503: {"description": "Database storage unavailable"},
    },
)
async def create_configuration(
    request: CreateConfigurationRequest, session: Database, response: Response
) -> DetectionConfigurationResponse:
    result = await CreateConfigurationHandler(session).handle(
        CreateConfigurationCommand(request.detection_type, request.method, request.parameters)
    )
    response.headers["Location"] = f"/api/v1/detection-configurations/{result.configuration_id}"
    return result
