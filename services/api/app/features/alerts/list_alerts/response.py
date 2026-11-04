from typing import Literal

from pydantic import BaseModel, Field, computed_field

from app.features.alerts.common.response import AlertResponse


class AlertListDetectionResponse(BaseModel):
    type: str
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    confidence: float | None
    src_ip: str | None
    dst_ip: str | None
    protocol: str | None


class AlertListItemResponse(AlertResponse):
    detection: AlertListDetectionResponse


class ListAlertsResponse(BaseModel):
    items: list[AlertListItemResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)

    @computed_field
    @property
    def total_pages(self) -> int:
        return (self.total + self.page_size - 1) // self.page_size

    @computed_field
    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @computed_field
    @property
    def has_previous(self) -> bool:
        return self.total > 0 and self.page > 1
