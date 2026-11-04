from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class UpdateConfigurationCommand:
    configuration_id: UUID
    changes: dict[str, Any]
