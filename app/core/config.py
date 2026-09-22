from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuracao compartilhada entre o Web Service e o futuro Worker."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = Field(validation_alias="DATABASE_URL")
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    max_cnpjs_per_job: int = Field(default=500, gt=0, validation_alias="MAX_CNPJS_PER_JOB")
    cnpjws_base_url: str = Field(default="https://publica.cnpj.ws", validation_alias="CNPJWS_BASE_URL")
    cnpjws_timeout_seconds: int = Field(default=15, gt=0, validation_alias="CNPJWS_TIMEOUT_SECONDS")
    cnpjws_rate_limit_interval_seconds: int = Field(
        default=21, ge=21, validation_alias="CNPJWS_RATE_LIMIT_INTERVAL_SECONDS"
    )
    cnpjws_max_attempts: int = Field(default=3, gt=0, validation_alias="CNPJWS_MAX_ATTEMPTS")
    cnpjws_429_cooldown_seconds: int = Field(default=60, ge=60, validation_alias="CNPJWS_429_COOLDOWN_SECONDS")
    worker_poll_interval_seconds: int = Field(default=5, gt=0, validation_alias="WORKER_POLL_INTERVAL_SECONDS")
    worker_lease_seconds: int = Field(default=60, gt=0, validation_alias="WORKER_LEASE_SECONDS")
    run_embedded_worker: bool = Field(default=False, validation_alias="RUN_EMBEDDED_WORKER")

    @field_validator("database_url", mode="before")
    @classmethod
    def use_psycopg_for_render_postgres(cls, value: object) -> object:
        """Makes Render's PostgreSQL URL select the installed psycopg 3 dialect."""
        if isinstance(value, str) and value.startswith("postgresql://"):
            return f"postgresql+psycopg://{value.removeprefix('postgresql://')}"
        return value

    @model_validator(mode="after")
    def validate_worker_lease(self) -> "Settings":
        if self.worker_lease_seconds <= self.cnpjws_timeout_seconds:
            raise ValueError("WORKER_LEASE_SECONDS must be greater than CNPJWS_TIMEOUT_SECONDS")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
