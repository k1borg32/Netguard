from sqlalchemy import func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.detection_configurations.common.response import DetectionConfigurationResponse
from app.infrastructure.persistence.tables import detection_configs

from .query import ListConfigurationsQuery
from .response import ListConfigurationsResponse


class ListConfigurationsHandler:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def handle(self, query: ListConfigurationsQuery) -> ListConfigurationsResponse:
        statement = select(detection_configs)
        for column, value in (
            (detection_configs.c.detection_type, query.detection_type),
            (detection_configs.c.method, query.method),
            (detection_configs.c.active, query.active),
        ):
            if value is not None:
                statement = statement.where(column == value)

        filtered = statement.cte("filtered_configurations")
        descending = query.sort_order == "desc"
        page = (
            select(filtered)
            .order_by(filtered.c.configuration_id.desc() if descending else filtered.c.configuration_id.asc())
            .limit(query.page_size)
            .offset((query.page - 1) * query.page_size)
            .cte("configuration_page")
        )
        total = select(func.count().label("total")).select_from(filtered).cte("configuration_total")
        # A single statement keeps items and total consistent, including empty pages.
        result = await self._session.execute(
            select(page, total.c.total)
            .select_from(total.outerjoin(page, true()))
            .order_by(page.c.configuration_id.desc() if descending else page.c.configuration_id.asc())
        )
        rows = result.mappings().all()
        return ListConfigurationsResponse(
            items=[
                DetectionConfigurationResponse.model_validate(row)
                for row in rows
                if row["configuration_id"] is not None
            ],
            total=rows[0]["total"],
            page=query.page,
            page_size=query.page_size,
        )
