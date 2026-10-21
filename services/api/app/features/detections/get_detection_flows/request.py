from typing import Literal

from pydantic import BaseModel, Field


class GetDetectionFlowsRequest(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=500)
    sort_order: Literal["asc", "desc"] = Field(default="desc", description="Order by ts_start, then flow_id.")
