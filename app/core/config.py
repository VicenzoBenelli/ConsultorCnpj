from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuracao compartilhada entre o Web Service e o futuro Worker."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = Field(validation_alias="DATABASE_URL")
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    max_cnpjs_per_job: int = Field(default=500, gt=0, validation_alias="MAX_CNPJS_PER_JOB")


@lru_cache
def get_settings() -> Settings:
    return Settings()
