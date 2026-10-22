from sqlalchemy import func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.flows.common.response import FlowResponse
from app.infrastructure.persistence.tables import network_flows

from .query import ListFlowsQuery
from .response import ListFlowsResponse


class ListFlowsHandler:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def handle(self, query: ListFlowsQuery) -> ListFlowsResponse:
        statement = select(network_flows)
        if query.start_time is not None:
            statement = statement.where(network_flows.c.ts_start >= query.start_time)
        if query.end_time is not None:
            statement = statement.where(network_flows.c.ts_start < query.end_time)
        for column, value in (
            (network_flows.c.src_ip, query.src_ip),
            (network_flows.c.dst_ip, query.dst_ip),
            (network_flows.c.src_port, query.src_port),
            (network_flows.c.dst_port, query.dst_port),
            (network_flows.c.protocol, query.protocol),
        ):
            if value is not None:
                statement = statement.where(column == value)

        filtered = statement.cte("filtered_flows")
        descending = query.sort_order == "desc"
        order = [column.desc() if descending else column.asc() for column in (filtered.c.ts_start, filtered.c.flow_id)]
        page = (
            select(filtered)
            .order_by(*order)
            .limit(query.page_size)
            .offset((query.page - 1) * query.page_size)
            .cte("flow_page")
        )
        total = select(func.count().label("total")).select_from(filtered).cte("flow_total")
        # One snapshot for items and total; retain the count even when the requested page is empty.
        result = await self._session.execute(
            select(page, total.c.total)
            .select_from(total.outerjoin(page, true()))
            .order_by(*[column.desc() if descending else column.asc() for column in (page.c.ts_start, page.c.flow_id)])
        )
        rows = result.mappings().all()
        return ListFlowsResponse(
            items=[FlowResponse.model_validate(row) for row in rows if row["flow_id"] is not None],
            total=rows[0]["total"],
            page=query.page,
            page_size=query.page_size,
        )
