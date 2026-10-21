from typing import Annotated

from fastapi import APIRouter, Depends

from app.features.auth.common.authentication import get_verified_refresh_token
from app.features.auth.common.dependencies import Tokens
from app.features.common.dependencies import Database
from app.infrastructure.security.models import VerifiedRefreshToken

from .command import RefreshCommand
from .handler import RefreshHandler
from .response import RefreshResponse

router = APIRouter()


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    token: Annotated[VerifiedRefreshToken, Depends(get_verified_refresh_token)],
    session: Database,
    tokens: Tokens,
) -> RefreshResponse:
    handler = RefreshHandler(session, tokens)
    return await handler.handle(RefreshCommand(token))
