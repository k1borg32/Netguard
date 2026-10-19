from app.abstraction.auth.models import AuthUser
from app.abstraction.auth.ports import AuthRepository
from app.features.auth.exceptions import AuthenticationFailed

from .query import GetCurrentUserQuery


class GetCurrentUserHandler:
    def __init__(self, repository: AuthRepository) -> None:
        self._repository = repository

    def handle(self, query: GetCurrentUserQuery) -> AuthUser:
        user = self._repository.find_by_id(query.user_id)
        if user is None:
            raise AuthenticationFailed()
        return user
