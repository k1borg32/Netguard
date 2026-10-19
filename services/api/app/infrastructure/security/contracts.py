"""Security service contracts; handlers use persistence directly."""

from typing import Protocol
from uuid import UUID

from .models import TokenPair


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...
    def verify(self, password: str, password_hash: str) -> bool: ...


class TokenIssuer(Protocol):
    def issue_pair(self, user_id: UUID) -> TokenPair: ...
