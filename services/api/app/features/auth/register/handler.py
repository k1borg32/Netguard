from app.abstraction.auth.models import AuthUser
from app.abstraction.auth.ports import AuthRepository, PasswordHasher
from app.features.auth.exceptions import UserAlreadyExistsError

from .command import RegisterCommand


class RegisterHandler:
    def __init__(self, repository: AuthRepository, hasher: PasswordHasher) -> None:
        self._repository = repository
        self._hasher = hasher

    def handle(self, command: RegisterCommand) -> AuthUser:
        if self._repository.find_by_username(command.username) is not None:
            raise UserAlreadyExistsError()
        return self._repository.create_user(command.username, self._hasher.hash(command.password), command.role)
