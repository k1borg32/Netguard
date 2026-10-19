from sqlalchemy import delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.refresh_session import RefreshSession
from app.features.auth.exceptions import AuthenticationFailed
from app.infrastructure.persistence.tables import auth_refresh_sessions

from .command import LogoutCommand


class LogoutHandler:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def handle(self, command: LogoutCommand) -> None:
        user_id = await self._session.scalar(
            delete(auth_refresh_sessions)
            .where(
                auth_refresh_sessions.c.token_hash == RefreshSession.digest(command.token.raw_token),
                auth_refresh_sessions.c.user_id == command.token.user_id,
                auth_refresh_sessions.c.expires_at > func.clock_timestamp(),
            )
            .returning(auth_refresh_sessions.c.user_id)
        )
        if user_id is None:
            raise AuthenticationFailed()
        await self._session.commit()
