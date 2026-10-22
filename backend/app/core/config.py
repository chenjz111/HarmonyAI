"""Application configuration."""
from pathlib import Path
import ssl
from typing import Literal
from urllib.parse import parse_qsl, urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


def _valid_mysql_query(raw_query: str) -> bool:
    """Only non-target PyMySQL options; seconds are deliberately bounded."""
    pairs = parse_qsl(raw_query, keep_blank_values=True, strict_parsing=True)
    if len({name for name, _ in pairs}) != len(pairs):
        return False
    for name, value in pairs:
        if name == 'charset':
            if value != 'utf8mb4':
                return False
        elif name in {'connect_timeout', 'read_timeout', 'write_timeout'}:
            if not value.isascii() or not value.isdecimal() or not 1 <= int(value) <= 600:
                return False
        else:
            return False
    return True


def _has_obvious_key_pattern(key: str) -> bool:
    """Screen obvious patterns, not entropy; production keys still need CSPRNGs.

    Reject a whole-key period with at least two blocks (allowing a trailing
    partial block). Local repetition in an otherwise nonperiodic key is not
    sufficient. The prefix-function keeps the scan linear in key length.
    """
    prefixes = [0] * len(key)
    for i in range(1, len(key)):
        matched = prefixes[i - 1]
        while matched and key[i] != key[matched]:
            matched = prefixes[matched - 1]
        if key[i] == key[matched]:
            matched += 1
        prefixes[i] = matched
    if key and len(key) - prefixes[-1] <= len(key) // 2:
        return True

    # Deliberately finite denylist: ascending/descending alphabet, digit and
    # keyboard cycles, including rotated starts. Not a general strength meter.
    lowered = key.lower()
    for alphabet in (
        '0123456789abcdef',
        'abcdefghijklmnopqrstuvwxyz0123456789',
        '0123456789abcdefghijklmnopqrstuvwxyz',
        'qwertyuiopasdfghjklzxcvbnm0123456789',
    ):
        for sequence in (alphabet, alphabet[::-1]):
            cycle = sequence * (len(lowered) // len(sequence) + 2)
            if lowered and lowered in cycle:
                return True
    return False


class Settings(BaseSettings):
    """App settings loaded from environment variables / .env file."""

    APP_NAME: str = "HarmonyAI"
    APP_VERSION: str = "0.3.0"
    APP_ENV: Literal["development", "test", "production"] = "development"
    DEBUG: bool = True

    # Portable competition/demo default. Deployments can override DATABASE_URL.
    DATABASE_URL: str = Field(default="sqlite:///./harmonyai.db", repr=False)
    # Independent of the URL: query options may never disable/override TLS.
    MYSQL_TLS_CA_FILE: str | None = Field(default=None, repr=False)

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

    def build_mysql_tls_context(self) -> ssl.SSLContext:
        """Revalidate CA at engine construction; never downgrade on failure."""
        try:
            path = Path(self.MYSQL_TLS_CA_FILE or '')
            if not self.MYSQL_TLS_CA_FILE or not path.is_absolute() or not path.is_file():
                raise ValueError('Invalid CA target')
            context = ssl.create_default_context(cafile=str(path))
            context.verify_mode = ssl.CERT_REQUIRED
            context.check_hostname = True
        except (OSError, ValueError, ssl.SSLError):
            # No file path, URL, credentials or underlying OpenSSL error leaks.
            raise ValueError('MySQL TLS configuration rejected') from None
        return context

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
            or _has_obvious_key_pattern(key)
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
            elif url.drivername == "mysql+pymysql":
                valid = (
                    all(isinstance(v, str) and bool(v.strip()) and v == v.strip()
                        for v in (url.host, url.database, url.username, url.password))
                    and _valid_mysql_query(raw_query)
                    and not any(c.isspace() for c in url.host)
                    and (url.port is None or 1 <= url.port <= 65535)
                )
            else:
                valid = False
        except (ArgumentError, ValueError, TypeError):
            valid = False
        if not valid:
            raise ValueError("Production DATABASE_URL must identify a complete supported database target")
        if url.drivername == 'mysql+pymysql':
            self.build_mysql_tls_context()
        return self


settings = Settings()
