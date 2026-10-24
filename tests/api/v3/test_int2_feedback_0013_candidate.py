"""Explicit review-only migration; real file SQLite, no live dependencies."""
import importlib
import pytest
from sqlalchemy import create_engine,text,inspect
from sqlalchemy.exc import IntegrityError
from backend.app.core import v3_migrations as core
from tests.api.v3.test_v3_migrations import _create_legacy_foundation
from tests.api.v3.test_int2_0012_contract import seed


def candidate():return importlib.import_module('backend.drafts.s7_feedback_consent.migration')


@pytest.fixture
def database(tmp_path):
    engine=create_engine(f'sqlite:///{tmp_path / "feedback.sqlite"}',connect_args={'check_same_thread':False})
    _create_legacy_foundation(engine)
    core.apply_v3_migrations(engine)
    with engine.begin() as db:
        seed(db)
        db.execute(text("INSERT INTO feedback_v3(feedback_id,internal_user_pk,session_row_id,music_asset_id,change_label,liked_features_json,adjustment_preferences_json,idempotency_key,preference_update_status) VALUES('old-feedback',7,1,'music_shared','no_change','[]','[]','old-key','skipped')"))
        db.execute(text("INSERT INTO user_music_preferences(profile_id,internal_user_pk,current_version_id) VALUES('profile',7,'old-version')"))
        db.execute(text("INSERT INTO user_music_preference_versions(preference_version_id,profile_id,version) VALUES('old-version','profile',1)"))
    yield engine
    engine.dispose()


def snapshot(engine):
    with engine.connect() as db:
        names=[r[0] for r in db.exec_driver_sql("SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {n:db.exec_driver_sql(f'SELECT * FROM "{n}" ORDER BY 1').fetchall() for n in names}


def test_upgrade_defaults_and_history_unchanged(database):
    before=snapshot(database)
    assert candidate().install_sqlite(database)=='installed'
    with database.connect() as db:
        assert db.exec_driver_sql('SELECT learning_consent,consent_policy_version,consented_at,deleted_at,source_task_id,playback_event_row_id,evidence_epoch,request_fingerprint FROM feedback_v3').one()==(0,None,None,None,None,None,None,None)
        assert db.exec_driver_sql('SELECT evidence_epoch FROM user_music_preference_versions').scalar() is None
        assert db.exec_driver_sql('PRAGMA foreign_key_check').fetchall()==[]
    after=snapshot(database)
    for table,rows in before.items():
        if table in ('feedback_v3','user_music_preference_versions'):
            assert [tuple(r[:len(rows[0])]) for r in after[table]]==[tuple(r) for r in rows]
        else:assert after[table]==rows
    assert candidate().install_sqlite(database)=='already_installed'


@pytest.mark.parametrize('patch',["learning_consent=1","learning_consent=NULL","learning_consent=2",
    "consent_policy_version='invented'","consented_at='2026-10-19'","evidence_epoch=-1"])
def test_illegal_consent_and_epoch_fail_without_changing_legacy(database,patch):
    candidate().install_sqlite(database)
    before=snapshot(database)
    with pytest.raises(IntegrityError):
        with database.begin() as db:db.exec_driver_sql('UPDATE feedback_v3 SET '+patch)
    assert snapshot(database)==before


def test_tombstone_preserves_key_and_refuses_resurrection(database):
    candidate().install_sqlite(database)
    with database.begin() as db:db.exec_driver_sql("UPDATE feedback_v3 SET deleted_at=CURRENT_TIMESTAMP WHERE feedback_id='old-feedback'")
    before=snapshot(database)
    for sql in ["UPDATE feedback_v3 SET deleted_at=NULL","DELETE FROM feedback_v3",
                "UPDATE feedback_v3 SET idempotency_key='replacement'"]:
        with pytest.raises(IntegrityError):
            with database.begin() as db:db.exec_driver_sql(sql)
        assert snapshot(database)==before
    with pytest.raises(IntegrityError):
        with database.begin() as db:
            db.exec_driver_sql("INSERT INTO feedback_v3(feedback_id,internal_user_pk,session_row_id,music_asset_id,change_label,liked_features_json,adjustment_preferences_json,idempotency_key,preference_update_status) VALUES('replacement',7,1,'music_shared','no_change','[]','[]','old-key','skipped')")


def test_empty_extension_safe_down_restores_original_rows(database):
    before=snapshot(database)
    candidate().install_sqlite(database)
    assert candidate().remove_sqlite(database)=='removed'
    assert snapshot(database)==before


@pytest.mark.parametrize('external',["CREATE VIEW review_view AS SELECT source_task_id FROM feedback_v3",
    "CREATE TABLE external_ref(k INTEGER REFERENCES feedback_v3(evidence_epoch))"])
def test_down_refuses_external_objects_without_partial_ddl(database,external):
    candidate().install_sqlite(database)
    with database.begin() as db:db.exec_driver_sql(external)
    before=snapshot(database)
    with pytest.raises(candidate().CandidateRejected):candidate().remove_sqlite(database)
    assert snapshot(database)==before
    assert 'learning_consent' in {c['name'] for c in inspect(database).get_columns('feedback_v3')}


def test_production_registry_and_models_do_not_discover_candidate(database):
    assert core.V3_MIGRATION_VERSIONS[-1]=='0012_v3_music_library'
    from backend.app.models.v3.feedback import FeedbackV3
    assert 'learning_consent' not in FeedbackV3.__table__.c
    assert 'learning_consent' not in {c['name'] for c in inspect(database).get_columns('feedback_v3')}


def test_candidate_orm_and_mysql_fk_contract_are_explicit_not_auto_create(database):
    from sqlalchemy.schema import CreateTable
    from sqlalchemy.dialects import mysql
    model=importlib.import_module('backend.drafts.s7_feedback_consent.models')
    candidate().install_sqlite(database)
    assert set(model.table.c.keys())=={c['name'] for c in inspect(database).get_columns('feedback_v3')}
    assert model.table.c.learning_consent.nullable is False
    assert str(model.table.c.learning_consent.server_default.arg)=='0'
    with pytest.raises(RuntimeError):model.metadata.create_all(database)
    rendered=str(CreateTable(model.table).compile(dialect=mysql.dialect()))
    assert 'FOREIGN KEY(source_task_id, internal_user_pk, music_asset_id)' in rendered
    assert 'FOREIGN KEY(playback_event_row_id, internal_user_pk, music_asset_id, source_task_id)' in rendered
    assert 'DATETIME(6)' in rendered


def test_upgrade_failure_rolls_back_every_column_and_history(database,monkeypatch):
    before=snapshot(database)
    original=core._execute_sqlite_statements
    def fail(cursor,sql):
        original(cursor,sql)
        raise RuntimeError('injected failure after real DDL')
    monkeypatch.setattr(core,'_execute_sqlite_statements',fail)
    with pytest.raises(RuntimeError):candidate().install_sqlite(database)
    assert snapshot(database)==before
    assert 'learning_consent' not in {c['name'] for c in inspect(database).get_columns('feedback_v3')}


def test_fresh_create_and_upgrade_have_equivalent_candidate_fields(database,tmp_path,monkeypatch):
    from backend.app.core import database as application_db
    fresh=create_engine(f'sqlite:///{tmp_path / "fresh.sqlite"}')
    monkeypatch.setattr(application_db,'engine',fresh)
    application_db.init_database()
    candidate().install_sqlite(fresh)
    candidate().install_sqlite(database)
    def fields(engine):return [(c['name'],str(c['type']),c['nullable'],c['default']) for c in inspect(engine).get_columns('feedback_v3') if c['name'] in candidate().FIELDS]
    assert fields(fresh)==fields(database)
    assert candidate().install_sqlite(fresh)=='already_installed'
    fresh.dispose()


def test_partial_schema_and_bad_history_reject_before_any_new_ddl(database):
    with database.begin() as db:db.exec_driver_sql('ALTER TABLE feedback_v3 ADD COLUMN learning_consent INTEGER DEFAULT 0')
    before=snapshot(database)
    with pytest.raises(candidate().CandidateRejected):candidate().install_sqlite(database)
    assert snapshot(database)==before
    with database.begin() as db:db.exec_driver_sql("UPDATE schema_migrations SET checksum='bad' WHERE version='0012_v3_music_library'")
    before=snapshot(database)
    with pytest.raises(core.MigrationChecksumMismatch):candidate().install_sqlite(database)
    assert snapshot(database)==before


def test_duplicate_registration_is_rejected_without_changing_database(database,monkeypatch):
    before=snapshot(database)
    monkeypatch.setattr(core,'V3_MIGRATION_VERSIONS',core.V3_MIGRATION_VERSIONS+['0012_v3_music_library'])
    with pytest.raises(core.MigrationOrderError):candidate().install_sqlite(database)
    assert snapshot(database)==before


def test_changed_candidate_checksum_cannot_be_reapplied(database,monkeypatch):
    c=candidate();c.install_sqlite(database)
    before=snapshot(database)
    monkeypatch.setattr(c,'_checksum',lambda:'sha256:changed-review-source')
    with pytest.raises(c.CandidateRejected):c.install_sqlite(database)
    assert snapshot(database)==before


@pytest.mark.parametrize('context,event_context,consent,allowed',[
    ('ctx_a','ctx_a',1,True),('ctx_a','ctx_b',1,False),
    ('ctx_other','ctx_a',1,False),('ctx_a',None,1,False)])
def test_persisted_proof_enforces_same_owner_asset_task_event(database,context,event_context,consent,allowed):
    candidate().install_sqlite(database)
    with database.begin() as db:
        db.execute(text("INSERT INTO music_playback_events(internal_user_pk,event_id,music_asset_id,event_type,source_context_id,occurred_at) VALUES(7,'specific','music_shared','play_started',:c,CURRENT_TIMESTAMP)"),{'c':event_context})
        rowid=db.exec_driver_sql('SELECT playback_event_row_id FROM music_playback_events').scalar()
    before=snapshot(database)
    def insert():
        with database.begin() as db:
            db.execute(text("INSERT INTO feedback_v3(feedback_id,internal_user_pk,session_row_id,music_asset_id,change_label,liked_features_json,adjustment_preferences_json,idempotency_key,preference_update_status,learning_consent,consent_policy_version,consented_at,evidence_epoch,request_fingerprint,source_task_id,playback_event_row_id) VALUES('consented',7,1,'music_shared','no_change','[]','[]','specific-key','skipped',:yes,'synthetic-policy',CURRENT_TIMESTAMP,0,:fp,:context,:event)"),{'yes':consent,'fp':'sha256:'+'a'*64,'context':context,'event':rowid})
    if allowed:
        insert()
        with pytest.raises(candidate().CandidateRejected):candidate().remove_sqlite(database)
        with pytest.raises(IntegrityError):
            with database.begin() as db:db.exec_driver_sql("UPDATE music_playback_events SET source_context_id='ctx_b'")
    else:
        with pytest.raises(IntegrityError):insert()
        assert snapshot(database)==before


def test_down_error_after_first_drop_rolls_back_objects_and_columns(database,monkeypatch):
    c=candidate();c.install_sqlite(database)
    before=snapshot(database)
    original=database.raw_connection
    class Cursor:
        def __init__(self,real):self.real=real
        def execute(self,sql,*args):
            if sql.startswith('DROP INDEX'):raise RuntimeError('injected down DDL failure after trigger drops')
            return self.real.execute(sql,*args)
        def __getattr__(self,name):return getattr(self.real,name)
    class Connection:
        def __init__(self,real):self.real=real
        def cursor(self):return Cursor(self.real.cursor())
        def __getattr__(self,name):return getattr(self.real,name)
    with monkeypatch.context() as context:
        context.setattr(database,'raw_connection',lambda:Connection(original()))
        with pytest.raises(RuntimeError):c.remove_sqlite(database)
    assert snapshot(database)==before
    assert c.install_sqlite(database)=='already_installed'  # exact trigger/schema signature restored


def test_same_column_names_without_legacy_constraints_are_not_accepted(database):
    with database.begin() as db:
        db.exec_driver_sql('ALTER TABLE feedback_v3 RENAME TO preserved_old_feedback')
        db.exec_driver_sql('CREATE TABLE feedback_v3 AS SELECT * FROM preserved_old_feedback')
    before=snapshot(database)
    with pytest.raises(candidate().CandidateRejected):candidate().install_sqlite(database)
    assert snapshot(database)==before


@pytest.mark.parametrize('learning,policy',[ (None,None),(2,None),(1,None),(0,'invented-policy') ])
def test_insert_checks_reject_bad_consent_not_only_update_guard(database,learning,policy):
    candidate().install_sqlite(database)
    before=snapshot(database)
    with pytest.raises(IntegrityError):
        with database.begin() as db:
            db.execute(text("INSERT INTO feedback_v3(feedback_id,internal_user_pk,session_row_id,music_asset_id,change_label,liked_features_json,adjustment_preferences_json,idempotency_key,preference_update_status,learning_consent,consent_policy_version) VALUES('bad-new',7,1,'music_shared','no_change','[]','[]','bad-new','skipped',:c,:p)"),{'c':learning,'p':policy})
    assert snapshot(database)==before


@pytest.mark.parametrize('flaw',['type','default','version_fk','null_pk'])
def test_incompatible_constrained_legacy_schema_is_refused_before_ddl(database,flaw):
    from sqlalchemy.schema import CreateTable
    from backend.app.models.v3.feedback import FeedbackV3,UserMusicPreferenceVersion
    table=UserMusicPreferenceVersion.__table__ if flaw=='version_fk' else FeedbackV3.__table__
    sql=str(CreateTable(table).compile(database))
    if flaw=='type':sql=sql.replace('internal_user_pk INTEGER','internal_user_pk VARCHAR(64)')
    if flaw=='default':sql=sql.replace('idempotency_key VARCHAR(128) NOT NULL',"idempotency_key VARCHAR(128) DEFAULT 'invented' NOT NULL")
    if flaw=='version_fk':
        sql=sql.replace(', \n\tFOREIGN KEY(profile_id) REFERENCES user_music_preferences (profile_id) ON DELETE CASCADE','')
    if flaw=='null_pk':
        with database.begin() as db:db.exec_driver_sql("UPDATE feedback_v3 SET feedback_id=NULL")
    else:
        with database.begin() as db:
            db.exec_driver_sql(f'CREATE TEMP TABLE preserved AS SELECT * FROM {table.name}')
            db.exec_driver_sql(f'DROP TABLE {table.name}')
            db.exec_driver_sql(sql)
            db.exec_driver_sql(f'INSERT INTO {table.name} SELECT * FROM preserved')
    before=snapshot(database)
    with pytest.raises(candidate().CandidateRejected):candidate().install_sqlite(database)
    assert snapshot(database)==before
    assert 'learning_consent' not in {c['name'] for c in inspect(database).get_columns('feedback_v3')}


def test_nullable_historical_text_primary_key_cannot_accept_new_null_after_install(database):
    candidate().install_sqlite(database)
    with pytest.raises(IntegrityError):
        with database.begin() as db:
            db.exec_driver_sql("INSERT INTO feedback_v3(feedback_id,internal_user_pk,session_row_id,music_asset_id,change_label,liked_features_json,adjustment_preferences_json,idempotency_key,preference_update_status) VALUES(NULL,7,1,'music_shared','no_change','[]','[]','null-key','skipped')")


@pytest.fixture
def fingerprinted_feedback(database):
    candidate().install_sqlite(database)
    with database.begin() as db:
        db.exec_driver_sql("INSERT INTO music_playback_events(internal_user_pk,event_id,music_asset_id,event_type,source_context_id,occurred_at) VALUES(7,'r1-event','music_shared','play_started','ctx_a',CURRENT_TIMESTAMP)")
        rowid=db.exec_driver_sql("SELECT playback_event_row_id FROM music_playback_events WHERE event_id='r1-event'").scalar_one()
        db.execute(text("""INSERT INTO feedback_v3(feedback_id,internal_user_pk,session_row_id,music_asset_id,
            change_label,pre_state_snapshot_json,post_state_json,experience_json,continue_use,
            liked_features_json,adjustment_preferences_json,comment_ciphertext,playback_json,
            idempotency_key,preference_update_status,source_task_id,playback_event_row_id,evidence_epoch,
            learning_consent,consent_policy_version,consented_at,request_fingerprint)
            VALUES('r1-feedback',7,1,'music_shared','no_change','{"snapshot_id":"synthetic"}',
            '{"change_label":"no_change"}',:experience,'maybe','["calm"]','[]',NULL,
            :playback,'r1-key','pending','ctx_a',:event,0,
            1,'synthetic-policy',CURRENT_TIMESTAMP,:fingerprint)"""),
            {'event':rowid,'fingerprint':'sha256:'+'b'*64,
             'experience':'{"overall_rating":3}','playback':'{"played_seconds":3,"completed":false}'})
    return database


@pytest.mark.parametrize('patch',[
    "change_label='worse'", "pre_state_snapshot_json='{}'", "post_state_json='{}'",
    "experience_json='{}'", "continue_use='no'", "liked_features_json='[\"different\"]'",
    "adjustment_preferences_json='[\"slower_tempo\"]'", "comment_ciphertext='new-hash'",
    "playback_json='{}'", "created_at='2000-01-01 00:00:00'",
    'pre_state_snapshot_json=NULL','post_state_json=NULL','experience_json=NULL',
    'continue_use=NULL','playback_json=NULL',"comment_ciphertext='null'",
    "liked_features_json='[ \"calm\" ]'"
])
def test_r1_fingerprinted_business_content_cannot_drift(fingerprinted_feedback,patch):
    before=snapshot(fingerprinted_feedback)
    with pytest.raises(IntegrityError):
        with fingerprinted_feedback.begin() as db:
            db.exec_driver_sql("UPDATE feedback_v3 SET "+patch+" WHERE feedback_id='r1-feedback'")
    assert snapshot(fingerprinted_feedback)==before


@pytest.mark.parametrize('fingerprint',[True,False])
def test_r1_same_value_updates_and_legacy_processing_status_remain_legal(fingerprinted_feedback,fingerprint):
    target='r1-feedback' if fingerprint else 'old-feedback'
    with fingerprinted_feedback.begin() as db:
        db.execute(text("UPDATE feedback_v3 SET change_label=change_label,pre_state_snapshot_json=pre_state_snapshot_json,post_state_json=post_state_json,experience_json=experience_json,continue_use=continue_use,liked_features_json=liked_features_json,adjustment_preferences_json=adjustment_preferences_json,comment_ciphertext=comment_ciphertext,playback_json=playback_json,created_at=created_at WHERE feedback_id=:id"),{'id':target})
    from sqlalchemy.orm import Session
    from backend.app.services.v3.feedback_service import _set_status
    for status in ('failed','skipped'):
        with Session(fingerprinted_feedback,autoflush=False) as db:
            _set_status(db,target,status)
            db.commit()
        with fingerprinted_feedback.connect() as db:
            assert db.execute(text('SELECT preference_update_status FROM feedback_v3 WHERE feedback_id=:id'),{'id':target}).scalar_one()==status


@pytest.mark.parametrize('verb',['replace','upsert','tombstone'])
def test_r1_sql_conflicts_and_tombstone_do_not_allow_payload_replacement(fingerprinted_feedback,verb):
    if verb=='tombstone':
        with fingerprinted_feedback.begin() as db:
            db.exec_driver_sql("UPDATE feedback_v3 SET deleted_at=CURRENT_TIMESTAMP WHERE feedback_id='r1-feedback'")
    before=snapshot(fingerprinted_feedback)
    with pytest.raises(IntegrityError):
        with fingerprinted_feedback.begin() as db:
            if verb=='tombstone':sql="UPDATE feedback_v3 SET change_label='worse' WHERE feedback_id='r1-feedback'"
            else:
                sql="INSERT "+('OR REPLACE ' if verb=='replace' else '')+"INTO feedback_v3 SELECT * FROM feedback_v3 WHERE feedback_id='r1-feedback'"
                if verb=='upsert':sql+=" ON CONFLICT(internal_user_pk,idempotency_key) DO UPDATE SET change_label='worse'"
            db.exec_driver_sql(sql)
    assert snapshot(fingerprinted_feedback)==before


def test_r1_unconsented_fingerprinted_row_and_null_payload_are_also_immutable(fingerprinted_feedback):
    with fingerprinted_feedback.begin() as db:
        row=dict(db.exec_driver_sql("SELECT * FROM feedback_v3 WHERE feedback_id='r1-feedback'").mappings().one())
        row.update(feedback_id='false-consent',idempotency_key='false-key',learning_consent=0,
            consent_policy_version=None,consented_at=None,experience_json=None,playback_json=None)
        columns=','.join(row)
        db.execute(text(f"INSERT INTO feedback_v3({columns}) VALUES({','.join(':'+c for c in row)})"),row)
    for patch in ("change_label='worse'","experience_json='{}'","playback_json='null'"):
        before=snapshot(fingerprinted_feedback)
        with pytest.raises(IntegrityError):
            with fingerprinted_feedback.begin() as db:
                db.exec_driver_sql("UPDATE feedback_v3 SET "+patch+" WHERE feedback_id='false-consent'")
        assert snapshot(fingerprinted_feedback)==before
