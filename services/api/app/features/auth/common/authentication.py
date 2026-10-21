"""HTTP authentication and role checks shared by auth slices."""

from collections.abc import Callable
from typing import Annotated, Literal
from uuid import UUID

from authx import AuthX
from authx.exceptions import AuthXException
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app.domain.user_role import UserRole
from app.features.auth.exceptions import AuthenticationFailed, ForbiddenError
from app.features.common.dependencies import Database
from app.infrastructure.persistence.tables import users
from app.infrastructure.security.models import VerifiedRefreshToken

from .dependencies import get_auth

bearer = HTTPBearer(auto_error=False)


async def verify_request_token(
    request: Request, token_type: Literal["access", "refresh"], auth: AuthX
) -> tuple[UUID, str]:
    try:
        token = await auth.get_token_from_request(request, type=token_type, optional=False, locations=["headers"])
        if token is None:
            raise AuthenticationFailed()
        payload = auth.verify_token(token)
        return UUID(payload.sub), token.token
    except (AuthXException, ValueError, TypeError):
        raise AuthenticationFailed() from None


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


def require_roles(*roles: UserRole) -> Callable[..., object]:
    async def dependency(
        user_id: Annotated[UUID, Depends(get_authenticated_user_id)],
        session: Database,
    ) -> None:
        role = await session.scalar(select(users.c.role).where(users.c.user_id == user_id))
        if role is None:
            raise AuthenticationFailed()
        if role not in roles:
            raise ForbiddenError()

    return dependency
