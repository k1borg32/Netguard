from fastapi import APIRouter

from .ping_handler import handle
from .ping_query import PingQuery
from .ping_response import PingResponse

router = APIRouter()


@router.get("/health/ping", response_model=PingResponse)
def ping() -> PingResponse:
    return handle(PingQuery())
