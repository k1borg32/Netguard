from typing import Annotated

from fastapi import APIRouter, Query

from app.features.common.dependencies import Database

from .handler import ListDetectionsHandler
from .query import ListDetectionsQuery
from .request import ListDetectionsRequest
from .response import ListDetectionsResponse

router = APIRouter()


@router.get(
    "",
    response_model=ListDetectionsResponse,
    summary="List detections with filtering, sorting and pagination",
    description=(
        "Filters are combined with AND. Time bounds apply to detection creation: start_time inclusive, "
        "end_time exclusive. Other filters use exact, case-sensitive matches. "
        "Sort by created_at, then detection_id in the same direction; newest first by default. "
        "Returns items, total matching detections, page and page_size. "
        "The legacy limit parameter is an alias for page_size; both must match if provided together. "
        "No token needed for now."
    ),
    responses={
        422: {"description": "Invalid filters or pagination"},
        503: {"description": "Database storage unavailable"},
    },
)
async def list_detections(
    request: Annotated[ListDetectionsRequest, Query()],
    session: Database,
) -> ListDetectionsResponse:
    return await ListDetectionsHandler(session).handle(
        ListDetectionsQuery(
            start_time=request.start_time,
            end_time=request.end_time,
            severity=request.severity,
            detection_type=request.detection_type,
            method=request.method,
            src_ip=str(request.src_ip) if request.src_ip is not None else None,
            dst_ip=str(request.dst_ip) if request.dst_ip is not None else None,
            protocol=request.protocol,
            sort_order=request.sort_order,
            page=request.page,
            page_size=request.effective_page_size,
        )
    )
