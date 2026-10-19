from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.domain.user_role import UserRole
from app.features.auth.common.authentication import require_roles
from app.features.common.dependencies import Database

from .handler import GetDashboardSummaryHandler
from .query import GetDashboardSummaryQuery
from .request import DashboardSummaryRequest
from .response import DashboardSummaryResponse

router = APIRouter()


@router.get(
    "/summary",
    response_model=DashboardSummaryResponse,
    dependencies=[Depends(require_roles(UserRole.USER, UserRole.ADMIN))],
    summary="Count flows, detections and alerts within a time range",
    description=(
        "Counts flows by ts_start and detections/alerts by their own created_at. "
        "The range includes start_time and excludes end_time. All alert statuses are counted."
    ),
    responses={
        401: {"description": "Authentication required"},
        422: {"description": "Invalid time range"},
        503: {"description": "Database storage unavailable"},
    },
)
async def summary(
    request: Annotated[DashboardSummaryRequest, Query()],
    session: Database,
) -> DashboardSummaryResponse:
    handler = GetDashboardSummaryHandler(session)
    return await handler.handle(GetDashboardSummaryQuery(request.start_time, request.end_time))
