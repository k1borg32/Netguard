from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.domain.user import User
from app.features.auth.exceptions import UserAlreadyExistsError
from app.infrastructure.persistence.tables import users
from app.infrastructure.security.contracts import PasswordHasher

from .command import RegisterCommand
from .response import RegisterResponse


class RegisterHandler:
    def __init__(self, session: AsyncSession, hasher: PasswordHasher) -> None:
        self._session = session
        self._hasher = hasher

    async def handle(self, command: RegisterCommand) -> RegisterResponse:
        if await self._session.scalar(select(users.c.user_id).where(users.c.username == command.username)):
            raise UserAlreadyExistsError()
        password_hash = await run_in_threadpool(self._hasher.hash, command.password)
        user = User(username=command.username, password_hash=password_hash, role=command.role)
        self._session.add(user)
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            # The unique constraint also covers simultaneous registrations.
            if getattr(exc.orig, "sqlstate", None) == "23505":
                raise UserAlreadyExistsError() from None
            raise
        return RegisterResponse.model_validate(user)
