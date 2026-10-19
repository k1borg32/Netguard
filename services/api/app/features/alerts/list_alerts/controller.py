from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.domain.user_role import UserRole
from app.features.auth.common.authentication import require_roles
from app.features.common.dependencies import Database

from .handler import ListAlertsHandler
from .query import ListAlertsQuery
from .request import ListAlertsRequest
from .response import ListAlertsResponse

router = APIRouter()


@router.get(
    "",
    response_model=ListAlertsResponse,
    dependencies=[Depends(require_roles(UserRole.USER, UserRole.ADMIN))],
    summary="List alerts with filtering, sorting and pagination",
    description=(
        "Filters are combined with AND. Time bounds apply to alert creation: start_time inclusive, end_time exclusive. "
        "Other detection filters use exact, case-sensitive matches. Sort by created_at, then alert_id in the same "
        "direction."
    ),
    responses={
        401: {"description": "Authentication required"},
        422: {"description": "Invalid filters or pagination"},
        503: {"description": "Database storage unavailable"},
    },
)
async def list_alerts(request: Annotated[ListAlertsRequest, Query()], session: Database) -> ListAlertsResponse:
    handler = ListAlertsHandler(session)
    return await handler.handle(
        ListAlertsQuery(
            start_time=request.start_time,
            end_time=request.end_time,
            status=request.status,
            severity=request.severity,
            detection_type=request.detection_type,
            src_ip=str(request.src_ip) if request.src_ip is not None else None,
            dst_ip=str(request.dst_ip) if request.dst_ip is not None else None,
            protocol=request.protocol,
            sort_order=request.sort_order,
            page=request.page,
            page_size=request.page_size,
        )
    )
