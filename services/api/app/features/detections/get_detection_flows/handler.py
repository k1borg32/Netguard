from sqlalchemy import any_, func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.detections.exceptions import DetectionNotFoundError
from app.infrastructure.persistence.tables import detections, network_flows

from .query import GetDetectionFlowsQuery
from .response import DetectionFlowResponse, GetDetectionFlowsResponse


class GetDetectionFlowsHandler:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def handle(self, query: GetDetectionFlowsQuery) -> GetDetectionFlowsResponse:
        selected_detection = (
            select(detections.c.detection_id, detections.c.trace_ids)
            .where(detections.c.detection_id == query.detection_id)
            .cte("selected_detection")
        )
        # ANY keeps each flow once even if a trace ID occurs repeatedly in the sample.
        matched_flows = (
            select(network_flows)
            .select_from(
                network_flows.join(selected_detection, network_flows.c.trace_id == any_(selected_detection.c.trace_ids))
            )
            .cte("detection_flows")
        )
        descending = query.sort_order == "desc"
        order = [
            column.desc() if descending else column.asc()
            for column in (matched_flows.c.ts_start, matched_flows.c.flow_id)
        ]
        page = (
            select(matched_flows)
            .order_by(*order)
            .limit(query.page_size)
            .offset((query.page - 1) * query.page_size)
            .cte("flow_page")
        )
        total = select(func.count().label("total")).select_from(matched_flows).cte("flow_total")
        # Keep the parent in the final FROM: no rows means a missing detection,
        # while an existing parent retains total even when the requested page is empty.
        result = await self._session.execute(
            select(page, total.c.total)
            .select_from(selected_detection.join(total, true()).outerjoin(page, true()))
            .order_by(*[column.desc() if descending else column.asc() for column in (page.c.ts_start, page.c.flow_id)])
        )
        rows = result.mappings().all()
        if not rows:
            raise DetectionNotFoundError()
        return GetDetectionFlowsResponse(
            items=[DetectionFlowResponse.model_validate(row) for row in rows if row["flow_id"] is not None],
            total=rows[0]["total"],
            page=query.page,
            page_size=query.page_size,
        )
