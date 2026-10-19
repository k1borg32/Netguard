from typing import Annotated

from fastapi import APIRouter, Depends

from app.features.auth.common.dependencies import Hasher, Tokens, get_dummy_password_hash
from app.features.common.dependencies import Database

from .command import LoginCommand
from .handler import LoginHandler
from .request import LoginRequest
from .response import LoginResponse

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    session: Database,
    hasher: Hasher,
    tokens: Tokens,
    dummy_password_hash: Annotated[str, Depends(get_dummy_password_hash)],
) -> LoginResponse:
    handler = LoginHandler(session, hasher, tokens, dummy_password_hash)
    return await handler.handle(LoginCommand(request.username, request.password))
