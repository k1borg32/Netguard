from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.tables import alerts, detections, network_flows

from .query import GetDashboardSummaryQuery
from .response import DashboardSummaryResponse


class GetDashboardSummaryHandler:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def handle(self, query: GetDashboardSummaryQuery) -> DashboardSummaryResponse:
        # Independent counts in one statement share a database snapshot without joining rows.
        statement = select(
            select(func.count())
            .select_from(network_flows)
            .where(network_flows.c.ts_start >= query.start_time, network_flows.c.ts_start < query.end_time)
            .scalar_subquery()
            .label("flow_count"),
            select(func.count())
            .select_from(detections)
            .where(detections.c.created_at >= query.start_time, detections.c.created_at < query.end_time)
            .scalar_subquery()
            .label("detection_count"),
            select(func.count())
            .select_from(alerts)
            .where(alerts.c.created_at >= query.start_time, alerts.c.created_at < query.end_time)
            .scalar_subquery()
            .label("alert_count"),
        )
        result = await self._session.execute(statement)
        return DashboardSummaryResponse.model_validate(result.mappings().one())
