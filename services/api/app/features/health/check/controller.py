from fastapi import APIRouter

from app.features.common.dependencies import Database

from .handler import HealthCheckHandler
from .query import HealthCheckQuery
from .response import HealthCheckResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="API status including the database connection",
    description="Used by the Compose healthcheck and the dashboard. /health/ping only checks that the process runs.",
)
async def health(session: Database) -> HealthCheckResponse:
    return await HealthCheckHandler(session).handle(HealthCheckQuery())
