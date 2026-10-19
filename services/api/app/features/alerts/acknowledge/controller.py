from uuid import UUID

from fastapi import APIRouter, Depends

from app.domain.user_role import UserRole
from app.features.auth.common.authentication import require_roles
from app.features.common.dependencies import Database

from .command import AcknowledgeAlertCommand
from .handler import AcknowledgeAlertHandler
from .response import AcknowledgeAlertResponse

router = APIRouter()


@router.patch(
    "/{id}/acknowledge",
    response_model=AcknowledgeAlertResponse,
    dependencies=[Depends(require_roles(UserRole.USER, UserRole.ADMIN))],
    summary="Mark an alert as acknowledged",
    description="No request body. Repeated or concurrent acknowledgements preserve the first acknowledgement time.",
    responses={
        401: {"description": "Authentication required"},
        404: {"description": "Alert not found"},
        422: {"description": "Invalid alert UUID"},
        503: {"description": "Database storage unavailable"},
    },
)
async def acknowledge_alert(id: UUID, session: Database) -> AcknowledgeAlertResponse:
    handler = AcknowledgeAlertHandler(session)
    return await handler.handle(AcknowledgeAlertCommand(id))
