from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GetCurrentUserQuery:
    user_id: UUID
