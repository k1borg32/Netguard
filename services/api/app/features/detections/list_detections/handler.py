from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.tables import detections

from .query import ListDetectionsQuery
from .response import DetectionResponse


class ListDetectionsHandler:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def handle(self, query: ListDetectionsQuery) -> list[DetectionResponse]:
        result = await self._session.execute(
            select(detections).order_by(detections.c.created_at.desc()).limit(query.limit)
        )
        return [DetectionResponse.model_validate(dict(row)) for row in result.mappings().all()]
