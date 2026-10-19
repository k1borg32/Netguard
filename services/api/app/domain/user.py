"""User identity, independent of HTTP and persistence."""

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from .user_role import UserRole


@dataclass(eq=False, kw_only=True)
class User:
    username: str
    password_hash: str = field(repr=False)
    role: UserRole = UserRole.USER
    user_id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not 1 <= len(self.username) <= 128 or any(char.isspace() for char in self.username):
            raise ValueError("Username must contain 1–128 characters without whitespace")
        if not self.password_hash:
            raise ValueError("Password hash is required")
        self.role = UserRole(self.role)
