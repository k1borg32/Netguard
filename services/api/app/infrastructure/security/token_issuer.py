from uuid import UUID

from authx import AuthX, RequestToken

from .models import TokenPair


class AuthXTokenIssuer:
    def __init__(self, auth: AuthX) -> None:
        self._auth = auth

    def issue_pair(self, user_id: UUID) -> TokenPair:
        tokens = self._auth.create_token_pair(uid=str(user_id))
        payload = self._auth.verify_token(RequestToken(token=tokens.refresh_token, type="refresh", location="headers"))
        return TokenPair(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            refresh_expires_at=payload.exp,
        )
