from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.detection_configurations.common.response import DetectionConfigurationResponse
from app.features.detection_configurations.exceptions import DetectionConfigurationNotFoundError
from app.infrastructure.persistence.tables import detection_configs

from .query import GetConfigurationQuery


class GetConfigurationHandler:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def handle(self, query: GetConfigurationQuery) -> DetectionConfigurationResponse:
        result = await self._session.execute(
            select(detection_configs).where(detection_configs.c.configuration_id == query.configuration_id)
        )
        configuration = result.mappings().one_or_none()
        if configuration is None:
            raise DetectionConfigurationNotFoundError()
        return DetectionConfigurationResponse.model_validate(configuration)
