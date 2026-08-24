"""Database engine and session factory."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

from backend.app.core.config import settings


_engine_options = {
    "echo": settings.DEBUG,
    "pool_pre_ping": True,
}
if settings.DATABASE_URL.startswith("sqlite"):
    _engine_options["connect_args"] = {"check_same_thread": False}
else:
    _engine_options.update({"pool_size": 5, "max_overflow": 10})

engine = create_engine(settings.DATABASE_URL, **_engine_options)
if settings.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_database() -> None:
    """Create the lightweight local schema for development and demos."""
    Base.metadata.create_all(bind=engine)
    from backend.app.core.sprint4_migrations import apply_sprint4_migrations
    from backend.app.core.v3_migrations import apply_v3_migrations

    apply_sprint4_migrations(engine)
    apply_v3_migrations(engine)


def get_db():
    """FastAPI dependency — yields a DB session and closes it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
