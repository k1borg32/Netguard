from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.alerts.exceptions import AlertNotFoundError
from app.infrastructure.persistence.tables import alerts

from .command import AcknowledgeAlertCommand
from .response import AcknowledgeAlertResponse


class AcknowledgeAlertHandler:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def handle(self, command: AcknowledgeAlertCommand) -> AcknowledgeAlertResponse:
        result = await self._session.execute(
            update(alerts)
            .where(alerts.c.alert_id == command.alert_id)
            .values(status="ACKNOWLEDGED", acknowledged_at=func.coalesce(alerts.c.acknowledged_at, func.now()))
            .returning(alerts)
        )
        alert = result.mappings().one_or_none()
        if alert is None:
            raise AlertNotFoundError()
        response = AcknowledgeAlertResponse.model_validate(alert)
        await self._session.commit()
        return response
