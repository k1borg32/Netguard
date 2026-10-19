from dataclasses import dataclass, field

from app.domain.user_role import UserRole


@dataclass(frozen=True)
class RegisterCommand:
    username: str
    password: str = field(repr=False)
    role: UserRole = UserRole.USER
