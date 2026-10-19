from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.exceptions import AuthenticationFailed
from app.infrastructure.persistence.tables import users

from .query import GetCurrentUserQuery
from .response import CurrentUserResponse


class GetCurrentUserHandler:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def handle(self, query: GetCurrentUserQuery) -> CurrentUserResponse:
        result = await self._session.execute(
            select(users.c.user_id, users.c.username, users.c.role).where(users.c.user_id == query.user_id)
        )
        user = result.mappings().one_or_none()
        if user is None:
            raise AuthenticationFailed()
        return CurrentUserResponse.model_validate(user)
