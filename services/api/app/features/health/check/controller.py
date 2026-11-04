from fastapi import APIRouter, Response

from app.features.common.dependencies import Database

from .handler import HealthCheckHandler
from .query import HealthCheckQuery
from .response import HealthCheckResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    responses={503: {"model": HealthCheckResponse, "description": "Database unavailable"}},
    summary="API status including the database connection",
    description="Used by the Compose healthcheck and the dashboard. /health/ping only checks that the process runs.",
)
async def health(response: Response, session: Database) -> HealthCheckResponse:
    result = await HealthCheckHandler(session).handle(HealthCheckQuery())
    if result.status != "ok":
        response.status_code = 503
    return result
