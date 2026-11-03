from sqlalchemy import func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.tables import detections

from .query import ListDetectionsQuery
from .response import DetectionResponse, ListDetectionsResponse


class ListDetectionsHandler:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def handle(self, query: ListDetectionsQuery) -> ListDetectionsResponse:
        statement = select(detections)
        if query.start_time is not None:
            statement = statement.where(detections.c.created_at >= query.start_time)
        if query.end_time is not None:
            statement = statement.where(detections.c.created_at < query.end_time)
        for column, value in (
            (detections.c.severity, query.severity),
            (detections.c.type, query.detection_type),
            (detections.c.method, query.method),
            (detections.c.src_ip, query.src_ip),
            (detections.c.dst_ip, query.dst_ip),
            (detections.c.protocol, query.protocol),
        ):
            if value is not None:
                statement = statement.where(column == value)

        filtered = statement.cte("filtered_detections")
        descending = query.sort_order == "desc"
        order = [
            column.desc() if descending else column.asc() for column in (filtered.c.created_at, filtered.c.detection_id)
        ]
        page = (
            select(filtered)
            .order_by(*order)
            .limit(query.page_size)
            .offset((query.page - 1) * query.page_size)
            .cte("detection_page")
        )
        total = select(func.count().label("total")).select_from(filtered).cte("detection_total")
        # One snapshot for items and total; the outer join retains total on empty pages.
        result = await self._session.execute(
            select(page, total.c.total)
            .select_from(total.outerjoin(page, true()))
            .order_by(
                *[column.desc() if descending else column.asc() for column in (page.c.created_at, page.c.detection_id)]
            )
        )
        rows = result.mappings().all()
        return ListDetectionsResponse(
            items=[DetectionResponse.model_validate(row) for row in rows if row["detection_id"] is not None],
            total=rows[0]["total"],
            page=query.page,
            page_size=query.page_size,
        )
