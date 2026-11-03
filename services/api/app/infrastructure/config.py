"""Application settings loaded from environment variables."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    jwt_secret: SecretStr

    model_config = SettingsConfigDict(extra="ignore")


def database_dsn() -> str:
    """Normalize the configured URL for the existing psycopg driver."""
    return Settings().database_url.replace("postgresql+psycopg://", "postgresql://", 1)
