from backend.app.core.config import Settings


def test_default_database_is_portable_sqlite(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    settings = Settings(_env_file=None)

    assert settings.DATABASE_URL.startswith("sqlite:///")


def test_database_url_can_be_overridden_for_deployment(monkeypatch):
    url = "mysql+pymysql://app:password@database/harmonyai"
    monkeypatch.setenv("DATABASE_URL", url)

    settings = Settings(_env_file=None)

    assert settings.DATABASE_URL == url
