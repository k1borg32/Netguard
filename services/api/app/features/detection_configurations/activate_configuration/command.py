from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ActivateConfigurationCommand:
    configuration_id: UUID
