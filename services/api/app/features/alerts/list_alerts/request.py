from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field, IPvAnyAddress, ValidationInfo, field_validator


class ListAlertsRequest(BaseModel):
    start_time: AwareDatetime | None = Field(default=None, description="Inclusive alert creation time, with timezone.")
    end_time: AwareDatetime | None = Field(default=None, description="Exclusive alert creation time, with timezone.")
    status: Literal["NEW", "ACKNOWLEDGED"] | None = None
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] | None = None
    detection_type: str | None = Field(default=None, min_length=1)
    src_ip: IPvAnyAddress | None = None
    dst_ip: IPvAnyAddress | None = None
    protocol: str | None = Field(default=None, min_length=1)
    sort_order: Literal["asc", "desc"] = Field(default="desc", description="Order by created_at, then alert_id.")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=100)

    @field_validator("end_time")
    @classmethod
    def validate_range(cls, end_time: datetime | None, info: ValidationInfo) -> datetime | None:
        start_time = info.data.get("start_time")
        if start_time is not None and end_time is not None and end_time <= start_time:
            raise ValueError("end_time must be after start_time")
        return end_time
