import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from .response import DatabaseHealthResponse

logger = logging.getLogger(__name__)


class CheckDatabaseHealthHandler:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def handle(self) -> DatabaseHealthResponse:
        try:
            await self._session.execute(select(1))
        except SQLAlchemyError as exc:
            logger.error("Database health check failed: %s", type(exc).__name__)
            return DatabaseHealthResponse(status="degraded", db="unavailable")
        return DatabaseHealthResponse(status="ok", db="ok")
