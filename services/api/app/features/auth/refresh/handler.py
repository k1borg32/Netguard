from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.refresh_session import RefreshSession
from app.features.auth.exceptions import AuthenticationFailed
from app.infrastructure.persistence.tables import auth_refresh_sessions, users
from app.infrastructure.security.contracts import TokenIssuer

from .command import RefreshCommand
from .response import RefreshResponse


class RefreshHandler:
    def __init__(self, session: AsyncSession, tokens: TokenIssuer) -> None:
        self._session = session
        self._tokens = tokens

    async def handle(self, command: RefreshCommand) -> RefreshResponse:
        user_id = command.token.user_id
        if await self._session.scalar(select(users.c.user_id).where(users.c.user_id == user_id)) is None:
            raise AuthenticationFailed()
        pair = self._tokens.issue_pair(user_id)
        # DELETE locks the row; concurrent refreshes recheck it after the winner commits.
        consumed_user_id = await self._session.scalar(
            delete(auth_refresh_sessions)
            .where(
                auth_refresh_sessions.c.token_hash == RefreshSession.digest(command.token.raw_token),
                auth_refresh_sessions.c.user_id == user_id,
                auth_refresh_sessions.c.expires_at > func.clock_timestamp(),
            )
            .returning(auth_refresh_sessions.c.user_id)
        )
        if consumed_user_id is None:
            raise AuthenticationFailed()
        self._session.add(RefreshSession.from_token(user_id, pair.refresh_token, pair.refresh_expires_at))
        # Consuming the old session and saving the new one form a single transaction.
        await self._session.commit()
        return RefreshResponse(access_token=pair.access_token, refresh_token=pair.refresh_token)
