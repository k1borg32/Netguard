from fastapi import APIRouter

from .get_flow.controller import router as get_flow_router
from .list_flows.controller import router as list_flows_router

PREFIX = "/api/v1/flows"

router = APIRouter(tags=["flows"])
router.include_router(list_flows_router, prefix=PREFIX)
router.include_router(get_flow_router, prefix=PREFIX)
