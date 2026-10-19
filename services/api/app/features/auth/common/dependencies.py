"""Shared security providers; each slice composes its own handler."""

from functools import lru_cache
from secrets import token_urlsafe
from typing import Annotated

from authx import AuthX
from fastapi import Depends

from app.infrastructure.security.authx_config import create_auth
from app.infrastructure.security.contracts import PasswordHasher, TokenIssuer
from app.infrastructure.security.password_hasher import Argon2PasswordHasher
from app.infrastructure.security.token_issuer import AuthXTokenIssuer


@lru_cache
def get_auth() -> AuthX:
    return create_auth()


@lru_cache
def get_password_hasher() -> PasswordHasher:
    return Argon2PasswordHasher()


def get_token_provider(auth: Annotated[AuthX, Depends(get_auth)]) -> TokenIssuer:
    return AuthXTokenIssuer(auth)


@lru_cache
def get_dummy_password_hash(hasher: Annotated[PasswordHasher, Depends(get_password_hasher)]) -> str:
    return hasher.hash(token_urlsafe(32))


Hasher = Annotated[PasswordHasher, Depends(get_password_hasher)]
Tokens = Annotated[TokenIssuer, Depends(get_token_provider)]
