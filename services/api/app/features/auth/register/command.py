from dataclasses import dataclass, field

from app.abstraction.auth.enums import UserRole


@dataclass(frozen=True)
class RegisterCommand:
    username: str
    password: str = field(repr=False)
    role: UserRole = UserRole.USER
