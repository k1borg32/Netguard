"""Compose HTTP authentication and authorization dependencies."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from authx import AuthX
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.abstraction.auth.enums import UserRole
from app.abstraction.auth.models import AuthUser, VerifiedRefreshToken
from app.features.auth.common.ensure_role import ensure_role
from app.features.auth.me.handler import GetCurrentUserHandler
from app.features.auth.me.query import GetCurrentUserQuery
from app.infrastructure.security.authentication import verify_request_token

from .auth import get_current_user_handler
from .security import get_auth

bearer = HTTPBearer(auto_error=False)


async def get_authenticated_user_id(
    request: Request,
    auth: Annotated[AuthX, Depends(get_auth)],
    _credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> UUID:
    user_id, _ = await verify_request_token(request, "access", auth)
    return user_id


async def get_verified_refresh_token(
    request: Request,
    auth: Annotated[AuthX, Depends(get_auth)],
    _credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> VerifiedRefreshToken:
    user_id, raw_token = await verify_request_token(request, "refresh", auth)
    return VerifiedRefreshToken(user_id, raw_token)


def require_roles(*roles: UserRole) -> Callable[..., AuthUser]:
    def dependency(
        user_id: Annotated[UUID, Depends(get_authenticated_user_id)],
        handler: Annotated[GetCurrentUserHandler, Depends(get_current_user_handler)],
    ) -> AuthUser:
        user = handler.handle(GetCurrentUserQuery(user_id))
        ensure_role(user, set(roles))
        return user

    return dependency
