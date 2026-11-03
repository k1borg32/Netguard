from typing import Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.features.detection_configurations.common.validation import ConfigurationIdentifier, ConfigurationParameters


class UpdateConfigurationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    detection_type: ConfigurationIdentifier | None = None
    method: ConfigurationIdentifier | None = None
    parameters: ConfigurationParameters | None = None

    @field_validator("detection_type", "method", "parameters")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError("Explicit null is not allowed; omit the field to leave it unchanged")
        return value

    @model_validator(mode="after")
    def require_changes(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Provide at least one of detection_type, method or parameters")
        return self
