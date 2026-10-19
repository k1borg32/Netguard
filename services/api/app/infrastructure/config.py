"""Application settings loaded from environment variables."""

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    database_url: str
    jwt_secret: SecretStr

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        extra="ignore",
    )


def database_dsn() -> str:
    """Normalize the configured URL for the existing psycopg driver."""
    return Settings().database_url.replace("postgresql+psycopg://", "postgresql://", 1)
