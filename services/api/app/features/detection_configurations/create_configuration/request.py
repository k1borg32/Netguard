from pydantic import BaseModel, ConfigDict

from app.features.detection_configurations.common.validation import ConfigurationIdentifier, ConfigurationParameters


class CreateConfigurationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    detection_type: ConfigurationIdentifier
    method: ConfigurationIdentifier
    parameters: ConfigurationParameters
