"""Explicit opt-in draft schema tests; never use the configured application DB."""
import importlib
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[3]


def drafts():
    path = ROOT / 'backend/drafts/s7/models.py'
    assert path.exists(), 'INT-2 isolated models have not been implemented'
    return importlib.import_module('backend.drafts.s7.models')


def runner():
    drafts()
    return importlib.import_module('backend.drafts.s7.migrations')


def old_db():
    # Actual existing ORM schema, not a simplified imitation of its constraints.
    import backend.app.models  # noqa: F401
    from backend.app.core.database import Base
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO users(id,openid) VALUES(1,'synthetic:a'),(2,'synthetic:b')"))
    from backend.app.core.v3_migrations import apply_v3_migrations
    apply_v3_migrations(engine)
    raw = engine.raw_connection()
    connection = raw.driver_connection
    connection.execute('PRAGMA foreign_keys=ON')
    connection.execute("INSERT INTO music_assets(music_asset_id,source_type,title,storage_key,format,duration_seconds,checksum,playable_status) VALUES('shared','matched','Original','synthetic.wav','wav',131,'sha256:synthetic','ready')")
    connection.commit()
    return engine, raw, connection


@pytest.fixture
def database():
    engine, raw, connection = old_db()
    yield connection
    raw.close()
    engine.dispose()


def upgrade(connection):
    module = runner()
    for version in ('0012_library', '0013_consent'):
        module.apply_draft(connection, version)
    return module


def test_opt_in_models_do_not_pollute_production_metadata():
    import backend.app.models  # noqa: F401
    from backend.app.core.database import Base
    from backend.app.models.v3.feedback import FeedbackV3, UserMusicPreferenceVersion
    before = set(Base.metadata.tables)
    module = drafts()
    assert set(Base.metadata.tables) == before
    assert 'owner_music_state' not in before
    assert 'learning_consent' not in FeedbackV3.__table__.c
    assert 'evidence_epoch' not in UserMusicPreferenceVersion.__table__.c
    assert module.DraftBase.metadata is not Base.metadata
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    assert 'owner_music_state' not in inspect(engine).get_table_names()
    engine.dispose()


def test_fresh_draft_create_and_explicit_migrations():
    module = drafts()
    engine = create_engine('sqlite:///:memory:')
    module.DraftBase.metadata.create_all(engine)
    raw = engine.raw_connection()
    try:
        module_runner = runner()
        for version in ('0012_library', '0013_consent'):
            assert module_runner.apply_draft(raw.driver_connection, version)
        assert 'owner_music_state' in inspect(engine).get_table_names()
        assert 'learning_consent' in {c['name'] for c in inspect(engine).get_columns('feedback_v3')}
    finally:
        raw.close()
        engine.dispose()


def test_upgrade_defaults_and_history_unchanged(database):
    before = database.execute('SELECT title,checksum,duration_seconds FROM music_assets').fetchall()
    module = upgrade(database)
    database.execute('INSERT INTO owner_music_state(internal_user_pk) VALUES(1)')
    database.execute("INSERT INTO music_library_state(internal_user_pk,music_asset_id) VALUES(1,'shared')")
    assert database.execute('SELECT library_epoch,feedback_evidence_epoch,preference_clear_cutoff FROM owner_music_state').fetchone() == (0, 0, None)
    assert database.execute('SELECT metadata_version,last_played_at,user_title FROM music_library_state').fetchone() == (0, None, None)
    assert database.execute('SELECT title,checksum,duration_seconds FROM music_assets').fetchall() == before
    database.commit()
    assert not module.apply_draft(database, '0012_library')
    assert not module.apply_draft(database, '0013_consent')
    assert database.execute('SELECT count(*) FROM schema_migrations').fetchone()[0] == 10


@pytest.mark.parametrize('sql', [
    'INSERT INTO owner_music_state(internal_user_pk) VALUES(999)',
    'INSERT INTO owner_music_state(internal_user_pk,library_epoch) VALUES(1,-1)',
    "INSERT INTO music_library_state(internal_user_pk,music_asset_id,metadata_version) VALUES(1,'shared',-1)",
    "INSERT INTO music_library_state(internal_user_pk,music_asset_id) VALUES(1,'missing')",
    "INSERT INTO music_playback_events(internal_user_pk,event_id,music_asset_id,event_type) VALUES(1,'event','shared','paused')",
    "INSERT INTO music_playback_events(internal_user_pk,event_id,music_asset_id) VALUES(999,'event','shared')",
])
def test_database_rejects_invalid_shared_rows(database, sql):
    upgrade(database)
    with pytest.raises(sqlite3.IntegrityError):
        database.execute(sql)


def test_shared_asset_has_independent_owner_state_and_event_keys(database):
    upgrade(database)
    for owner in (1, 2):
        database.execute('INSERT INTO music_library_state(internal_user_pk,music_asset_id,user_title) VALUES(?,?,?)', (owner, 'shared', f'Private {owner}'))
        database.execute("INSERT INTO music_playback_events(internal_user_pk,event_id,music_asset_id) VALUES(?,'same-event','shared')", (owner,))
    assert database.execute('SELECT user_title FROM music_library_state WHERE internal_user_pk=1').fetchall() == [('Private 1',)]
    with pytest.raises(sqlite3.IntegrityError):
        database.execute("INSERT INTO music_library_state(internal_user_pk,music_asset_id) VALUES(1,'shared')")
    with pytest.raises(sqlite3.IntegrityError):
        database.execute("INSERT INTO music_playback_events(internal_user_pk,event_id,music_asset_id) VALUES(1,'same-event','shared')")


def test_orm_can_write_draft_tables_without_production_registration():
    module = drafts()
    engine = create_engine('sqlite:///:memory:')
    module.DraftBase.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO users(id,openid) VALUES(1,'synthetic:orm')"))
    with Session(engine) as session:
        session.add(module.OwnerMusicState(internal_user_pk=1))
        session.commit()
        state = session.get(module.OwnerMusicState, 1)
        assert (state.library_epoch, state.feedback_evidence_epoch) == (0, 0)
    engine.dispose()


def test_production_registration_remains_at_0010():
    from backend.app.core.v3_migrations import V3_MIGRATION_VERSIONS
    assert V3_MIGRATION_VERSIONS[-1] == '0010_v3_generation_prompt_audit'
    assert len(V3_MIGRATION_VERSIONS) == 10


def test_draft_checksum_mutation_is_rejected(database, tmp_path):
    module = runner()
    module.apply_draft(database, '0012_library')
    directory = tmp_path / 'sqlite'
    directory.mkdir()
    source = module.ROOT / 'sqlite/0012_library_up.sql'
    (directory / source.name).write_text(source.read_text() + '\n-- changed\n')
    with pytest.raises(module.DraftMigrationError, match='checksum'):
        module.apply_draft(database, '0012_library', root=tmp_path)


def test_failed_sql_rolls_back_ddl_and_ledger(database, tmp_path):
    module = runner()
    directory = tmp_path / 'sqlite'
    directory.mkdir()
    sql = (module.ROOT / 'sqlite/0012_library_up.sql').read_text()
    (directory / '0012_library_up.sql').write_text(sql + '\nINSERT INTO nonexistent_table VALUES(1);\n')
    with pytest.raises(sqlite3.OperationalError):
        module.apply_draft(database, '0012_library', root=tmp_path)
    assert not database.in_transaction
    assert database.execute("SELECT count(*) FROM sqlite_master WHERE name='owner_music_state'").fetchone()[0] == 0
    assert database.execute("SELECT count(*) FROM sqlite_master WHERE name='int2_draft_migrations'").fetchone()[0] == 0


def test_draft_down_is_reverse_order_and_refuses_data_loss(database):
    module = upgrade(database)
    with pytest.raises(module.DraftMigrationError, match='reverse'):
        module.rollback_draft(database, '0012_library')
    module.rollback_draft(database, '0013_consent')
    database.execute('INSERT INTO owner_music_state(internal_user_pk) VALUES(1)')
    database.commit()
    with pytest.raises(module.DraftMigrationError, match='nonempty'):
        module.rollback_draft(database, '0012_library')
    database.execute('DELETE FROM owner_music_state')
    database.commit()
    module.rollback_draft(database, '0012_library')
    assert database.execute("SELECT count(*) FROM sqlite_master WHERE name='owner_music_state'").fetchone()[0] == 0


@pytest.mark.parametrize('registered,applied', [
    (['0010_a','0011_auth','0012_library'], ['0010_a','0012_library']),
    (['0010_a','0012_library'], ['0010_a','0011_auth']),
    (['0012_library','0010_a'], []),
])
def test_future_order_guard_rejects_retroactive_insertion(registered, applied):
    module = runner()
    with pytest.raises(module.DraftMigrationError, match='order'):
        module.validate_migration_history(registered, applied)


def test_future_order_guard_accepts_only_applied_prefix():
    module = runner()
    module.validate_migration_history(['0010_a','0011_auth','0012_library'], ['0010_a','0011_auth'])


def test_mysql_draft_ddl_compiles_models_without_connecting():
    from sqlalchemy.dialects import mysql
    from sqlalchemy.schema import CreateTable
    module = drafts()
    for cls in (module.OwnerMusicState, module.MusicLibraryState, module.MusicPlaybackEvent):
        sql = str(CreateTable(cls.__table__).compile(dialect=mysql.dialect()))
        assert 'FOREIGN KEY' in sql
    for version in ('0012_library', '0013_consent'):
        for direction in ('up','down'):
            path = runner().ROOT / 'mysql' / f'{version}_{direction}.sql'
            assert path.exists() and path.stat().st_size > 100


def seed_history(connection):
    """Minimal synthetic but FK-valid chain; no provider or medical inference."""
    for owner in (1, 2):
        connection.execute('INSERT INTO sessions(id,user_id,session_id) VALUES(?,?,?)', (owner, owner, f's{owner}'))
        connection.execute("INSERT INTO assessment_v3(assessment_id,internal_user_pk,session_row_id,current_revision,status) VALUES(?,?,?,1,'confirmed')", (f'a{owner}',owner,owner))
        connection.execute("INSERT INTO assessment_revisions_v3(assessment_id,revision,status,confirmation_status,state_summary,organ_profile_json,evidence_coverage,source_diversity,conflicts_json,missing_information_json,degradation_json,presentation_json) VALUES(?,1,'confirmed','confirmed','synthetic','{}',0,0,'[]','[]','{}','{}')", (f'a{owner}',))
        connection.execute("INSERT INTO diagnosis_runs(diagnosis_id,internal_user_pk,session_row_id,assessment_id,assessment_revision,status,abstained,degradation_json,presentation_json) VALUES(?,?,?,?,1,'success',0,'{}','{}')", (f'd{owner}',owner,owner,f'a{owner}'))
        connection.execute("INSERT INTO prescription_v3(prescription_id,internal_user_pk,session_row_id,diagnosis_id,status,generation_spec_json,personalization_json,presentation_json) VALUES(?,?,?,?,'success','{}','{}','{}')", (f'p{owner}',owner,owner,f'd{owner}'))
        connection.execute("INSERT INTO generation_tasks(task_id,internal_user_pk,session_row_id,prescription_id,idempotency_key,status,progress_indeterminate,message_code,fallback_applied,music_asset_id) VALUES(?,?,?,?,?,'matched_fallback',0,'synthetic',1,'shared')", (f't{owner}',owner,owner,f'p{owner}',f'key{owner}'))
    connection.execute("INSERT INTO feedback_v3(feedback_id,internal_user_pk,session_row_id,music_asset_id,change_label,liked_features_json,adjustment_preferences_json,idempotency_key,preference_update_status) VALUES('f1',1,1,'shared','no_change','[]','[]','feedback-key','skipped')")
    connection.execute("INSERT INTO user_music_preferences(profile_id,internal_user_pk) VALUES('profile1',1)")
    connection.execute("INSERT INTO user_music_preference_versions(preference_version_id,profile_id,version,feedback_count,minimum_samples_for_application) VALUES('version1','profile1',1,0,1)")
    connection.commit()


def test_legacy_consent_and_snapshots_are_not_rewritten(database):
    seed_history(database)
    tables = ('users','sessions','music_assets','generation_tasks','diagnosis_runs','prescription_v3','feedback_v3','user_music_preference_versions')
    columns = {table: [r[1] for r in database.execute(f'PRAGMA table_info({table})')] for table in tables}
    before = {table: database.execute(f'SELECT {",".join(columns[table])} FROM {table}').fetchall() for table in tables}
    upgrade(database)
    for table in tables:
        assert database.execute(f'SELECT {",".join(columns[table])} FROM {table}').fetchall() == before[table]
    assert database.execute('SELECT learning_consent,consent_policy_version,consented_at,deleted_at,evidence_epoch,source_task_id FROM feedback_v3').fetchone() == (0,None,None,None,None,None)
    assert database.execute('SELECT evidence_epoch FROM user_music_preference_versions').fetchone() == (None,)
    with pytest.raises(sqlite3.IntegrityError):
        database.execute('UPDATE feedback_v3 SET learning_consent=1')


def test_playback_context_cannot_reference_other_owner(database):
    seed_history(database)
    upgrade(database)
    with pytest.raises(sqlite3.IntegrityError):
        database.execute("INSERT INTO music_playback_events(internal_user_pk,event_id,music_asset_id,origin_task_id) VALUES(1,'bad','shared','t2')")
    database.execute("INSERT INTO music_playback_events(internal_user_pk,event_id,music_asset_id,origin_task_id) VALUES(1,'good','shared','t1')")
    assert database.execute('PRAGMA foreign_key_check').fetchall() == []


def test_deleted_feedback_keeps_idempotency_and_blocks_downgrade(database):
    seed_history(database)
    module = upgrade(database)
    database.execute("UPDATE feedback_v3 SET deleted_at='2026-10-15 00:00:00'")
    database.commit()
    with pytest.raises(module.DraftMigrationError, match='nonempty'):
        module.rollback_draft(database,'0013_consent')
    with pytest.raises(sqlite3.IntegrityError):
        database.execute("INSERT INTO feedback_v3(feedback_id,internal_user_pk,session_row_id,music_asset_id,change_label,liked_features_json,adjustment_preferences_json,idempotency_key,preference_update_status) VALUES('new',1,1,'shared','no_change','[]','[]','feedback-key','skipped')")


def test_real_legacy_schema_upgrade_path(tmp_path):
    from tests.api.v3.test_v3_migrations import _create_legacy_foundation
    from backend.app.core.v3_migrations import apply_v3_migrations
    engine = create_engine(f'sqlite:///{tmp_path / "legacy.sqlite"}')
    _create_legacy_foundation(engine)
    apply_v3_migrations(engine)
    raw = engine.raw_connection()
    try:
        connection = raw.driver_connection
        before = connection.execute('SELECT * FROM sessions').fetchall()
        upgrade(connection)
        assert connection.execute('SELECT * FROM sessions').fetchall() == before
        assert connection.execute('PRAGMA foreign_key_check').fetchall() == []
    finally:
        raw.close()
        engine.dispose()


def test_successful_down_preserves_legacy_feedback(database):
    seed_history(database)
    before = database.execute('SELECT * FROM feedback_v3').fetchall()
    module = upgrade(database)
    module.rollback_draft(database,'0013_consent')
    module.rollback_draft(database,'0012_library')
    assert database.execute('SELECT * FROM feedback_v3').fetchall() == before


def test_out_of_order_draft_is_rejected_before_ddl(database):
    module = runner()
    with pytest.raises(module.DraftMigrationError, match='order'):
        module.apply_draft(database,'0013_consent')
    assert 'learning_consent' not in [r[1] for r in database.execute('PRAGMA table_info(feedback_v3)')]


def test_later_draft_checks_all_previously_applied_checksums(database, tmp_path):
    module = runner()
    module.apply_draft(database, '0012_library')
    directory = tmp_path / 'sqlite'
    directory.mkdir()
    for version in ('0012_library','0013_consent'):
        sql = (module.ROOT / 'sqlite' / f'{version}_up.sql').read_text()
        (directory / f'{version}_up.sql').write_text(sql + ('\n-- changed\n' if version == '0012_library' else ''))
    with pytest.raises(module.DraftMigrationError, match='checksum'):
        module.apply_draft(database,'0013_consent',root=tmp_path)
    assert 'learning_consent' not in [r[1] for r in database.execute('PRAGMA table_info(feedback_v3)')]


def test_down_refuses_tampered_ledger(database):
    module = upgrade(database)
    database.execute("UPDATE int2_draft_migrations SET checksum='sha256:tampered' WHERE version='0013_consent'")
    database.commit()
    with pytest.raises(module.DraftMigrationError, match='checksum'):
        module.rollback_draft(database,'0013_consent')
    assert 'learning_consent' in [r[1] for r in database.execute('PRAGMA table_info(feedback_v3)')]


def test_synthetic_contract_fixture_can_be_inserted(database):
    import json
    fixture = json.loads((Path(__file__).parent / 'fixtures/int2_shared_fields.json').read_text())
    upgrade(database)
    for table in ('owner_music_state','music_library_state','music_playback_events'):
        values = fixture[table]
        columns = ','.join(values)
        placeholders = ','.join('?' for _ in values)
        database.execute(f'INSERT INTO {table}({columns}) VALUES({placeholders})',list(values.values()))
    assert database.execute('SELECT metadata_version,last_played_at FROM music_library_state').fetchone() == (0,None)
    assert database.execute('PRAGMA foreign_key_check').fetchall() == []


def test_future_guard_uses_actual_0010_ledger(database):
    module = runner()
    from backend.app.core.v3_migrations import V3_MIGRATION_VERSIONS
    applied = [r[0] for r in database.execute('SELECT version FROM schema_migrations ORDER BY version')]
    module.validate_migration_history(V3_MIGRATION_VERSIONS + ['0011_auth','0012_library'],applied)
    with pytest.raises(module.DraftMigrationError,match='order'):
        module.validate_migration_history(V3_MIGRATION_VERSIONS + ['0011_auth','0012_library'],applied + ['0012_library'])
