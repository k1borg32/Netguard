from typing import Annotated

from fastapi import APIRouter, Depends

from .command import LoginCommand
from .dependencies import get_login_handler
from .handler import LoginHandler
from .request import LoginRequest
from .response import LoginResponse

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    handler: Annotated[LoginHandler, Depends(get_login_handler)],
) -> LoginResponse:
    return await handler.handle(LoginCommand(request.username, request.password))
