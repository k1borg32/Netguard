from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from .enums import UserRole


@dataclass(frozen=True)
class AuthUser:
    user_id: UUID
    username: str
    password_hash: str = field(repr=False)
    role: UserRole


@dataclass(frozen=True)
class TokenPair:
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    refresh_expires_at: datetime


@dataclass(frozen=True)
class VerifiedRefreshToken:
    user_id: UUID
    raw_token: str = field(repr=False)
