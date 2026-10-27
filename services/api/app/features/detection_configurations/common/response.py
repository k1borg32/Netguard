from uuid import UUID

from pydantic import BaseModel, ConfigDict, JsonValue


class DetectionConfigurationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    configuration_id: UUID
    detection_type: str
    method: str
    parameters: dict[str, JsonValue]
    active: bool
