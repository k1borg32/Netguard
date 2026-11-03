from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.network_flow import NetworkFlow
from app.features.flows.common.response import FlowResponse
from app.features.flows.exceptions import FlowNotFoundError

from .query import GetFlowQuery


class GetFlowHandler:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def handle(self, query: GetFlowQuery) -> FlowResponse:
        flow = await self._session.get(NetworkFlow, (query.flow_id, query.ts_start))
        if flow is None:
            raise FlowNotFoundError()
        return FlowResponse.model_validate(flow)
