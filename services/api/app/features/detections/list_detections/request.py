from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field, IPvAnyAddress, ValidationInfo, field_validator


class ListDetectionsRequest(BaseModel):
    start_time: AwareDatetime | None = Field(
        default=None, description="Inclusive detection creation time, with timezone."
    )
    end_time: AwareDatetime | None = Field(
        default=None, description="Exclusive detection creation time, with timezone."
    )
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] | None = None
    detection_type: str | None = Field(default=None, min_length=1)
    method: str | None = Field(default=None, min_length=1)
    src_ip: IPvAnyAddress | None = None
    dst_ip: IPvAnyAddress | None = None
    protocol: str | None = Field(default=None, min_length=1)
    sort_order: Literal["asc", "desc"] = Field(default="desc", description="Order by created_at, then detection_id.")
    page: int = Field(default=1, ge=1)
    page_size: int | None = Field(default=None, ge=1, le=500, description="Items per page; defaults to 50.")
    limit: int | None = Field(default=None, ge=1, le=500, deprecated=True, description="Legacy alias for page_size.")

    @field_validator("end_time")
    @classmethod
    def validate_range(cls, end_time: datetime | None, info: ValidationInfo) -> datetime | None:
        start_time = info.data.get("start_time")
        if start_time is not None and end_time is not None and end_time <= start_time:
            raise ValueError("end_time must be after start_time")
        return end_time

    @field_validator("limit")
    @classmethod
    def validate_page_size_alias(cls, limit: int | None, info: ValidationInfo) -> int | None:
        page_size = info.data.get("page_size")
        if page_size is not None and limit is not None and page_size != limit:
            raise ValueError("limit and page_size must match when both are provided")
        return limit

    @property
    def effective_page_size(self) -> int:
        return self.page_size or self.limit or 50
