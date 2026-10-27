from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GetConfigurationQuery:
    configuration_id: UUID
