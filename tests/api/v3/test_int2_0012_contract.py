"""Actual SQLite migration + Backend API against one unified model contract."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.core import v3_migrations as migrations
from tests.api.v3.test_v3_migrations import _create_legacy_foundation

VERSION = '0012_v3_music_library'
FIXTURES = Path(__file__).parent / 'fixtures'

@pytest.fixture(autouse=True)
def historical_0012_registry(monkeypatch):
    """Keep historical 0012 downgrade/recovery assertions; 0013 has its own suite."""
    monkeypatch.setattr(migrations, 'V3_MIGRATION_VERSIONS', migrations.V3_MIGRATION_VERSIONS[:12])



@pytest.fixture
def upgraded(tmp_path,monkeypatch):
    engine = create_engine(f'sqlite:///{tmp_path / "library.sqlite"}',connect_args={'check_same_thread':False})
    _create_legacy_foundation(engine)
    with monkeypatch.context() as context:
        context.setattr(migrations,'V3_MIGRATION_VERSIONS',migrations.V3_MIGRATION_VERSIONS[:10])
        migrations.apply_v3_migrations(engine)
    yield engine
    engine.dispose()


def seed(connection):
    connection.execute(text("INSERT INTO music_assets(music_asset_id,owner_internal_user_pk,source_type,title,storage_key,format,duration_seconds,checksum,playable_status,created_at,updated_at) VALUES('music_shared',NULL,'matched','Original','music_shared.mp3','mp3',240,'sha256:synthetic','ready','2026-10-12 08:00:00','2026-10-12 08:00:00')"))
    for task_id,owner in [('ctx_a',7),('ctx_b',7),('ctx_other',1)]:
        if owner==1:
            connection.execute(text("INSERT INTO sessions(id,user_id,session_id) VALUES(2,1,'synthetic-other')"))
        session_id = 1 if owner==7 else 2
        connection.execute(text("INSERT INTO assessment_v3(assessment_id,internal_user_pk,session_row_id,current_revision,status) VALUES(:id,:owner,:session,1,'confirmed')"),{'id':'a_'+task_id,'owner':owner,'session':session_id})
        connection.execute(text("INSERT INTO assessment_revisions_v3(assessment_id,revision,status,confirmation_status,state_summary,organ_profile_json,evidence_coverage,source_diversity,conflicts_json,missing_information_json,degradation_json,presentation_json) VALUES(:id,1,'confirmed','confirmed','synthetic','{}',0,0,'[]','[]','{}','{}')"),{'id':'a_'+task_id})
        connection.execute(text("INSERT INTO diagnosis_runs(diagnosis_id,internal_user_pk,session_row_id,assessment_id,assessment_revision,status,abstained,degradation_json,presentation_json) VALUES(:id,:owner,:session,:a,1,'success',0,'{}','{}')"),{'id':'d_'+task_id,'owner':owner,'session':session_id,'a':'a_'+task_id})
        connection.execute(text("INSERT INTO prescription_v3(prescription_id,internal_user_pk,session_row_id,diagnosis_id,status,generation_spec_json,personalization_json,presentation_json) VALUES(:id,:owner,:session,:d,'success','{}','{}','{}')"),{'id':'p_'+task_id,'owner':owner,'session':session_id,'d':'d_'+task_id})
        connection.execute(text("INSERT INTO generation_tasks(task_id,internal_user_pk,session_row_id,prescription_id,idempotency_key,status,progress_indeterminate,message_code,fallback_applied,music_asset_id,completed_at) VALUES(:id,:owner,:session,:p,:id,'matched_fallback',0,'synthetic',1,'music_shared','2026-10-12 08:00:00')"),{'id':task_id,'owner':owner,'session':session_id,'p':'p_'+task_id})
    connection.execute(text("INSERT INTO favorites(favorite_id,internal_user_pk,music_asset_id) VALUES('synthetic-fav',7,'music_shared')"))


def test_0012_registration_and_owner_defaults(upgraded):
    assert migrations.V3_MIGRATION_VERSIONS[-1] == VERSION
    with upgraded.begin() as connection:
        seed(connection)
        protected = ('users','music_assets','generation_tasks','diagnosis_runs','prescription_v3')
        before = {table: connection.execute(text(f'SELECT * FROM {table} ORDER BY 1')).fetchall() for table in protected}
    result = migrations.apply_v3_migrations(upgraded)
    assert result['applied_versions'] == ['0011_v3_auth_foundation',VERSION]
    assert migrations.apply_v3_migrations(upgraded)['applied_versions'] == []
    with upgraded.begin() as connection:
        connection.execute(text('INSERT INTO owner_music_state(owner_internal_user_pk) VALUES(7)'))
        connection.execute(text("INSERT INTO music_library_state(owner_internal_user_pk,music_asset_id) VALUES(7,'music_shared')"))
        assert connection.execute(text('SELECT library_epoch,feedback_evidence_epoch,preference_clear_cutoff FROM owner_music_state')).one() == (0,0,None)
        assert connection.execute(text('SELECT metadata_version FROM music_library_state')).scalar_one() == 0
        assert {table: connection.execute(text(f'SELECT * FROM {table} ORDER BY 1')).fetchall() for table in protected} == before
        assert connection.execute(text('PRAGMA foreign_key_check')).fetchall() == []
    for name in ('library_epoch','feedback_evidence_epoch'):
        assert str(next(c['type'] for c in inspect(upgraded).get_columns('owner_music_state') if c['name']==name)) == 'BIGINT'
    assert 'last_played_at' not in {c['name'] for c in inspect(upgraded).get_columns('music_library_state')}


def test_existing_0011_and_fresh_create_initialize(upgraded,tmp_path,monkeypatch):
    from backend.app.core import database
    with monkeypatch.context() as context:
        context.setattr(migrations,'V3_MIGRATION_VERSIONS',migrations.V3_MIGRATION_VERSIONS[:11])
        migrations.apply_v3_migrations(upgraded)
    assert migrations.apply_v3_migrations(upgraded)['applied_versions'] == [VERSION]
    engine = create_engine(f'sqlite:///{tmp_path / "fresh.sqlite"}')
    monkeypatch.setattr(database,'engine',engine)
    database.init_database()
    database.init_database()
    assert 'music_playback_events' in inspect(engine).get_table_names()
    with engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM schema_migrations')).scalar_one()==12
        assert connection.execute(text('PRAGMA foreign_key_check')).fetchall()==[]
    engine.dispose()


@pytest.mark.parametrize('owner,context',[ (7,'ctx_other'),(7,'missing-context'),(1,'ctx_a') ])
def test_play_context_composite_fk_rejects_other_owner(upgraded,owner,context):
    from sqlalchemy.exc import IntegrityError
    with upgraded.begin() as connection:
        seed(connection)
    migrations.apply_v3_migrations(upgraded)
    with pytest.raises(IntegrityError):
        with upgraded.begin() as connection:
            connection.execute(text("INSERT INTO music_playback_events(internal_user_pk,event_id,music_asset_id,event_type,source_context_id,occurred_at) VALUES(:owner,'synthetic-event','music_shared','play_started',:context,'2026-10-15 00:00:00')"),{'owner':owner,'context':context})


def test_downgrade_rejects_extension_data(upgraded):
    migrations.apply_v3_migrations(upgraded)
    with upgraded.begin() as connection:
        connection.execute(text('INSERT INTO owner_music_state(owner_internal_user_pk) VALUES(7)'))
    with pytest.raises(Exception):
        migrations.rollback_music_library(upgraded)
    assert 'owner_music_state' in inspect(upgraded).get_table_names()
    with upgraded.begin() as connection:
        connection.execute(text('DELETE FROM owner_music_state'))
    migrations.rollback_music_library(upgraded)
    assert 'owner_music_state' not in inspect(upgraded).get_table_names()
    assert migrations.apply_v3_migrations(upgraded)['applied_versions']==[VERSION]


def test_real_migrated_api_matches_fixed_fixture(upgraded,tmp_path,monkeypatch):
    from backend.app.core.database import get_db
    from backend.app.schemas.v3.common import AuthPrincipal
    from backend.app.services.v3.auth_service import get_current_v3_principal
    from backend.app.routers.v3 import music_library_router
    from backend.app.routers.v3.transport import V3APIError,v3_api_error_handler
    from backend.app.models.v3.music_library import OwnerMusicState
    with upgraded.begin() as connection:
        seed(connection)
    migrations.apply_v3_migrations(upgraded)
    media = tmp_path / 'media'
    media.mkdir()
    (media/'music_shared.mp3').write_bytes(b'synthetic test audio')
    monkeypatch.setenv('HARMONY_MEDIA_ROOT',str(media))
    monkeypatch.setenv('HARMONY_LIBRARY_CURSOR_SECRET','synthetic-cursor-fixture-key-123456789')
    app = FastAPI()
    app.add_exception_handler(V3APIError,v3_api_error_handler)
    app.include_router(music_library_router.router,prefix='/api/v3')
    factory = sessionmaker(bind=upgraded)
    def get_test_db():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = get_test_db
    app.dependency_overrides[get_current_v3_principal] = lambda: AuthPrincipal(internal_user_pk=7,public_user_id='synthetic-owner',auth_type='registered',guest_expires_at=None)
    fixture=json.loads((FIXTURES/'int2_music_library_api_v1.json').read_text(encoding='utf-8'))
    with TestClient(app) as client:
        for key in ('history','favorites','detail','selected_detail'):
            case=fixture[key]
            response=client.request(case['method'],case['path'])
            assert response.status_code==case['status']
            body=response.json()
            assert set(body)=={'ok','data','request_id','schema_version'}
            assert body['schema_version']=='harmonyai_v3.0' and body['request_id']
            assert body['data']==case['data']
        with factory() as db:
            assert db.get(OwnerMusicState,7) is None  # GET does not create state
        for key in ('title','stale_title','play','play_replay'):
            case=fixture[key]
            # Pin server time for deterministic playback fixture, never client time.
            monkeypatch.setattr(music_library_router,'_utc_now',lambda:datetime(2026,10,15,tzinfo=timezone.utc))
            import backend.app.services.v3.music_library_service as service
            original=service.record_playback_event
            # Actual implementation used with deterministic time only.
            def record_with_time(db,**kwargs):
                return original(db,now=datetime(2026,10,15,tzinfo=timezone.utc),**kwargs)
            monkeypatch.setattr(music_library_router,'record_playback_event',record_with_time)
            response=client.request(case['method'],case['path'],json=case['body'])
            assert response.status_code==case['status']
            body=response.json()
            if case['status']==409:
                assert body['error']['code']==case['error_code']
            else:
                assert body['data']==case['data']
        for case in fixture['errors']:
            response=client.request(case['method'],case['path'])
            assert response.status_code==case['status']
            body=response.json()
            assert set(body)=={'ok','error','request_id','schema_version'}
            assert body['ok'] is False and isinstance(body['error']['message'],str)
            assert {key:body['error'][key] for key in ('code','retryable','next_actions')}==case['error']
        invalid=client.patch('/api/v3/music/assets/music_shared/title',json={'user_title':'test','expected_version':-1})
        assert invalid.status_code==422 and isinstance(invalid.json()['detail'],list)
        with factory() as db:
            assert db.get(OwnerMusicState,7).library_epoch==2 # title + first play, replay=0
    with upgraded.connect() as connection:
        assert connection.execute(text('PRAGMA foreign_key_check')).fetchall()==[]
        assert connection.execute(text('SELECT title,checksum FROM music_assets')).one()==('Original','sha256:synthetic')


@pytest.mark.parametrize('sql',[
    'INSERT INTO owner_music_state(owner_internal_user_pk,library_epoch) VALUES(7,-1)',
    'INSERT INTO owner_music_state(owner_internal_user_pk,feedback_evidence_epoch) VALUES(7,-1)',
    'INSERT INTO owner_music_state(owner_internal_user_pk) VALUES(999)',
    "INSERT INTO music_library_state(owner_internal_user_pk,music_asset_id,metadata_version) VALUES(7,'music_shared',-1)",
    "INSERT INTO music_library_state(owner_internal_user_pk,music_asset_id,user_title) VALUES(7,'music_shared','')",
])
def test_migrated_constraints_reject_invalid_rows(upgraded,sql):
    from sqlalchemy.exc import IntegrityError
    with upgraded.begin() as connection:
        seed(connection)
    migrations.apply_v3_migrations(upgraded)
    with pytest.raises(IntegrityError):
        with upgraded.begin() as connection:
            connection.execute(text(sql))


def test_title_character_limit_and_owner_uniqueness(upgraded):
    from sqlalchemy.exc import IntegrityError
    with upgraded.begin() as connection:
        seed(connection)
    migrations.apply_v3_migrations(upgraded)
    with upgraded.begin() as connection:
        for owner in (7,1):
            connection.execute(text("INSERT INTO music_library_state(owner_internal_user_pk,music_asset_id,user_title) VALUES(:owner,'music_shared',:title)"),{'owner':owner,'title':'音'*120})
    with pytest.raises(IntegrityError):
        with upgraded.begin() as connection:
            connection.execute(text("UPDATE music_library_state SET user_title=:title WHERE owner_internal_user_pk=7"),{'title':'音'*121})
    with pytest.raises(IntegrityError):
        with upgraded.begin() as connection:
            connection.execute(text("INSERT INTO music_library_state(owner_internal_user_pk,music_asset_id) VALUES(7,'music_shared')"))


def test_0012_failure_rolls_back_and_can_retry(upgraded,tmp_path):
    import shutil
    root=tmp_path/'migrations'
    shutil.copytree(Path(__file__).parents[3]/'backend/migrations/v3',root)
    source=root/'sqlite'/f'{VERSION}_up.sql'
    source.write_text(source.read_text()+'\nINSERT INTO missing_table VALUES(1);\n')
    with pytest.raises(Exception):
        migrations.apply_v3_migrations(upgraded,migrations_root=root)
    assert 'owner_music_state' not in inspect(upgraded).get_table_names()
    assert migrations.apply_v3_migrations(upgraded)['applied_versions']==[VERSION] #0011 committed separately


def test_incompatible_unregistered_side_table_fails_closed(upgraded):
    with upgraded.begin() as connection:
        connection.execute(text('CREATE TABLE owner_music_state(owner_internal_user_pk INTEGER PRIMARY KEY,library_epoch INTEGER DEFAULT 0)'))
    with pytest.raises(migrations.MigrationSchemaMismatch):
        migrations.apply_v3_migrations(upgraded)


def test_mysql_character_semantics_compile_without_connecting():
    from sqlalchemy.schema import CreateTable
    from sqlalchemy.dialects import mysql
    from backend.app.models.v3.music_library import MusicLibraryState,OwnerMusicState,MusicPlaybackEvent
    sql=str(CreateTable(MusicLibraryState.__table__).compile(dialect=mysql.dialect()))
    assert 'char_length' in sql.lower()
    for cls in (OwnerMusicState,MusicLibraryState,MusicPlaybackEvent):
        assert 'FOREIGN KEY' in str(CreateTable(cls.__table__).compile(dialect=mysql.dialect()))


def test_music_card_fixture_unchanged_and_new_contract_uses_same_card():
    existing=json.loads((FIXTURES/'music_card_v1.json').read_text(encoding='utf-8'))
    new=json.loads((FIXTURES/'int2_music_library_api_v1.json').read_text(encoding='utf-8'))
    assert existing==new['history']['data']['items'][0]==new['detail']['data']['card']


def test_context_fk_rejects_same_owner_different_asset(upgraded):
    from sqlalchemy.exc import IntegrityError
    with upgraded.begin() as connection:
        seed(connection)
        connection.execute(text("INSERT INTO music_assets(music_asset_id,source_type,title,storage_key,format,duration_seconds,checksum,playable_status) VALUES('second','matched','Synthetic','second.mp3','mp3',240,'sha256:second','ready')"))
    migrations.apply_v3_migrations(upgraded)
    with pytest.raises(IntegrityError):
        with upgraded.begin() as connection:
            connection.execute(text("INSERT INTO music_playback_events(internal_user_pk,event_id,music_asset_id,event_type,source_context_id,occurred_at) VALUES(7,'wrong-asset','second','play_started','ctx_a','2026-10-15 00:00:00')"))


def test_applied_0012_checksum_change_is_rejected(upgraded,tmp_path):
    import shutil
    migrations.apply_v3_migrations(upgraded)
    root=tmp_path/'changed-migrations'
    shutil.copytree(Path(__file__).parents[3]/'backend/migrations/v3',root)
    source=root/'sqlite'/f'{VERSION}_up.sql'
    source.write_text(source.read_text()+'\n-- changed SQL\n')
    with pytest.raises(migrations.MigrationChecksumMismatch):
        migrations.apply_v3_migrations(upgraded,migrations_root=root)
