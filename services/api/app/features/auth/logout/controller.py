from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.features.auth.common.authentication import get_verified_refresh_token
from app.infrastructure.security.models import VerifiedRefreshToken

from .command import LogoutCommand
from .dependencies import get_logout_handler
from .handler import LogoutHandler

router = APIRouter()


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    token: Annotated[VerifiedRefreshToken, Depends(get_verified_refresh_token)],
    handler: Annotated[LogoutHandler, Depends(get_logout_handler)],
) -> Response:
    await handler.handle(LogoutCommand(token))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
