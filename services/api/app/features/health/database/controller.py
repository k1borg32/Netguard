from fastapi import APIRouter, Response

from app.features.common.dependencies import Database

from .handler import CheckDatabaseHealthHandler
from .response import DatabaseHealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=DatabaseHealthResponse,
    responses={503: {"model": DatabaseHealthResponse, "description": "Database unavailable"}},
)
async def database_health(response: Response, session: Database) -> DatabaseHealthResponse:
    result = await CheckDatabaseHealthHandler(session).handle()
    if result.status != "ok":
        response.status_code = 503
    return result
