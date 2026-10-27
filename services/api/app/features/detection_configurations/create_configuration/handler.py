from uuid import uuid4

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.detection_configurations.common.response import DetectionConfigurationResponse
from app.infrastructure.persistence.tables import detection_configs

from .command import CreateConfigurationCommand


class CreateConfigurationHandler:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def handle(self, command: CreateConfigurationCommand) -> DetectionConfigurationResponse:
        result = await self._session.execute(
            insert(detection_configs)
            .values(
                configuration_id=uuid4(),
                detection_type=command.detection_type,
                method=command.method,
                parameters=command.parameters,
                active=False,
            )
            .returning(detection_configs)
        )
        response = DetectionConfigurationResponse.model_validate(result.mappings().one())
        await self._session.commit()
        return response
