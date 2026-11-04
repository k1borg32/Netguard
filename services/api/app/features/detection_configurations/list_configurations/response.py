from pydantic import BaseModel, Field, computed_field

from app.features.detection_configurations.common.response import DetectionConfigurationResponse


class ListConfigurationsResponse(BaseModel):
    items: list[DetectionConfigurationResponse]
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
