from uuid import UUID

from fastapi import APIRouter

from app.features.common.dependencies import Database

from .handler import GetDetectionHandler
from .query import GetDetectionQuery
from .response import GetDetectionResponse

router = APIRouter()


@router.get(
    "/{id}",
    response_model=GetDetectionResponse,
    summary="Retrieve detection details",
    description=(
        "Returns the detection's classification, confidence, ingestion timestamps, network context, "
        "window, features, explanation and trace IDs. No token needed for now."
    ),
    responses={
        404: {"description": "Detection not found"},
        422: {"description": "Invalid detection UUID"},
        503: {"description": "Database storage unavailable"},
    },
)
async def get_detection(id: UUID, session: Database) -> GetDetectionResponse:
    return await GetDetectionHandler(session).handle(GetDetectionQuery(id))
