from datetime import UTC, datetime, timedelta
from typing import Self

from pydantic import AwareDatetime, BaseModel, Field, field_validator, model_validator

MAX_RANGE = timedelta(days=366)
MAX_BUCKETS = 500
BUCKET_ORIGIN = datetime(1970, 1, 1, tzinfo=UTC)


class DashboardTimeseriesRequest(BaseModel):
    start_time: AwareDatetime | None = Field(
        default=None,
        description="Inclusive start (ISO 8601 with timezone); defaults to end_time minus 24 hours.",
    )
    end_time: AwareDatetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Exclusive end (ISO 8601 with timezone); defaults to now in UTC.",
    )
    interval_s: int = Field(default=3600, ge=1, le=86400, description="UTC bucket size in whole seconds (1-86400).")

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def validate_iso_timestamp(cls, value: object) -> object:
        # AwareDatetime also accepts Unix timestamps; the HTTP contract requires ISO 8601.
        if isinstance(value, str):
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        try:
            self.end_time = self.end_time.astimezone(UTC)
            self.start_time = (
                self.start_time.astimezone(UTC) if self.start_time is not None else self.end_time - timedelta(days=1)
            )
        except (OverflowError, ValueError) as exc:
            raise ValueError("Time range cannot be represented in UTC") from exc
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        if self.end_time - self.start_time > MAX_RANGE:
            raise ValueError("Time range must not exceed 366 days")

        step = timedelta(seconds=self.interval_s)
        first_bucket = self.start_time - (self.start_time - BUCKET_ORIGIN) % step
        complete_buckets, remainder = divmod(self.end_time - first_bucket, step)
        if complete_buckets + bool(remainder) > MAX_BUCKETS:
            raise ValueError("Time range must not exceed 500 buckets; select a larger interval_s")
        return self
