"""Compose authentication handlers from application protocols."""

from typing import Annotated

from fastapi import Depends

from app.features.auth.login.handler import LoginHandler
from app.features.auth.logout.handler import LogoutHandler
from app.features.auth.me.handler import GetCurrentUserHandler
from app.features.auth.refresh.handler import RefreshHandler
from app.features.auth.register.handler import RegisterHandler

from .database import Repository
from .security import Hasher, Tokens, get_dummy_password_hash


def get_register_handler(repository: Repository, hasher: Hasher) -> RegisterHandler:
    return RegisterHandler(repository, hasher)


def get_login_handler(
    repository: Repository,
    hasher: Hasher,
    tokens: Tokens,
    dummy_password_hash: Annotated[str, Depends(get_dummy_password_hash)],
) -> LoginHandler:
    return LoginHandler(repository, hasher, tokens, dummy_password_hash)


def get_refresh_handler(repository: Repository, tokens: Tokens) -> RefreshHandler:
    return RefreshHandler(repository, tokens)


def get_logout_handler(repository: Repository) -> LogoutHandler:
    return LogoutHandler(repository)


def get_current_user_handler(repository: Repository) -> GetCurrentUserHandler:
    return GetCurrentUserHandler(repository)
