from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.features.auth.common.authentication import get_verified_refresh_token
from app.features.common.dependencies import Database
from app.infrastructure.security.models import VerifiedRefreshToken

from .command import LogoutCommand
from .handler import LogoutHandler

router = APIRouter()


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    token: Annotated[VerifiedRefreshToken, Depends(get_verified_refresh_token)],
    session: Database,
) -> Response:
    handler = LogoutHandler(session)
    await handler.handle(LogoutCommand(token))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
