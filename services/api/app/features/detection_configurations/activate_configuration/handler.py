from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.detection_configurations.common.response import DetectionConfigurationResponse
from app.features.detection_configurations.exceptions import DetectionConfigurationNotFoundError
from app.infrastructure.persistence.tables import detection_configs

from .command import ActivateConfigurationCommand


class ActivateConfigurationHandler:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def handle(self, command: ActivateConfigurationCommand) -> DetectionConfigurationResponse:
        result = await self._session.execute(
            update(detection_configs)
            .where(detection_configs.c.configuration_id == command.configuration_id)
            .values(active=True)
            .returning(detection_configs)
        )
        configuration = result.mappings().one_or_none()
        if configuration is None:
            raise DetectionConfigurationNotFoundError()
        response = DetectionConfigurationResponse.model_validate(configuration)
        await self._session.commit()
        return response
