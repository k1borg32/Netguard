from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field, IPvAnyAddress, ValidationInfo, field_validator


class ListFlowsRequest(BaseModel):
    start_time: AwareDatetime | None = Field(default=None, description="Inclusive flow start time, with timezone.")
    end_time: AwareDatetime | None = Field(default=None, description="Exclusive flow start time, with timezone.")
    src_ip: IPvAnyAddress | None = None
    dst_ip: IPvAnyAddress | None = None
    src_port: int | None = Field(default=None, ge=0, le=65535)
    dst_port: int | None = Field(default=None, ge=0, le=65535)
    protocol: str | None = Field(default=None, min_length=1)
    sort_order: Literal["asc", "desc"] = Field(default="desc", description="Order by ts_start, then flow_id.")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=100)

    @field_validator("end_time")
    @classmethod
    def validate_range(cls, end_time: datetime | None, info: ValidationInfo) -> datetime | None:
        start_time = info.data.get("start_time")
        if start_time is not None and end_time is not None and end_time <= start_time:
            raise ValueError("end_time must be after start_time")
        return end_time
