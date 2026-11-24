from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.tables import alerts, detections, network_flows

from .query import GetDashboardSummaryQuery
from .response import DashboardSummaryResponse


class GetDashboardSummaryHandler:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def handle(self, query: GetDashboardSummaryQuery) -> DashboardSummaryResponse:
        detections_in_range = (
            select(detections.c.type, detections.c.severity)
            .where(detections.c.created_at >= query.start_time, detections.c.created_at < query.end_time)
            .cte("detections_in_range")
        )
        counts_by_type = (
            select(detections_in_range.c.type, func.count().label("count"))
            .group_by(detections_in_range.c.type)
            .subquery()
        )
        counts_by_severity = (
            select(detections_in_range.c.severity, func.count().label("count"))
            .group_by(detections_in_range.c.severity)
            .subquery()
        )
        # Independent counts in one statement share a database snapshot without joining rows.
        statement = select(
            select(func.count())
            .select_from(network_flows)
            .where(network_flows.c.ts_start >= query.start_time, network_flows.c.ts_start < query.end_time)
            .scalar_subquery()
            .label("flow_count"),
            select(func.count()).select_from(detections_in_range).scalar_subquery().label("detection_count"),
            select(func.count())
            .select_from(alerts)
            .where(alerts.c.created_at >= query.start_time, alerts.c.created_at < query.end_time)
            .scalar_subquery()
            .label("alert_count"),
            select(func.jsonb_object_agg(counts_by_type.c.type, counts_by_type.c.count))
            .scalar_subquery()
            .label("detections_by_type"),
            select(func.jsonb_object_agg(counts_by_severity.c.severity, counts_by_severity.c.count))
            .scalar_subquery()
            .label("detections_by_severity"),
        )
        result = await self._session.execute(statement)
        summary = dict(result.mappings().one())
        if summary["detections_by_type"] is None:
            summary["detections_by_type"] = {}
        severity_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
        if summary["detections_by_severity"] is not None:
            severity_counts.update(summary["detections_by_severity"])
        summary["detections_by_severity"] = severity_counts
        return DashboardSummaryResponse.model_validate(summary)
