from datetime import timedelta

from authx import AuthX, AuthXConfig

from app.infrastructure.config import Settings

ACCESS_TOKEN_TTL = timedelta(minutes=15)
REFRESH_TOKEN_TTL = timedelta(days=7)


def create_auth() -> AuthX:
    return AuthX(
        config=AuthXConfig(
            JWT_SECRET_KEY=Settings().jwt_secret.get_secret_value(),
            JWT_ALGORITHM="HS256",
            JWT_TOKEN_LOCATION=["headers"],
            JWT_ACCESS_TOKEN_EXPIRES=ACCESS_TOKEN_TTL,
            JWT_REFRESH_TOKEN_EXPIRES=REFRESH_TOKEN_TTL,
        )
    )
