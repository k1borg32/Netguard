from .ping_query import PingQuery
from .ping_response import PingResponse


def handle(query: PingQuery) -> PingResponse:
    return PingResponse(status="ok")
