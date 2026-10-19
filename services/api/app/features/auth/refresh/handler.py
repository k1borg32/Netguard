from app.abstraction.auth.models import TokenPair
from app.abstraction.auth.ports import AuthRepository, TokenIssuer
from app.features.auth.exceptions import AuthenticationFailed

from .command import RefreshCommand


class RefreshHandler:
    def __init__(self, repository: AuthRepository, tokens: TokenIssuer) -> None:
        self._repository = repository
        self._tokens = tokens

    def handle(self, command: RefreshCommand) -> TokenPair:
        user = self._repository.find_by_id(command.token.user_id)
        if user is None:
            raise AuthenticationFailed()
        pair = self._tokens.issue_pair(user.user_id)
        if not self._repository.rotate_refresh_token(
            user.user_id, command.token.raw_token, pair.refresh_token, pair.refresh_expires_at
        ):
            raise AuthenticationFailed()
        return pair
