from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query
from pydantic import AwareDatetime

from app.domain.user_role import UserRole
from app.features.auth.common.authentication import require_roles
from app.features.common.dependencies import Database
from app.features.flows.common.response import FlowResponse

from .handler import GetFlowHandler
from .query import GetFlowQuery

router = APIRouter()


@router.get(
    "/{flowId}",
    response_model=FlowResponse,
    dependencies=[Depends(require_roles(UserRole.USER, UserRole.ADMIN))],
    summary="Retrieve a flow by its identifier and start time",
    description="Both flowId and timezone-aware tsStart are required to identify the flow's composite key.",
    responses={
        401: {"description": "Authentication required"},
        404: {"description": "Flow not found"},
        422: {"description": "Invalid flow UUID or missing/invalid tsStart"},
        503: {"description": "Database storage unavailable"},
    },
)
async def get_flow(
    flow_id: Annotated[UUID, Path(alias="flowId")],
    ts_start: Annotated[
        AwareDatetime, Query(alias="tsStart", description="Flow start time, with timezone (ISO 8601).")
    ],
    session: Database,
) -> FlowResponse:
    handler = GetFlowHandler(session)
    return await handler.handle(GetFlowQuery(flow_id, ts_start))
