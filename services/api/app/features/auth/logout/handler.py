from app.abstraction.auth.ports import AuthRepository
from app.features.auth.exceptions import AuthenticationFailed

from .command import LogoutCommand


class LogoutHandler:
    def __init__(self, repository: AuthRepository) -> None:
        self._repository = repository

    def handle(self, command: LogoutCommand) -> None:
        if not self._repository.revoke_refresh_token(command.token.user_id, command.token.raw_token):
            raise AuthenticationFailed()
