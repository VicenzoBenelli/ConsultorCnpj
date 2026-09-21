import pytest
from pydantic import ValidationError

from app.core.config import get_settings


def test_settings_reads_required_database_url(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:password@localhost:5432/app")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("MAX_CNPJS_PER_JOB", "25")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.database_url == "postgresql+psycopg://user:password@localhost:5432/app"
    assert settings.app_env == "test"
    assert settings.log_level == "DEBUG"
    assert settings.max_cnpjs_per_job == 25
    get_settings.cache_clear()


def test_settings_rejects_non_positive_max_cnpjs_per_job(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:password@localhost:5432/app")
    monkeypatch.setenv("MAX_CNPJS_PER_JOB", "0")
    get_settings.cache_clear()

    with pytest.raises(ValidationError):
        get_settings()

    get_settings.cache_clear()


def test_settings_validate_worker_configuration(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:password@localhost:5432/app")
    monkeypatch.setenv("CNPJWS_RATE_LIMIT_INTERVAL_SECONDS", "20")
    get_settings.cache_clear()

    with pytest.raises(ValidationError):
        get_settings()

    monkeypatch.setenv("CNPJWS_RATE_LIMIT_INTERVAL_SECONDS", "21")
    monkeypatch.setenv("CNPJWS_TIMEOUT_SECONDS", "15")
    monkeypatch.setenv("WORKER_LEASE_SECONDS", "15")
    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        get_settings()
    get_settings.cache_clear()
