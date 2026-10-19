from datetime import datetime

from pydantic import AwareDatetime, BaseModel, Field, ValidationInfo, field_validator


class DashboardSummaryRequest(BaseModel):
    start_time: AwareDatetime = Field(description="Inclusive start, with timezone (ISO 8601).")
    end_time: AwareDatetime = Field(description="Exclusive end, with timezone (ISO 8601).")

    @field_validator("end_time")
    @classmethod
    def validate_range(cls, end_time: datetime, info: ValidationInfo) -> datetime:
        start_time = info.data.get("start_time")
        if start_time is not None and end_time <= start_time:
            raise ValueError("end_time must be after start_time")
        return end_time
