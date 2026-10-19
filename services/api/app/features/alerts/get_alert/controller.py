from uuid import UUID

from fastapi import APIRouter, Depends

from app.domain.user_role import UserRole
from app.features.auth.common.authentication import require_roles
from app.features.common.dependencies import Database

from .handler import GetAlertHandler
from .query import GetAlertQuery
from .response import GetAlertResponse

router = APIRouter()


@router.get(
    "/{id}",
    response_model=GetAlertResponse,
    dependencies=[Depends(require_roles(UserRole.USER, UserRole.ADMIN))],
    summary="Retrieve an alert and its related detection",
    responses={
        401: {"description": "Authentication required"},
        404: {"description": "Alert not found"},
        422: {"description": "Invalid alert UUID"},
        503: {"description": "Database storage unavailable"},
    },
)
async def get_alert(id: UUID, session: Database) -> GetAlertResponse:
    handler = GetAlertHandler(session)
    return await handler.handle(GetAlertQuery(id))
