from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.detection import Detection
from app.features.detections.exceptions import DetectionNotFoundError

from .query import GetDetectionQuery
from .response import GetDetectionResponse


class GetDetectionHandler:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def handle(self, query: GetDetectionQuery) -> GetDetectionResponse:
        detection = await self._session.get(Detection, query.detection_id)
        if detection is None:
            raise DetectionNotFoundError()
        return GetDetectionResponse.model_validate(detection)
