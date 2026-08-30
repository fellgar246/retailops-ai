from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration resolved from environment variables."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "RetailOps AI API"
    environment: str = "local"
    log_level: str = "info"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    database_url: str = Field(
        default="postgresql+psycopg://retailops:retailops@localhost:5435/retailops"
    )
    database_echo: bool = False

    # `NoDecode` keeps pydantic-settings from JSON-decoding the raw value, so the
    # variable can be written as a plain comma-separated list.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
