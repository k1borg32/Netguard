from fastapi import APIRouter

from .handler import handle
from .query import PingQuery
from .response import PingResponse

router = APIRouter()


@router.get("/health/ping", response_model=PingResponse)
async def ping() -> PingResponse:
    return handle(PingQuery())
