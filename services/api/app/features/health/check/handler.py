from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from .query import HealthCheckQuery
from .response import HealthCheckResponse


class HealthCheckHandler:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def handle(self, query: HealthCheckQuery) -> HealthCheckResponse:
        try:
            await self._session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            # Reported instead of raised: the Compose healthcheck reads the status field.
            return HealthCheckResponse(status="degraded", db="unavailable")
        return HealthCheckResponse(status="ok", db="ok")
