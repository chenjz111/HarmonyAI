"""Formal registry/startup contract against isolated SQLite files."""
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from backend.app.core import v3_migrations as core
from tests.api.v3.test_v3_migrations import _create_legacy_foundation
from tests.api.v3.test_int2_0012_contract import seed

VERSION = '0013_v3_feedback_consent'
FIELDS = {'learning_consent', 'consent_policy_version', 'consented_at', 'deleted_at',
          'source_task_id', 'playback_event_row_id', 'evidence_epoch', 'request_fingerprint'}


@pytest.fixture(autouse=True)
def historical0013_registry(monkeypatch):
    monkeypatch.setattr(core,'V3_MIGRATION_VERSIONS',core.V3_MIGRATION_VERSIONS[:13])


@pytest.fixture
def legacy(tmp_path, monkeypatch):
    engine = create_engine(f'sqlite:///{tmp_path / "feedback.sqlite"}')
    _create_legacy_foundation(engine)
    with monkeypatch.context() as patch:
        patch.setattr(core, 'V3_MIGRATION_VERSIONS', core.V3_MIGRATION_VERSIONS[:12])
        core.apply_v3_migrations(engine)
    with engine.begin() as db:
        seed(db)
        db.exec_driver_sql("INSERT INTO feedback_v3(feedback_id,internal_user_pk,session_row_id,"
                           "music_asset_id,change_label,liked_features_json,adjustment_preferences_json,"
                           "idempotency_key,preference_update_status) VALUES"
                           "('old',7,1,'music_shared','no_change','[]','[]','old-key','skipped')")
    yield engine
    engine.dispose()


def schema(engine):
    with engine.connect() as db:
        return db.exec_driver_sql('SELECT type,name,sql FROM sqlite_schema ORDER BY type,name').fetchall()


def test_formal_upgrade_defaults_no_backfill_repeat_and_production_orm(legacy):
    with legacy.connect() as db:
        prefix = db.exec_driver_sql('SELECT version,checksum FROM schema_migrations ORDER BY version').fetchall()
    assert core.apply_v3_migrations(legacy)['applied_versions'] == [VERSION]
    assert core.apply_v3_migrations(legacy)['applied_versions'] == []
    from backend.app.models.v3 import FeedbackV3, UserMusicPreferenceVersion
    assert FIELDS <= set(FeedbackV3.__table__.c.keys())
    assert 'evidence_epoch' in UserMusicPreferenceVersion.__table__.c
    with legacy.connect() as db:
        assert db.exec_driver_sql('SELECT version,checksum FROM schema_migrations ORDER BY version').fetchall()[:12] == prefix
        assert db.exec_driver_sql('SELECT learning_consent,consent_policy_version,consented_at,deleted_at,source_task_id,playback_event_row_id,evidence_epoch,request_fingerprint FROM feedback_v3').one() == (0, None, None, None, None, None, None, None)
        assert db.exec_driver_sql('PRAGMA foreign_key_check').fetchall() == []


def test_fresh_init_repeat_and_trigger_revalidation(tmp_path, monkeypatch):
    from backend.app import models  # noqa: F401
    from backend.app.core import database
    engine = create_engine(f'sqlite:///{tmp_path / "fresh.sqlite"}')
    monkeypatch.setattr(database, 'engine', engine)
    database.init_database()
    database.init_database()
    assert FIELDS <= {c['name'] for c in inspect(engine).get_columns('feedback_v3')}
    with engine.begin() as db:
        assert db.exec_driver_sql('SELECT count(*) FROM schema_migrations').scalar_one() == 13
        db.exec_driver_sql('DROP TRIGGER int2_0013_feedback_immutable')
    before = schema(engine)
    with pytest.raises(core.MigrationSchemaMismatch):
        database.init_database()
    assert schema(engine) == before
    engine.dispose()


def test_partial_schema_refused_without_new_ddl_or_ledger(legacy):
    with legacy.begin() as db:
        db.exec_driver_sql('ALTER TABLE feedback_v3 ADD COLUMN learning_consent INTEGER DEFAULT 0')
    before = schema(legacy)
    with pytest.raises(core.MigrationSchemaMismatch):
        core.apply_v3_migrations(legacy)
    assert schema(legacy) == before


def test_install_failure_rolls_back_and_retry_recovers(legacy, monkeypatch):
    before = schema(legacy)
    original = core._execute_sqlite_statements
    def fail_after_ddl(cursor, sql):
        if 'int2_0013_feedback_immutable' in sql:
            cursor.execute('ALTER TABLE feedback_v3 ADD COLUMN synthetic_partial INTEGER')
            raise RuntimeError('synthetic interrupted install')
        return original(cursor, sql)
    with monkeypatch.context() as patch:
        patch.setattr(core, '_execute_sqlite_statements', fail_after_ddl)
        with pytest.raises(RuntimeError, match='synthetic interrupted install'):
            core.apply_v3_migrations(legacy)
    assert schema(legacy) == before
    assert core.apply_v3_migrations(legacy)['applied_versions'] == [VERSION]


@pytest.mark.parametrize('patch', ["change_label='worse'", "playback_json='{}'",
                                    "request_fingerprint=NULL", "learning_consent=1"])
def test_fingerprinted_payload_and_authorization_are_immutable(legacy, patch):
    core.apply_v3_migrations(legacy)
    with legacy.begin() as db:
        db.exec_driver_sql("INSERT INTO feedback_v3(feedback_id,internal_user_pk,session_row_id,music_asset_id,change_label,liked_features_json,adjustment_preferences_json,idempotency_key,preference_update_status,request_fingerprint) VALUES('new',7,1,'music_shared','no_change','[]','[]','new-key','skipped','sha256:" + 'b'*64 + "')")
    with pytest.raises(IntegrityError):
        with legacy.begin() as db:
            db.exec_driver_sql('UPDATE feedback_v3 SET '+patch+" WHERE feedback_id='new'")


def test_tombstone_cannot_resurrect_or_release_idempotency_key(legacy):
    core.apply_v3_migrations(legacy)
    with legacy.begin() as db:
        db.exec_driver_sql("UPDATE feedback_v3 SET deleted_at=CURRENT_TIMESTAMP WHERE feedback_id='old'")
    for sql in ("UPDATE feedback_v3 SET deleted_at=NULL WHERE feedback_id='old'",
                "DELETE FROM feedback_v3 WHERE feedback_id='old'",
                "INSERT OR REPLACE INTO feedback_v3 SELECT * FROM feedback_v3 WHERE feedback_id='old'"):
        with pytest.raises(IntegrityError):
            with legacy.begin() as db:
                db.exec_driver_sql(sql)


def test_safe_downgrade_refuses_evidence_then_restores_0012(legacy):
    core.apply_v3_migrations(legacy)
    core.rollback_feedback_consent(legacy)
    assert not FIELDS.intersection(c['name'] for c in inspect(legacy).get_columns('feedback_v3'))
    assert core.apply_v3_migrations(legacy)['applied_versions'] == [VERSION]
    with legacy.begin() as db:
        db.exec_driver_sql("UPDATE feedback_v3 SET deleted_at=CURRENT_TIMESTAMP WHERE feedback_id='old'")
    before = schema(legacy)
    with pytest.raises(core.MigrationSchemaMismatch):
        core.rollback_feedback_consent(legacy)
    assert schema(legacy) == before


def test_paired_mysql_script_executes_compound_statements_as_inventory():
    root = Path(core.__file__).parents[2] / 'migrations/v3'
    for dialect in ('sqlite', 'mysql'):
        for direction in ('up', 'down'):
            assert (root/dialect/f'{VERSION}_{direction}.sql').is_file()
    sql = (root/'mysql'/f'{VERSION}_up.sql').read_text(encoding='utf-8')
    statements = core._mysql_migration_statements(sql)
    assert sum(statement.startswith('CREATE TRIGGER') for statement in statements) == 8
    assert not any(statement.startswith(('END', 'IF', 'THEN')) for statement in statements)


def test_fresh_table_checks_refuse_downgrade_before_destructive_ddl(tmp_path, monkeypatch):
    from backend.app.core import database
    from sqlalchemy import event
    engine = create_engine(f'sqlite:///{tmp_path / "fresh-down.sqlite"}')
    monkeypatch.setattr(database, 'engine', engine)
    database.init_database()
    seen = []
    def trace(connection, cursor, statement, parameters, context, executemany):
        seen.append(statement.lstrip().upper())
    event.listen(engine, 'before_cursor_execute', trace)
    before = schema(engine)
    with pytest.raises(core.MigrationSchemaMismatch):
        core.rollback_feedback_consent(engine)
    assert schema(engine) == before
    assert not any(s.startswith(('DROP ', 'ALTER ')) for s in seen)
    engine.dispose()


def test_upgrade_rejects_legacy_fk_violations_before_ddl(legacy):
    with legacy.connect() as db:
        db.exec_driver_sql('PRAGMA foreign_keys=OFF')
        db.exec_driver_sql("UPDATE feedback_v3 SET music_asset_id='missing'")
        db.commit()
        db.exec_driver_sql('PRAGMA foreign_keys=ON')
    before = schema(legacy)
    with pytest.raises(core.MigrationSchemaMismatch):
        core.apply_v3_migrations(legacy)
    assert schema(legacy) == before
