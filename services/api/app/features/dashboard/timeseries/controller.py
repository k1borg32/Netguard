from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.domain.user_role import UserRole
from app.features.auth.common.authentication import require_roles
from app.features.common.dependencies import Database

from .handler import GetDashboardTimeseriesHandler
from .query import GetDashboardTimeseriesQuery
from .request import DashboardTimeseriesRequest
from .response import DashboardTimeseriesResponse

router = APIRouter()


@router.get(
    "/timeseries",
    response_model=DashboardTimeseriesResponse,
    dependencies=[Depends(require_roles(UserRole.USER, UserRole.ADMIN))],
    summary="Count network flows and detections over time",
    description=(
        "Counts flows by ts_start and detections by created_at in [from, to). "
        "Defaults to the last 24 hours and 1h buckets. UTC-aligned buckets include "
        "empty and partial buckets; the first timestamp may precede from. "
        "Maximum range: 366 days and 2000 buckets."
    ),
    responses={
        401: {"description": "Authentication required"},
        422: {"description": "Invalid timestamps, range, interval or query size"},
        503: {"description": "Database storage unavailable"},
    },
)
async def timeseries(
    request: Annotated[DashboardTimeseriesRequest, Query()],
    session: Database,
) -> DashboardTimeseriesResponse:
    # Request validation resolves the optional start before application dispatch.
    assert request.start_time is not None
    handler = GetDashboardTimeseriesHandler(session)
    return await handler.handle(GetDashboardTimeseriesQuery(request.start_time, request.end_time, request.interval))
