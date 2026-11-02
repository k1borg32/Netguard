from sqlalchemy import func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.tables import alerts, detections

from .query import ListAlertsQuery
from .response import AlertListItemResponse, ListAlertsResponse


class ListAlertsHandler:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def handle(self, query: ListAlertsQuery) -> ListAlertsResponse:
        statement = select(
            alerts,
            detections.c.type.label("detection_type"),
            detections.c.severity.label("detection_severity"),
            detections.c.confidence.label("detection_confidence"),
            detections.c.src_ip.label("detection_src_ip"),
            detections.c.dst_ip.label("detection_dst_ip"),
            detections.c.protocol.label("detection_protocol"),
        ).select_from(alerts.join(detections))
        if query.start_time is not None:
            statement = statement.where(alerts.c.created_at >= query.start_time)
        if query.end_time is not None:
            statement = statement.where(alerts.c.created_at < query.end_time)
        for column, value in (
            (alerts.c.status, query.status),
            (detections.c.severity, query.severity),
            (detections.c.type, query.detection_type),
            (detections.c.src_ip, query.src_ip),
            (detections.c.dst_ip, query.dst_ip),
            (detections.c.protocol, query.protocol),
        ):
            if value is not None:
                statement = statement.where(column == value)

        filtered = statement.cte("filtered_alerts")
        descending = query.sort_order == "desc"
        order = [
            column.desc() if descending else column.asc() for column in (filtered.c.created_at, filtered.c.alert_id)
        ]
        page = (
            select(filtered)
            .order_by(*order)
            .limit(query.page_size)
            .offset((query.page - 1) * query.page_size)
            .cte("alert_page")
        )
        total = select(func.count().label("total")).select_from(filtered).cte("alert_total")
        # One snapshot for items and total; the outer join retains total on empty pages.
        result = await self._session.execute(
            select(page, total.c.total)
            .select_from(total.outerjoin(page, true()))
            .order_by(
                *[column.desc() if descending else column.asc() for column in (page.c.created_at, page.c.alert_id)]
            )
        )
        rows = result.mappings().all()
        return ListAlertsResponse(
            items=[
                AlertListItemResponse.model_validate(
                    {
                        "alert_id": row["alert_id"],
                        "detection_id": row["detection_id"],
                        "status": row["status"],
                        "created_at": row["created_at"],
                        "acknowledged_at": row["acknowledged_at"],
                        "detection": {
                            "type": row["detection_type"],
                            "severity": row["detection_severity"],
                            "confidence": row["detection_confidence"],
                            "src_ip": row["detection_src_ip"],
                            "dst_ip": row["detection_dst_ip"],
                            "protocol": row["detection_protocol"],
                        },
                    }
                )
                for row in rows
                if row["alert_id"] is not None
            ],
            total=rows[0]["total"],
            page=query.page,
            page_size=query.page_size,
        )
