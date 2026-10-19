"""AuthX adapter: extract and validate JWTs without referencing DI providers."""

from typing import Literal
from uuid import UUID

from authx import AuthX
from authx.exceptions import AuthXException
from fastapi import Request

from app.features.auth.exceptions import AuthenticationFailed


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
