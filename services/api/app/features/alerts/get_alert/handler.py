from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.domain.alert import Alert
from app.features.alerts.exceptions import AlertNotFoundError

from .query import GetAlertQuery
from .response import GetAlertResponse


class GetAlertHandler:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def handle(self, query: GetAlertQuery) -> GetAlertResponse:
        alert = await self._session.scalar(
            select(Alert).where(Alert.alert_id == query.alert_id).options(joinedload(Alert.detection))
        )
        if alert is None:
            raise AlertNotFoundError()
        return GetAlertResponse.model_validate(alert)
