from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.domain.user_role import UserRole
from app.features.auth.common.authentication import require_roles
from app.features.common.dependencies import Database

from .handler import ListFlowsHandler
from .query import ListFlowsQuery
from .request import ListFlowsRequest
from .response import ListFlowsResponse

router = APIRouter()


@router.get(
    "",
    response_model=ListFlowsResponse,
    dependencies=[Depends(require_roles(UserRole.USER, UserRole.ADMIN))],
    summary="List flows with filtering, sorting and pagination",
    description=(
        "Filters are combined with AND. Time bounds apply to ts_start: start_time inclusive, end_time exclusive. "
        "IP addresses, ports and protocol use exact matches; protocol is case-sensitive. "
        "Sort by ts_start, then flow_id in the same direction."
    ),
    responses={
        401: {"description": "Authentication required"},
        422: {"description": "Invalid filters or pagination"},
        503: {"description": "Database storage unavailable"},
    },
)
async def list_flows(request: Annotated[ListFlowsRequest, Query()], session: Database) -> ListFlowsResponse:
    handler = ListFlowsHandler(session)
    return await handler.handle(
        ListFlowsQuery(
            start_time=request.start_time,
            end_time=request.end_time,
            src_ip=str(request.src_ip) if request.src_ip is not None else None,
            dst_ip=str(request.dst_ip) if request.dst_ip is not None else None,
            src_port=request.src_port,
            dst_port=request.dst_port,
            protocol=request.protocol,
            sort_order=request.sort_order,
            page=request.page,
            page_size=request.page_size,
        )
    )
