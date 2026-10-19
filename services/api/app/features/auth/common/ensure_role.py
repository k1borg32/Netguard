from app.abstraction.auth import AuthUser
from app.abstraction.auth.enums import UserRole
from app.features.auth.exceptions import ForbiddenError


def ensure_role(
    user: AuthUser,
    allowed_roles: set[UserRole],
) -> None:
    if user.role not in allowed_roles:
        raise ForbiddenError()
