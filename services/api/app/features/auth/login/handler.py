from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.domain.refresh_session import RefreshSession
from app.features.auth.exceptions import AuthenticationFailed
from app.infrastructure.persistence.tables import users
from app.infrastructure.security.contracts import PasswordHasher, TokenIssuer

from .command import LoginCommand
from .response import LoginResponse


class LoginHandler:
    def __init__(
        self, session: AsyncSession, hasher: PasswordHasher, tokens: TokenIssuer, dummy_password_hash: str
    ) -> None:
        self._session = session
        self._hasher = hasher
        self._tokens = tokens
        self._dummy_password_hash = dummy_password_hash

    async def handle(self, command: LoginCommand) -> LoginResponse:
        result = await self._session.execute(
            select(users.c.user_id, users.c.password_hash).where(users.c.username == command.username)
        )
        user = result.one_or_none()
        valid = await run_in_threadpool(
            self._hasher.verify,
            command.password,
            user.password_hash if user else self._dummy_password_hash,
        )
        if user is None or not valid:
            raise AuthenticationFailed()
        pair = self._tokens.issue_pair(user.user_id)
        self._session.add(RefreshSession.from_token(user.user_id, pair.refresh_token, pair.refresh_expires_at))
        await self._session.commit()
        return LoginResponse(access_token=pair.access_token, refresh_token=pair.refresh_token)
