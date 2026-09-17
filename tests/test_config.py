from app.core.config import get_settings


def test_settings_reads_required_database_url(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:password@localhost:5432/app")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.database_url == "postgresql+psycopg://user:password@localhost:5432/app"
    assert settings.app_env == "test"
    assert settings.log_level == "DEBUG"
    get_settings.cache_clear()

