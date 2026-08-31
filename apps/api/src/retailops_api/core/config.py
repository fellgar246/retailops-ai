from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from retailops_api.core.aws import AwsConfig


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

    # Empty means the CLI uses <repo>/data/documents. Set this to pin a root.
    document_storage_root: str = ""

    # AWS stays disabled unless explicitly enabled. Feature flags cannot turn
    # adapters on by themselves.
    aws_enabled: bool = False
    aws_region: str = "us-east-1"
    aws_account_id: str = ""
    aws_environment_name: str = "local"
    aws_resource_prefix: str = "retailops"
    aws_documents_bucket: str = ""
    aws_documents_prefix: str = "documents"
    aws_bedrock_model_id: str = ""
    aws_sagemaker_model_group: str = "category-forecast"
    aws_sagemaker_artifact_prefix: str = "models"
    aws_use_s3_storage: bool = False
    aws_use_textract: bool = False
    aws_use_bedrock: bool = False
    aws_use_sagemaker_registry: bool = False

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    def aws_config(self) -> AwsConfig:
        environment_name = self.aws_environment_name.strip() or self.environment
        return AwsConfig(
            enabled=self.aws_enabled,
            region=self.aws_region,
            account_id=self.aws_account_id.strip(),
            environment_name=environment_name,
            resource_prefix=self.aws_resource_prefix.strip() or "retailops",
            documents_bucket=self.aws_documents_bucket.strip(),
            documents_prefix=self.aws_documents_prefix.strip() or "documents",
            bedrock_model_id=self.aws_bedrock_model_id.strip(),
            sagemaker_model_group=self.aws_sagemaker_model_group.strip() or "category-forecast",
            sagemaker_artifact_prefix=self.aws_sagemaker_artifact_prefix.strip() or "models",
            use_s3_storage=self.aws_use_s3_storage,
            use_textract=self.aws_use_textract,
            use_bedrock=self.aws_use_bedrock,
            use_sagemaker_registry=self.aws_use_sagemaker_registry,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
