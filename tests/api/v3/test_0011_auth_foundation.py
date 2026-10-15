"""Synthetic SQLite execution and migration-history safety, not auth enablement."""
import shutil
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from backend.app.core import v3_migrations as migrations
from tests.api.v3.test_v3_migrations import _create_legacy_foundation

ROOT = Path(__file__).resolve().parents[3] / 'backend/migrations/v3'
VERSION = '0011_v3_auth_foundation'


@pytest.fixture
def old_database(tmp_path, monkeypatch):
    engine = create_engine(f'sqlite:///{tmp_path / "isolated.sqlite"}')
    _create_legacy_foundation(engine)
    versions = list(migrations.V3_MIGRATION_VERSIONS)
    with monkeypatch.context() as context:
        context.setattr(migrations,'V3_MIGRATION_VERSIONS',versions[:10])
        migrations.apply_v3_migrations(engine)
    yield engine
    engine.dispose()


def test_real_0011_is_registered():
    assert migrations.V3_MIGRATION_VERSIONS[-1] == VERSION


def test_upgrade_preserves_owner_and_old_guest_jwt(old_database):
    from backend.app.services.v3.auth_service import create_guest_principal, _resolve_principal
    from sqlalchemy.orm import Session
    with old_database.begin() as connection:
        connection.execute(text("INSERT INTO user_identities(internal_user_pk,public_user_id,auth_type,guest_expires_at) VALUES(7,'synthetic:old','guest','2099-01-01')"))
        before_users = connection.execute(text('SELECT * FROM users')).fetchall()
        before_sessions = connection.execute(text('SELECT * FROM sessions')).fetchall()
    result = migrations.apply_v3_migrations(old_database)
    assert result['applied_versions'] == [VERSION]
    with old_database.connect() as connection:
        assert connection.execute(text('SELECT * FROM users')).fetchall() == before_users
        assert connection.execute(text('SELECT * FROM sessions')).fetchall() == before_sessions
        assert connection.execute(text('SELECT auth_epoch FROM user_identities WHERE internal_user_pk=7')).scalar_one() == 0
    from datetime import datetime, timezone
    from backend.app.services.v3.auth_service import _encode_guest_token
    old_token = _encode_guest_token('synthetic:old',datetime(2099,1,1,tzinfo=timezone.utc))
    with Session(old_database) as session:
        assert _resolve_principal(old_token, session).internal_user_pk == 7
        new_guest = create_guest_principal(session)
        assert _resolve_principal(new_guest.access_token,session).public_user_id == new_guest.public_user_id
    assert migrations.apply_v3_migrations(old_database)['applied_versions'] == []


def test_fresh_create_all_and_repeat_startup(tmp_path, monkeypatch):
    from backend.app.core import database
    import backend.app.models  # noqa: F401
    engine = create_engine(f'sqlite:///{tmp_path / "fresh.sqlite"}')
    monkeypatch.setattr(database,'engine',engine)
    database.init_database()
    database.init_database()
    assert 'auth_sessions' in inspect(engine).get_table_names()
    with engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM schema_migrations')).scalar_one() == 11
    engine.dispose()


def test_schema_defaults_and_session_constraints(old_database):
    migrations.apply_v3_migrations(old_database)
    with old_database.begin() as connection:
        connection.execute(text("INSERT INTO auth_sessions(auth_session_id,internal_user_pk,refresh_credential_hash,family_id,created_at,expires_at) VALUES('s1',7,'synthetic-digest-1','f1','2026-01-01','2099-01-01')"))
        assert connection.execute(text("SELECT revoked_at FROM auth_sessions WHERE auth_session_id='s1'")).scalar_one() is None
    invalid = [
        "UPDATE user_identities SET auth_epoch=-1",
        "INSERT INTO auth_sessions(auth_session_id,internal_user_pk,refresh_credential_hash,family_id,created_at,expires_at) VALUES('orphan',999,'digest-orphan','f','2026-01-01','2099-01-01')",
        "INSERT INTO auth_sessions(auth_session_id,internal_user_pk,refresh_credential_hash,family_id,created_at,expires_at) VALUES('dup',7,'synthetic-digest-1','f','2026-01-01','2099-01-01')",
        "INSERT INTO auth_sessions(auth_session_id,internal_user_pk,refresh_credential_hash,family_id,created_at,expires_at) VALUES('bad-time',7,'digest-time','f','2099-01-01','2026-01-01')",
        "INSERT INTO auth_sessions(auth_session_id,internal_user_pk,refresh_credential_hash,family_id,created_at,expires_at,revoked_at) VALUES('bad-revoke',7,'digest-revoke','f','2026-01-01','2099-01-01','2025-01-01')",
    ]
    for sql in invalid:
        with pytest.raises(IntegrityError):
            with old_database.begin() as connection:
                # Old identity row is required for the epoch constraint test.
                if sql.startswith('UPDATE'):
                    connection.execute(text("INSERT INTO user_identities(internal_user_pk,public_user_id,auth_type) VALUES(7,'synthetic:registered','registered')"))
                connection.execute(text(sql))


@pytest.mark.parametrize('case',['unknown','hole','reordered','duplicate'])
def test_history_rejected_before_any_new_ddl(old_database, case, monkeypatch):
    if case == 'unknown':
        with old_database.begin() as connection:
            connection.execute(text("INSERT INTO schema_migrations(version,checksum) VALUES('0012_library','sha256:synthetic')"))
    elif case == 'hole':
        with old_database.begin() as connection:
            connection.execute(text("DELETE FROM schema_migrations WHERE version='0005_v3_relevance'"))
    elif case == 'reordered':
        with old_database.begin() as connection:
            connection.execute(text("UPDATE schema_migrations SET applied_at='2000-01-01' WHERE version='0010_v3_generation_prompt_audit'"))
    else:
        monkeypatch.setattr(migrations,'V3_MIGRATION_VERSIONS',migrations.V3_MIGRATION_VERSIONS+[VERSION])
    with pytest.raises(migrations.MigrationOrderError):
        migrations.apply_v3_migrations(old_database)
    assert 'auth_sessions' not in inspect(old_database).get_table_names()
    assert 'auth_epoch' not in {c['name'] for c in inspect(old_database).get_columns('user_identities')}


def test_all_prior_checksums_checked_before_new_ddl(old_database):
    with old_database.begin() as connection:
        connection.execute(text("UPDATE schema_migrations SET checksum='sha256:tampered' WHERE version='0010_v3_generation_prompt_audit'"))
    with pytest.raises(migrations.MigrationChecksumMismatch):
        migrations.apply_v3_migrations(old_database)
    assert 'auth_sessions' not in inspect(old_database).get_table_names()


def test_initialization_preflight_runs_before_create_all(old_database, monkeypatch):
    from backend.app.core import database
    monkeypatch.setattr(database,'engine',old_database)
    with old_database.begin() as connection:
        connection.execute(text("INSERT INTO schema_migrations(version,checksum) VALUES('0012_library','sha256:synthetic')"))
    before = set(inspect(old_database).get_table_names())
    with pytest.raises(migrations.MigrationOrderError):
        database.init_database()
    assert set(inspect(old_database).get_table_names()) == before


def test_0011_failure_is_atomic_and_can_retry(old_database,tmp_path):
    modified = tmp_path / 'migrations'
    shutil.copytree(ROOT,modified)
    source = modified / 'sqlite' / f'{VERSION}_up.sql'
    assert source.exists(), '0011 SQL not implemented'
    source.write_text(source.read_text() + '\nINSERT INTO missing_table VALUES(1);\n')
    with pytest.raises(Exception):
        migrations.apply_v3_migrations(old_database,migrations_root=modified)
    assert 'auth_sessions' not in inspect(old_database).get_table_names()
    assert 'auth_epoch' not in {c['name'] for c in inspect(old_database).get_columns('user_identities')}
    assert migrations.apply_v3_migrations(old_database)['applied_versions'] == [VERSION]


def test_partial_schema_from_create_all_can_resume(old_database):
    from backend.app.models.v3.identity import AuthSession
    with old_database.begin() as connection:
        connection.execute(text('ALTER TABLE user_identities ADD COLUMN auth_epoch INTEGER NOT NULL DEFAULT 0 CHECK(auth_epoch>=0)'))
    AuthSession.__table__.create(old_database)
    assert migrations.apply_v3_migrations(old_database)['applied_versions'] == [VERSION]


def test_existing_wrong_epoch_definition_fails_closed(old_database):
    with old_database.begin() as connection:
        connection.execute(text('ALTER TABLE user_identities ADD COLUMN auth_epoch TEXT NULL'))
    with pytest.raises(migrations.MigrationSchemaMismatch):
        migrations.apply_v3_migrations(old_database)
    assert 'auth_sessions' not in inspect(old_database).get_table_names()


def test_mysql_model_ddl_only_no_service_connection():
    from sqlalchemy.schema import CreateTable
    from sqlalchemy.dialects import mysql
    from backend.app.models.v3.identity import AuthSession
    sql = str(CreateTable(AuthSession.__table__).compile(dialect=mysql.dialect()))
    assert 'FOREIGN KEY' in sql and 'refresh_credential_hash' in sql
    up, down = migrations.mysql_migration_sql()
    assert 'auth_sessions' in up and 'auth_sessions' in down


def test_0011_down_requires_empty_sessions_and_zero_epoch(old_database):
    migrations.apply_v3_migrations(old_database)
    with old_database.begin() as connection:
        connection.execute(text("INSERT INTO auth_sessions(auth_session_id,internal_user_pk,refresh_credential_hash,family_id,expires_at) VALUES('synthetic',7,'synthetic-digest','family','2099-01-01')"))
    with pytest.raises(Exception):
        migrations.rollback_auth_foundation(old_database)
    assert 'auth_sessions' in inspect(old_database).get_table_names()
    with old_database.begin() as connection:
        connection.execute(text('DELETE FROM auth_sessions'))
        connection.execute(text("INSERT INTO user_identities(internal_user_pk,public_user_id,auth_type,auth_epoch) VALUES(7,'synthetic:epoch','registered',1)"))
    with pytest.raises(Exception):
        migrations.rollback_auth_foundation(old_database)
    with old_database.begin() as connection:
        connection.execute(text('UPDATE user_identities SET auth_epoch=0'))
    migrations.rollback_auth_foundation(old_database)
    assert 'auth_sessions' not in inspect(old_database).get_table_names()
    assert 'auth_epoch' not in {c['name'] for c in inspect(old_database).get_columns('user_identities')}
    assert migrations.apply_v3_migrations(old_database)['applied_versions'] == [VERSION]


def test_mysql_create_all_renderer_omits_duplicate_nullable_additions():
    import backend.app.models  # noqa: F401
    from backend.app.core.database import Base
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    for version in ('0009_v3_five_tone_read_model','0010_v3_generation_prompt_audit'):
        sql = migrations._read_migration('mysql',version,'up')
        rendered = migrations._render_mysql_model_columns(engine,version,sql)
        assert 'ADD COLUMN' not in rendered
    engine.dispose()


def test_duplicate_ledger_rows_rejected_before_new_ddl(old_database):
    with old_database.begin() as connection:
        connection.execute(text('ALTER TABLE schema_migrations RENAME TO original_ledger'))
        connection.execute(text('CREATE TABLE schema_migrations AS SELECT * FROM original_ledger'))
        connection.execute(text('INSERT INTO schema_migrations SELECT * FROM original_ledger LIMIT 1'))
    with pytest.raises(migrations.MigrationOrderError):
        migrations.apply_v3_migrations(old_database)
    assert 'auth_sessions' not in inspect(old_database).get_table_names()


def test_failed_initialization_can_resume_without_deleting_create_all_schema(tmp_path, monkeypatch):
    from backend.app.core import database
    engine = create_engine(f'sqlite:///{tmp_path / "retry-init.sqlite"}')
    monkeypatch.setattr(database,'engine',engine)
    original = migrations._read_migration
    with monkeypatch.context() as context:
        def failed(dialect,version,direction,migrations_root=None):
            sql = original(dialect,version,direction,migrations_root)
            if version == VERSION and direction == 'up':
                sql += '\nINSERT INTO missing_table VALUES(1);\n'
            return sql
        context.setattr(migrations,'_read_migration',failed)
        with pytest.raises(Exception):
            database.init_database()
    # create_all is an earlier phase; do not pretend it rolled back too.
    assert 'auth_sessions' in inspect(engine).get_table_names()
    with engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM schema_migrations')).scalar_one() == 10
    database.init_database()
    with engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM schema_migrations')).scalar_one() == 11
    engine.dispose()


def test_refresh_hash_storage_rejects_empty_digest(old_database):
    migrations.apply_v3_migrations(old_database)
    with pytest.raises(IntegrityError):
        with old_database.begin() as connection:
            connection.execute(text("INSERT INTO auth_sessions(auth_session_id,internal_user_pk,refresh_credential_hash,family_id,expires_at) VALUES('empty',7,'','family','2099-01-01')"))
