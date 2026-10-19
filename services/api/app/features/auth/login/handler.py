from app.abstraction.auth.models import TokenPair
from app.abstraction.auth.ports import AuthRepository, PasswordHasher, TokenIssuer
from app.features.auth.exceptions import AuthenticationFailed

from .command import LoginCommand


class LoginHandler:
    def __init__(
        self, repository: AuthRepository, hasher: PasswordHasher, tokens: TokenIssuer, dummy_password_hash: str
    ) -> None:
        self._repository = repository
        self._hasher = hasher
        self._tokens = tokens
        self._dummy_password_hash = dummy_password_hash

    def handle(self, command: LoginCommand) -> TokenPair:
        user = self._repository.find_by_username(command.username)
        valid = self._hasher.verify(command.password, user.password_hash if user else self._dummy_password_hash)
        if user is None or not valid:
            raise AuthenticationFailed()
        pair = self._tokens.issue_pair(user.user_id)
        self._repository.save_refresh_token(user.user_id, pair.refresh_token, pair.refresh_expires_at)
        return pair
