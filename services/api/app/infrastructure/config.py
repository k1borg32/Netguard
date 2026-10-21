"""Application settings loaded from environment variables."""

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> Path | None:
    """The repo's .env for local runs. In the container there is none and Compose passes the variables."""
    return next((folder / ".env" for folder in Path(__file__).resolve().parents if (folder / ".env").is_file()), None)


class Settings(BaseSettings):
    database_url: str
    jwt_secret: SecretStr

    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
        extra="ignore",
    )


def database_dsn() -> str:
    """Normalize the configured URL for the existing psycopg driver."""
    return Settings().database_url.replace("postgresql+psycopg://", "postgresql://", 1)
