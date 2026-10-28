from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.domain.user_role import UserRole
from app.features.auth.common.authentication import require_roles
from app.features.common.dependencies import Database

from .handler import ListConfigurationsHandler
from .query import ListConfigurationsQuery
from .request import ListConfigurationsRequest
from .response import ListConfigurationsResponse

router = APIRouter()


@router.get(
    "",
    response_model=ListConfigurationsResponse,
    dependencies=[Depends(require_roles(UserRole.USER, UserRole.ADMIN))],
    summary="List detection configurations",
    description=(
        "Exact, case-sensitive detection_type and method filters combine with active using AND. "
        "Results are ordered by configuration_id ascending by default. "
        "Returns the filtered total even for an empty or out-of-range page."
    ),
    responses={
        401: {"description": "Authentication required"},
        422: {"description": "Invalid filters or pagination"},
        503: {"description": "Database storage unavailable"},
    },
)
async def list_configurations(
    request: Annotated[ListConfigurationsRequest, Query()], session: Database
) -> ListConfigurationsResponse:
    return await ListConfigurationsHandler(session).handle(
        ListConfigurationsQuery(
            detection_type=request.detection_type,
            method=request.method,
            active=request.active,
            sort_order=request.sort_order,
            page=request.page,
            page_size=request.page_size,
        )
    )
