"""Database engine and session factory."""
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker, declarative_base

from backend.app.core.config import Settings, settings


def build_database_engine(configuration: Settings):
    """Construct without connecting; TLS failures must stop engine creation."""
    url = make_url(configuration.DATABASE_URL)
    if url.drivername != 'mysql+pymysql' and configuration.MYSQL_TLS_CA_FILE is not None:
        raise ValueError('MYSQL_TLS_CA_FILE requires the mysql+pymysql driver')
    options = {"echo": configuration.DEBUG, "pool_pre_ping": True}
    if url.get_backend_name() == 'sqlite':
        options['connect_args'] = {'check_same_thread': False}
    else:
        options.update({'pool_size': 5, 'max_overflow': 10})
        if (url.drivername == 'mysql+pymysql'
                and (configuration.APP_ENV == 'production'
                     or configuration.MYSQL_TLS_CA_FILE is not None)):
            options['connect_args'] = {'ssl': configuration.build_mysql_tls_context()}
    return create_engine(configuration.DATABASE_URL, **options)


engine = build_database_engine(settings)
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
    from backend.app.core.sprint4_migrations import apply_sprint4_migrations
    from backend.app.core.v3_migrations import apply_v3_migrations, preflight_v3_migrations

    preflight_v3_migrations(engine)
    Base.metadata.create_all(bind=engine)
    apply_sprint4_migrations(engine)
    apply_v3_migrations(engine)


def get_db():
    """FastAPI dependency — yields a DB session and closes it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
