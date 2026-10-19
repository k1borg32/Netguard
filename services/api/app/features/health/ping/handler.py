from .query import PingQuery
from .response import PingResponse


def handle(query: PingQuery) -> PingResponse:
    return PingResponse(status="ok")
