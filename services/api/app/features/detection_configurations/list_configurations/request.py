from typing import Literal

from pydantic import BaseModel, Field

from app.features.detection_configurations.common.validation import ConfigurationIdentifier


class ListConfigurationsRequest(BaseModel):
    detection_type: ConfigurationIdentifier | None = None
    method: ConfigurationIdentifier | None = None
    active: bool | None = None
    sort_order: Literal["asc", "desc"] = "asc"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=100)
