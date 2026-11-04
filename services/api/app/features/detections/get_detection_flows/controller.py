from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.features.common.dependencies import Database

from .handler import GetDetectionFlowsHandler
from .query import GetDetectionFlowsQuery
from .request import GetDetectionFlowsRequest
from .response import GetDetectionFlowsResponse

router = APIRouter()


@router.get(
    "/{id}/flows",
    response_model=GetDetectionFlowsResponse,
    summary="Retrieve flows associated with a detection",
    description=(
        "Matches network_flows.trace_id against the detection's stored trace_ids. "
        "These trace IDs are an evidence sample; total counts matching stored flows. "
        "Returns an empty page when an existing detection has no matching flows. "
        "Sort by ts_start, then flow_id in the same direction; newest first by default. "
        "No token needed for now."
    ),
    responses={
        404: {"description": "Detection not found"},
        422: {"description": "Invalid detection UUID, pagination or sort order"},
        503: {"description": "Database storage unavailable"},
    },
)
async def get_detection_flows(
    id: UUID,
    request: Annotated[GetDetectionFlowsRequest, Query()],
    session: Database,
) -> GetDetectionFlowsResponse:
    return await GetDetectionFlowsHandler(session).handle(
        GetDetectionFlowsQuery(
            detection_id=id,
            page=request.page,
            page_size=request.page_size,
            sort_order=request.sort_order,
        )
    )
