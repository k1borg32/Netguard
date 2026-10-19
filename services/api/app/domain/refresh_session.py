from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
from uuid import UUID


@dataclass(eq=False, kw_only=True)
class RefreshSession:
    user_id: UUID
    token_hash: str = field(repr=False)
    expires_at: datetime

    @staticmethod
    def digest(raw_token: str) -> str:
        return sha256(raw_token.encode("utf-8")).hexdigest()

    @classmethod
    def from_token(cls, user_id: UUID, raw_token: str, expires_at: datetime) -> "RefreshSession":
        return cls(user_id=user_id, token_hash=cls.digest(raw_token), expires_at=expires_at)
