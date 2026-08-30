from pathlib import Path
import shutil
import tempfile
import uuid

import pytest
from sqlalchemy import create_engine, inspect, text

from backend.app.core.v3_migrations import (
    MigrationChecksumMismatch,
    apply_v3_migrations,
    mysql_migration_sql,
    v3_migration_status,
)


@pytest.fixture
def tmp_workspace():
    """Writable temp dir with best-effort cleanup.

    Created via ``Path.mkdir`` instead of ``tempfile.mkdtemp``: some sandboxed
    environments deny sqlite file creation inside mkdtemp-created directories,
    and pytest's builtin ``tmp_path`` session cleanup can also fail there.
    """
    base = Path(tempfile.gettempdir()) / f"harmonyai-v3-mig-{uuid.uuid4().hex}"
    base.mkdir(parents=True, exist_ok=True)
    yield base
    try:
        shutil.rmtree(base)
    except OSError:
        pass


def _create_legacy_foundation(engine):
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE users ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "openid VARCHAR(128) NOT NULL UNIQUE, nickname VARCHAR(64), "
                "avatar_url TEXT, phone VARCHAR(20), "
                "preferred_instruments TEXT, preferred_bpm_min INTEGER, "
                "preferred_bpm_max INTEGER, preferred_session VARCHAR(32), "
                "effective_syndrome_data TEXT, created_at DATETIME, updated_at DATETIME)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE sessions ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, "
                "session_id VARCHAR(64) NOT NULL UNIQUE, status VARCHAR(16), "
                "current_agent VARCHAR(32), metadata_json TEXT, "
                "created_at DATETIME, updated_at DATETIME)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO sessions (user_id, session_id, status) "
                "VALUES (7, 'sess_legacy', 'active')"
            )
        )


def test_sqlite_v3_migration_is_versioned_idempotent_and_preserves_sessions(tmp_workspace):
    engine = create_engine(f"sqlite:///{tmp_workspace / 'v3.db'}")
    _create_legacy_foundation(engine)

    first = apply_v3_migrations(engine)
    second = apply_v3_migrations(engine)

    assert first["applied_versions"] == [
        "0001_v3_foundation",
        "0002_v3_session_activity",
    ]
    assert second["applied_versions"] == []
    status = v3_migration_status(engine)
    assert status["applied"] is True
    assert status["foreign_keys_enabled"] is True
    assert status["sessions_user_fk"] is True
    assert status["missing_tables"] == []
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT user_id, session_id, flow_version FROM sessions")
        ).one()
        legacy_demo_user = connection.execute(
            text("SELECT openid FROM users WHERE id = 1")
        ).scalar_one()
    assert row == (7, "sess_legacy", None)
    assert legacy_demo_user == "legacy:demo:v2-default"
    session_indexes = inspect(engine).get_indexes("sessions")
    assert any(
        index["column_names"] == ["user_id", "created_at"]
        for index in session_indexes
    )


def test_applied_v3_migration_checksum_cannot_change(tmp_workspace):
    engine = create_engine(f"sqlite:///{tmp_workspace / 'checksum.db'}")
    _create_legacy_foundation(engine)
    apply_v3_migrations(engine)

    source = Path(__file__).parents[3] / "backend" / "migrations" / "v3"
    changed = tmp_workspace / "changed-migrations"
    shutil.copytree(source, changed)
    up = changed / "sqlite" / "0001_v3_foundation_up.sql"
    up.write_text(up.read_text(encoding="utf-8") + "\n-- changed\n", encoding="utf-8")

    with pytest.raises(MigrationChecksumMismatch):
        apply_v3_migrations(engine, migrations_root=changed)


def test_mysql_v3_migration_scripts_have_equivalent_foundation_constraints():
    up, down = mysql_migration_sql()

    assert "CREATE TABLE IF NOT EXISTS user_identities" in up
    assert "CREATE TABLE IF NOT EXISTS user_profiles" in up
    assert "CREATE TABLE IF NOT EXISTS idempotency_records" in up
    assert "FOREIGN KEY (user_id) REFERENCES users(id)" in up
    assert "ADD COLUMN flow_version" in up
    assert "ON sessions(user_id, created_at DESC)" in up
    assert "ENGINE=InnoDB" in up
    assert "DEFAULT CHARSET=utf8mb4" in up
    assert "DROP TABLE" not in up.upper()
    assert "DROP TABLE IF EXISTS user_identities" in down
    assert "DROP INDEX ix_sessions_user_created ON sessions" in down


def test_v3_activity_migration_creates_both_new_tables(tmp_workspace):
    engine = create_engine(f"sqlite:///{tmp_workspace / 'activity.db'}")
    _create_legacy_foundation(engine)

    result = apply_v3_migrations(engine)

    assert "0002_v3_session_activity" in result["applied_versions"]
    tables = set(inspect(engine).get_table_names())
    assert "v3_session_activities" in tables
    assert "v3_understanding_snapshots" in tables
    status = v3_migration_status(engine)
    assert status["session_activity_present"] is True
    assert status["understanding_snapshots_present"] is True
    assert status["applied"] is True


def test_mysql_activity_migration_scripts_are_dialect_equivalent():
    root = Path(__file__).parents[3] / "backend" / "migrations" / "v3"
    up = (root / "mysql" / "0002_v3_session_activity_up.sql").read_text(
        encoding="utf-8"
    )
    down = (root / "mysql" / "0002_v3_session_activity_down.sql").read_text(
        encoding="utf-8"
    )

    assert "CREATE TABLE IF NOT EXISTS v3_session_activities" in up
    assert "CREATE TABLE IF NOT EXISTS v3_understanding_snapshots" in up
    assert "UNIQUE KEY uq_v3_session_activity_session" in up
    assert "UNIQUE KEY uq_v3_understanding_revision" in up
    assert "REFERENCES sessions(session_id) ON DELETE CASCADE" in up
    assert "ENGINE=InnoDB" in up
    assert "DROP TABLE IF EXISTS v3_understanding_snapshots" in down
    assert "DROP TABLE IF EXISTS v3_session_activities" in down


def test_sqlite_activity_session_foreign_key_rejects_orphan_rows(tmp_workspace):
    engine = create_engine(f"sqlite:///{tmp_workspace / 'fk-activity.db'}")
    _create_legacy_foundation(engine)
    apply_v3_migrations(engine)

    with pytest.raises(Exception):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO v3_session_activities ("
                    "session_id, internal_user_pk, input_revision"
                    ") VALUES ('sess_orphan_activity', 1, 1)"
                )
            )

    assert inspect(engine).get_foreign_keys("v3_session_activities")
    assert inspect(engine).get_foreign_keys("v3_understanding_snapshots")


def test_sqlite_understanding_snapshot_session_foreign_key(tmp_workspace):
    engine = create_engine(f"sqlite:///{tmp_workspace / 'fk-und.db'}")
    _create_legacy_foundation(engine)
    apply_v3_migrations(engine)

    with pytest.raises(Exception):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO v3_understanding_snapshots ("
                    "understanding_id, revision, session_id, internal_user_pk, "
                    "status, snapshot_json"
                    ") VALUES ('und_orphan', 1, 'sess_orphan_und', 1, "
                    "'needs_confirmation', '{}')"
                )
            )


def test_v3_migrations_tolerate_orm_create_all_first(tmp_workspace):
    """Reproduces the CI failure on f5a08df: when Base.metadata.create_all
    (ORM model) already created idempotency_records WITH response_json,
    the 0002 ALTER must be skipped instead of raising
    ``duplicate column name: response_json``."""
    from backend.app.core.database import Base

    engine = create_engine(f"sqlite:///{tmp_workspace / 'orm-first.db'}")
    Base.metadata.create_all(bind=engine)

    result = apply_v3_migrations(engine)

    assert "0002_v3_session_activity" in result["applied_versions"]
    columns = [
        column["name"]
        for column in inspect(engine).get_columns("idempotency_records")
    ]
    assert columns.count("response_json") == 1
    # and the new tables exist exactly once
    assert "v3_session_activities" in inspect(engine).get_table_names()
    assert "v3_understanding_snapshots" in inspect(engine).get_table_names()


def test_sqlite_0002_down_rolls_back_response_json_and_tables(tmp_workspace):
    """0002 owns the idempotency_records.response_json column, so its down
    migration must remove the column and both tables."""
    root = Path(__file__).parents[3] / "backend" / "migrations" / "v3"
    engine = create_engine(f"sqlite:///{tmp_workspace / 'down.db'}")
    _create_legacy_foundation(engine)
    apply_v3_migrations(engine)

    columns = [
        column["name"]
        for column in inspect(engine).get_columns("idempotency_records")
    ]
    assert "response_json" in columns
    assert "v3_session_activities" in inspect(engine).get_table_names()
    assert "v3_understanding_snapshots" in inspect(engine).get_table_names()

    down = (root / "sqlite" / "0002_v3_session_activity_down.sql").read_text(
        encoding="utf-8"
    )
    raw = engine.raw_connection()
    try:
        # The pooled connection may predate the 0002 up run (which executed
        # on a different pooled connection); refresh its schema cache before
        # applying the down script, otherwise SQLite reports the ALTER-added
        # column as missing.
        raw.execute("PRAGMA table_info(idempotency_records)").fetchall()
        raw.commit()
        raw.executescript(down)
        raw.commit()
    finally:
        raw.close()

    columns = [
        column["name"]
        for column in inspect(engine).get_columns("idempotency_records")
    ]
    assert "response_json" not in columns
    assert "v3_session_activities" not in inspect(engine).get_table_names()
    assert "v3_understanding_snapshots" not in inspect(engine).get_table_names()
    # simulate a true rollback-then-reapply: clear the 0002 ledger entry
    # (down does not delete the ledger) and run up again
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "DELETE FROM schema_migrations "
            "WHERE version = '0002_v3_session_activity'"
        )
    result = apply_v3_migrations(engine)
    assert "0002_v3_session_activity" in result["applied_versions"]
    assert "response_json" in [
        column["name"]
        for column in inspect(engine).get_columns("idempotency_records")
    ]


def test_mysql_0002_down_script_rolls_back_response_json():
    root = Path(__file__).parents[3] / "backend" / "migrations" / "v3"
    down = (root / "mysql" / "0002_v3_session_activity_down.sql").read_text(
        encoding="utf-8"
    )
    up = (root / "mysql" / "0002_v3_session_activity_up.sql").read_text(
        encoding="utf-8"
    )

    assert "ALTER TABLE idempotency_records DROP COLUMN response_json" in down
    assert "DROP TABLE IF EXISTS v3_understanding_snapshots" in down
    assert "DROP TABLE IF EXISTS v3_session_activities" in down
    # up declares the column with a marker so create_all-first is tolerated
    assert "ADD COLUMN response_json" in up
    assert "V3_IDEMPOTENCY_RESPONSE_JSON_BEGIN" in up


def test_sqlite_foreign_key_enforcement_rejects_new_orphan_session(tmp_workspace):
    engine = create_engine(f"sqlite:///{tmp_workspace / 'fk.db'}")
    _create_legacy_foundation(engine)
    apply_v3_migrations(engine)

    with pytest.raises(Exception):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO sessions (user_id, session_id, status, flow_version) "
                    "VALUES (999, 'sess_orphan', 'active', 'v3')"
                )
            )

    assert inspect(engine).get_foreign_keys("sessions")


def test_sqlite_v3_identity_constraints_and_cascade_are_enforced(tmp_workspace):
    engine = create_engine(f"sqlite:///{tmp_workspace / 'constraints.db'}")
    _create_legacy_foundation(engine)
    apply_v3_migrations(engine)

    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id, openid) "
                "VALUES (20, 'guest:constraint-owner')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO user_identities ("
                "internal_user_pk, public_user_id, auth_type, guest_expires_at"
                ") VALUES (20, 'u_guest_constraint', 'guest', "
                "'2030-01-01 00:00:00')"
            )
        )

    with pytest.raises(Exception):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO user_identities ("
                    "internal_user_pk, public_user_id, auth_type, guest_expires_at"
                    ") VALUES (1, 'u_invalid_registered', 'registered', "
                    "'2030-01-01 00:00:00')"
                )
            )

    with engine.begin() as connection:
        connection.execute(text("DELETE FROM users WHERE id = 20"))
    with engine.connect() as connection:
        remaining = connection.execute(
            text(
                "SELECT COUNT(*) FROM user_identities "
                "WHERE public_user_id = 'u_guest_constraint'"
            )
        ).scalar_one()
    assert remaining == 0