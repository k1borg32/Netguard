"""Public dependency providers. Import these same callables when overriding dependencies in tests."""

from .auth import (
    get_current_user_handler,
    get_login_handler,
    get_logout_handler,
    get_refresh_handler,
    get_register_handler,
)
from .authentication import get_authenticated_user_id, get_verified_refresh_token, require_roles
from .database import get_auth_repository, get_db_connection
from .security import get_auth, get_password_hasher, get_token_provider

__all__ = [
    "get_auth",
    "get_authenticated_user_id",
    "get_verified_refresh_token",
    "require_roles",
    "get_auth_repository",
    "get_db_connection",
    "get_password_hasher",
    "get_token_provider",
    "get_register_handler",
    "get_login_handler",
    "get_refresh_handler",
    "get_logout_handler",
    "get_current_user_handler",
]
