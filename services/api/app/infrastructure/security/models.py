from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class TokenPair:
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    refresh_expires_at: datetime


@dataclass(frozen=True)
class VerifiedRefreshToken:
    user_id: UUID
    raw_token: str = field(repr=False)
