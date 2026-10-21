"""Application configuration."""
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    """App settings loaded from environment variables / .env file."""

    APP_NAME: str = "HarmonyAI"
    APP_VERSION: str = "0.3.0"
    APP_ENV: Literal["development", "test", "production"] = "development"
    DEBUG: bool = True

    # Portable competition/demo default. Deployments can override DATABASE_URL.
    DATABASE_URL: str = Field(default="sqlite:///./harmonyai.db", repr=False)

    # Retained for backward-compatible environment documentation only.
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = Field(default="", repr=False)
    MYSQL_DATABASE: str = "harmonyai"

    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0", repr=False)

    # JWT
    JWT_SECRET_KEY: str = Field(default="change-me-in-production", repr=False)
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # CORS
    CORS_ORIGINS: list[str] = ["*"]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "hide_input_in_errors": True,
    }

    def __init__(self, **values):
        # Pydantic's hide_input_in_errors protects str(error), but errors()
        # still retains the complete input mapping. Do not expose that object
        # at the runtime configuration boundary, including structured logging.
        rejected = False
        try:
            super().__init__(**values)
        except ValueError:
            rejected = True
        if rejected:
            raise ValueError("Runtime configuration rejected; verify APP_ENV and explicit production settings")

    @model_validator(mode="after")
    def validate_production_runtime(self) -> "Settings":
        """Validate configuration only: never connect or initialize a DB.

        APP_ENV must be explicitly selected by deployment tooling. Development
        defaults are intentionally retained; passing this gate is not deploy
        authorization, entropy certification or MySQL execution evidence.
        """
        if self.APP_ENV != "production":
            return self
        required = {"DEBUG", "JWT_SECRET_KEY", "DATABASE_URL", "CORS_ORIGINS"}
        if not required.issubset(self.model_fields_set):
            raise ValueError("Production requires explicit DEBUG, JWT_SECRET_KEY, DATABASE_URL and CORS_ORIGINS")
        if self.DEBUG:
            raise ValueError("Production DEBUG and SQL echo must be disabled")
        key = self.JWT_SECRET_KEY
        if (
            self.JWT_ALGORITHM != "HS256"
            or key != key.strip()
            or len(key.encode("utf-8")) < 32
            or len(set(key)) < 12
            or key.lower() in {"change-me-in-production", "changeme", "secret", "password"}
        ):
            raise ValueError("Production requires an approved HS256 signing key, not a default or weak value")
        for origin in self.CORS_ORIGINS:
            try:
                parsed = urlsplit(origin)
                valid = (
                    parsed.scheme == "https" and bool(parsed.hostname)
                    and not parsed.username and not parsed.password
                    and not parsed.path and not parsed.query and not parsed.fragment
                    and "*" not in origin and not any(c.isspace() for c in origin)
                    and (parsed.port is None or 1 <= parsed.port <= 65535)
                )
            except ValueError:
                valid = False
            if not valid:
                raise ValueError("Production CORS_ORIGINS must contain only explicit HTTPS origins")
        # An explicit empty CORS list is deny-all, not a wildcard fallback.
        try:
            url = make_url(self.DATABASE_URL)
            # make_url normalizes away blank query values. Check the raw URL
            # too, so an explicitly supplied option never silently disappears.
            raw_query = urlsplit(self.DATABASE_URL).query
            if url.drivername in {"sqlite", "sqlite+pysqlite"}:
                target = Path(url.database or "")
                valid = (
                    bool(url.database) and target.is_absolute()
                    and ".." not in target.parts
                    and not str(url.database).startswith(("\\\\", "//"))
                    and not url.host and not url.username and not url.password
                    and not url.query and not raw_query
                )
            elif url.drivername in {"mysql", "mysql+pymysql"}:
                valid = (
                    all(isinstance(v, str) and bool(v.strip()) and v == v.strip()
                        for v in (url.host, url.database, url.username, url.password))
                    and not url.query and not raw_query  # Driver options can override the target.
                    and not any(c.isspace() for c in url.host)
                    and (url.port is None or 1 <= url.port <= 65535)
                )
            else:
                valid = False
        except (ArgumentError, ValueError, TypeError):
            valid = False
        if not valid:
            raise ValueError("Production DATABASE_URL must identify a complete supported database target")
        return self


settings = Settings()
