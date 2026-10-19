from typing import Annotated

from fastapi import Depends

from app.features.auth.common.dependencies import Hasher, Tokens, get_dummy_password_hash
from app.features.common.dependencies import Database

from .handler import LoginHandler


def get_login_handler(
    session: Database,
    hasher: Hasher,
    tokens: Tokens,
    dummy_password_hash: Annotated[str, Depends(get_dummy_password_hash)],
) -> LoginHandler:
    return LoginHandler(session, hasher, tokens, dummy_password_hash)
