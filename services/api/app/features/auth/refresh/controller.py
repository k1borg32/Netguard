from typing import Annotated

from fastapi import APIRouter, Depends

from app.features.auth.common.authentication import get_verified_refresh_token
from app.infrastructure.security.models import VerifiedRefreshToken

from .command import RefreshCommand
from .dependencies import get_refresh_handler
from .handler import RefreshHandler
from .response import RefreshResponse

router = APIRouter()


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    token: Annotated[VerifiedRefreshToken, Depends(get_verified_refresh_token)],
    handler: Annotated[RefreshHandler, Depends(get_refresh_handler)],
) -> RefreshResponse:
    return await handler.handle(RefreshCommand(token))
