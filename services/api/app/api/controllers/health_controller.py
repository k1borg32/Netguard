from fastapi import APIRouter

from app.features.health.ping.ping_handler import handle
from app.features.health.ping.ping_query import PingQuery
from app.features.health.ping.ping_response import PingResponse

router = APIRouter()


@router.get("/health/ping", response_model=PingResponse)
def ping() -> PingResponse:
    return handle(PingQuery())
