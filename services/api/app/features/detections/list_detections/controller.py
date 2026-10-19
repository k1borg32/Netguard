from typing import Annotated

from fastapi import APIRouter, Query

from app.features.common.dependencies import Database

from .handler import ListDetectionsHandler
from .query import ListDetectionsQuery
from .response import DetectionResponse

router = APIRouter()


@router.get(
    "",
    response_model=list[DetectionResponse],
    summary="Latest detections, newest first",
    description=(
        "No token needed for now: the placeholder dashboard and the full-stack tests read it. "
        "It gets the same role check as alerts once the dashboard has a login."
    ),
    responses={
        422: {"description": "Invalid limit"},
        503: {"description": "Database storage unavailable"},
    },
)
async def list_detections(
    session: Database,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> list[DetectionResponse]:
    return await ListDetectionsHandler(session).handle(ListDetectionsQuery(limit))
