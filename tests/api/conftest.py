"""Isolated database fixtures for API tests.

API tests must not depend on a developer's local MySQL credentials.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from backend.app.core.database import Base, get_db
from backend.app.main import app


_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestingSession = sessionmaker(
    bind=_engine,
    autocommit=False,
    autoflush=False,
)


def _override_get_db():
    db = _TestingSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def isolated_api_database():
    Base.metadata.create_all(bind=_engine)
    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=_engine)


@pytest.fixture
def db_session_factory():
    """Expose the isolated testing session factory for direct row setup."""

    return _TestingSession


@pytest.fixture
def concurrent_api_database(tmp_path):
    """Use a file-backed SQLite database so two requests have transactions."""

    engine = create_engine(
        f"sqlite:///{tmp_path / 'concurrent.db'}",
        connect_args={"check_same_thread": False, "timeout": 10},
        poolclass=NullPool,
    )

    session_factory = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
    )
    Base.metadata.create_all(bind=engine)

    previous_override = app.dependency_overrides.get(get_db)

    def _override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield session_factory, engine
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
