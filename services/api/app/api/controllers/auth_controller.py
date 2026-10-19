from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.abstraction.auth.models import VerifiedRefreshToken
from app.di import (
    get_authenticated_user_id,
    get_current_user_handler,
    get_login_handler,
    get_logout_handler,
    get_refresh_handler,
    get_register_handler,
    get_verified_refresh_token,
)
from app.features.auth.login.command import LoginCommand
from app.features.auth.login.handler import LoginHandler
from app.features.auth.login.request import LoginRequest
from app.features.auth.login.response import LoginResponse
from app.features.auth.logout.command import LogoutCommand
from app.features.auth.logout.handler import LogoutHandler
from app.features.auth.me.handler import GetCurrentUserHandler
from app.features.auth.me.query import GetCurrentUserQuery
from app.features.auth.me.response import CurrentUserResponse
from app.features.auth.refresh.command import RefreshCommand
from app.features.auth.refresh.handler import RefreshHandler
from app.features.auth.refresh.response import RefreshResponse
from app.features.auth.register.command import RegisterCommand
from app.features.auth.register.handler import RegisterHandler
from app.features.auth.register.request import RegisterRequest
from app.features.auth.register.response import RegisterResponse

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(
    request: RegisterRequest,
    handler: Annotated[RegisterHandler, Depends(get_register_handler)],
) -> RegisterResponse:
    user = handler.handle(RegisterCommand(request.username, request.password, request.role))
    return RegisterResponse.model_validate(user)


@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest, handler: Annotated[LoginHandler, Depends(get_login_handler)]) -> LoginResponse:
    pair = handler.handle(LoginCommand(request.username, request.password))
    return LoginResponse(access_token=pair.access_token, refresh_token=pair.refresh_token)


@router.post("/refresh", response_model=RefreshResponse)
def refresh(
    token: Annotated[VerifiedRefreshToken, Depends(get_verified_refresh_token)],
    handler: Annotated[RefreshHandler, Depends(get_refresh_handler)],
) -> RefreshResponse:
    pair = handler.handle(RefreshCommand(token))
    return RefreshResponse(access_token=pair.access_token, refresh_token=pair.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    token: Annotated[VerifiedRefreshToken, Depends(get_verified_refresh_token)],
    handler: Annotated[LogoutHandler, Depends(get_logout_handler)],
) -> Response:
    handler.handle(LogoutCommand(token))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=CurrentUserResponse)
def me(
    user_id: Annotated[UUID, Depends(get_authenticated_user_id)],
    handler: Annotated[GetCurrentUserHandler, Depends(get_current_user_handler)],
) -> CurrentUserResponse:
    return CurrentUserResponse.model_validate(handler.handle(GetCurrentUserQuery(user_id)))
