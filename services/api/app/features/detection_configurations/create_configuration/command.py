from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CreateConfigurationCommand:
    detection_type: str
    method: str
    parameters: dict[str, Any]
