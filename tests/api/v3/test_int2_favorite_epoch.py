"""Favorite epoch transitions on real migrated SQLite, synthetic resources only."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from tests.api.v3.test_int2_0012_contract import seed
from tests.api.v3.test_feedback import _feedback_body
from backend.app.core import v3_migrations as migrations
from backend.app.core.database import Base
from backend.app.models import Session as SessionModel
from backend.app.models.v3.feedback import Favorite, FeedbackV3
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.schemas.v3.feedback import FeedbackV3 as Request
from backend.app.services.v3 import feedback_service as service
from backend.app.services.v3 import owner_music_state_service as state
from backend.app.services.v3.music_library_service import page_owner_music, LibraryCursorError


def principal(pk=7):
    return AuthPrincipal(internal_user_pk=pk,public_user_id=f'synthetic-{pk}',auth_type='registered',guest_expires_at=None)


@pytest.fixture(params=[False,True],ids=['production-no-autoflush','legacy-autoflush'])
def resources(tmp_path,monkeypatch,request):
    engine=create_engine(f'sqlite:///{tmp_path / "favorites.sqlite"}',connect_args={'check_same_thread':False})
    @event.listens_for(engine,'connect')
    def foreign_keys(connection,record):
        connection.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    migrations.apply_v3_migrations(engine)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO users(id,openid) VALUES(7,'synthetic-seven')"))
        connection.execute(text("INSERT INTO sessions(id,user_id,session_id) VALUES(1,7,'synthetic-session')"))
        seed(connection)
        for name,owner in [('owned1',7),('owned2',7),('foreign',1),('unclaimed',None)]:
            connection.execute(text("INSERT INTO music_assets(music_asset_id,owner_internal_user_pk,source_type,title,storage_key,format,duration_seconds,checksum,playable_status) VALUES(:name,:owner,'matched','Synthetic',:path,'mp3',240,:checksum,'ready')"),{'name':name,'owner':owner,'path':name+'.mp3','checksum':'sha256:synthetic-'+name})
    media=tmp_path/'media'
    media.mkdir()
    for name in ('owned1','owned2','foreign','unclaimed','music_shared'):
        (media/(name+'.mp3')).write_bytes(b'synthetic fixture')
    monkeypatch.setenv('HARMONY_MEDIA_ROOT',str(media))
    monkeypatch.setenv('HARMONY_LIBRARY_CURSOR_SECRET','synthetic-favorite-cursor-secret-0123456789')
    try:
        yield engine,sessionmaker(bind=engine,autoflush=request.param,autocommit=False)
    finally:
        engine.dispose()


def epoch(factory,pk=7):
    with factory() as db:
        return state.library_epoch_for(db,internal_user_pk=pk)


def feedback(factory,intent,key):
    with factory() as db:
        session_id=db.query(SessionModel).filter(SessionModel.id==1).one().session_id
        body=Request.model_validate(_feedback_body(session_id,'owned1',favorite=intent))
        return service.submit_feedback(db,principal(),body,key)


def test_add_repeat_remove_repeat_and_owner_isolation(resources):
    _,factory=resources
    with factory() as db:
        assert service.set_favorite(db,principal(),'owned1').is_favorite is True
    assert epoch(factory)==1 and epoch(factory,1)==0
    with factory() as db:
        service.set_favorite(db,principal(),'owned1')
    assert epoch(factory)==1
    with factory() as db:
        assert service.remove_favorite(db,principal(),'owned1').is_favorite is False
    assert epoch(factory)==2
    with factory() as db:
        service.remove_favorite(db,principal(),'owned1')
    assert epoch(factory)==2 and epoch(factory,1)==0


@pytest.mark.parametrize('intent',[True,False,None])
def test_feedback_real_transition_replay_and_noop(resources,intent):
    _,factory=resources
    if intent is False:
        with factory.begin() as db:
            db.add(Favorite(favorite_id='synthetic-before',internal_user_pk=7,music_asset_id='owned1'))
    expected=0 if intent is None else 1
    result,replayed=feedback(factory,intent,'first')
    assert result.status=='saved' and replayed is False
    assert epoch(factory)==expected
    _,replayed=feedback(factory,intent,'first')
    assert replayed is True and epoch(factory)==expected
    feedback(factory,intent,'different-feedback-same-intent')
    assert epoch(factory)==expected
    with factory() as db:
        assert db.query(FeedbackV3).count()==2
        assert db.query(Favorite).filter(Favorite.music_asset_id=='owned1').count()==(1 if intent is True else 0)


@pytest.mark.parametrize('operation',['put','delete','feedback'])
def test_epoch_failure_rolls_back_business_write(resources,monkeypatch,operation):
    _,factory=resources
    if operation=='delete':
        with factory.begin() as db:
            db.add(Favorite(favorite_id='before',internal_user_pk=7,music_asset_id='owned1'))
    actual_advance=state.advance_library_epoch
    def failed(*args,**kwargs):
        actual_advance(*args,**kwargs)
        raise RuntimeError('synthetic epoch failure')
    monkeypatch.setattr(state,'advance_library_epoch',failed)
    with pytest.raises(RuntimeError,match='synthetic epoch'):
        if operation=='feedback':
            feedback(factory,True,'rollback')
        else:
            with factory() as db:
                (service.set_favorite if operation=='put' else service.remove_favorite)(db,principal(),'owned1')
    with factory() as db:
        assert db.query(Favorite).filter(Favorite.music_asset_id=='owned1').count()==(1 if operation=='delete' else 0)
        assert db.query(FeedbackV3).count()==0
    assert epoch(factory)==0


def test_feedback_status_stage_failure_does_not_undo_durable_stage1(resources,monkeypatch):
    _,factory=resources
    def failed(*args,**kwargs):
        raise RuntimeError('synthetic stage2')
    monkeypatch.setattr(service,'_set_status',failed)
    with pytest.raises(RuntimeError,match='stage2'):
        feedback(factory,True,'durable')
    assert epoch(factory)==1
    with factory() as db:
        assert db.query(FeedbackV3).count()==1
        assert db.query(Favorite).filter(Favorite.music_asset_id=='owned1').count()==1
    result,replayed=feedback(factory,True,'durable')
    assert result.status=='saved' and replayed and epoch(factory)==1


def test_favorite_cursor_invalidated_and_get_does_not_create_state(resources):
    _,factory=resources
    with factory.begin() as db:
        db.add(Favorite(favorite_id='cursor-first',internal_user_pk=7,music_asset_id='owned1'))
    with factory() as db:
        page=page_owner_music(db,internal_user_pk=7,limit=1,list_key='favorites',favorites_only=True)
        assert page.next_cursor is not None
        assert state.current_owner_music_state(db,internal_user_pk=7) is None
        assert service.list_favorites(db,principal()).total==2
        assert state.current_owner_music_state(db,internal_user_pk=7) is None
    with factory() as db:
        service.set_favorite(db,principal(),'owned2')
    with factory() as db:
        with pytest.raises(LibraryCursorError) as error:
            page_owner_music(db,internal_user_pk=7,limit=1,list_key='favorites',favorites_only=True,cursor=page.next_cursor)
        assert error.value.stale


@pytest.mark.parametrize('preexisting_state',[False,True])
@pytest.mark.parametrize('operation',['put','delete'])
def test_real_independent_connections_same_favorite_once(resources,preexisting_state,operation):
    engine,factory=resources
    with factory.begin() as db:
        if preexisting_state:
            state.lock_owner_music_state(db,internal_user_pk=7)
        if operation=='delete':
            db.add(Favorite(favorite_id='race-before',internal_user_pk=7,music_asset_id='owned1'))
    barrier=Barrier(2,timeout=10)
    connections=set()
    mutex=Lock()
    def synchronize(connection,cursor,sql,parameters,context,many):
        if sql.lower().lstrip().startswith('insert into favorites' if operation=='put' else 'delete from favorites'):
            with mutex:
                connections.add(id(connection.connection.driver_connection))
            barrier.wait()
    def write():
        with factory() as db:
            return (service.set_favorite if operation=='put' else service.remove_favorite)(db,principal(),'owned1')
    event.listen(engine,'before_cursor_execute',synchronize)
    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            futures=[workers.submit(write) for _ in range(2)]
            results=[f.result(timeout=20) for f in futures]
    finally:
        event.remove(engine,'before_cursor_execute',synchronize)
    assert len(connections)==2
    assert all(r.is_favorite is (operation=='put') for r in results)
    assert epoch(factory)==1
    with factory() as db:
        assert db.query(Favorite).filter(Favorite.music_asset_id=='owned1').count()==(1 if operation=='put' else 0)


@pytest.mark.parametrize('same_key',[True,False])
def test_real_feedback_race_keeps_stage1_and_one_favorite_epoch(resources,same_key):
    engine,factory=resources
    barrier=Barrier(2,timeout=10)
    connections=set()
    mutex=Lock()
    def synchronize(connection,cursor,sql,parameters,context,many):
        # Synchronize BEFORE each connection's first real write. Waiting after
        # an earlier Favorite INSERT would deadlock our own test on SQLite.
        if sql.lower().lstrip().startswith(('insert into feedback_v3','insert into favorites')):
            with mutex:
                identity=id(connection.connection.driver_connection)
                first=identity not in connections
                connections.add(identity)
            if first:
                barrier.wait()
    event.listen(engine,'before_cursor_execute',synchronize)
    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            futures=[workers.submit(feedback,factory,True,'same' if same_key else f'key-{i}') for i in range(2)]
            results=[future.result(timeout=20) for future in futures]
    finally:
        event.remove(engine,'before_cursor_execute',synchronize)
    assert len(connections)==2 and epoch(factory)==1
    assert sum(replayed for _,replayed in results)==(1 if same_key else 0)
    with factory() as db:
        assert db.query(FeedbackV3).count()==(1 if same_key else 2)
        assert db.query(Favorite).filter(Favorite.music_asset_id=='owned1').count()==1


@pytest.mark.parametrize('music_id,legacy_allowed,library_allowed',[
    ('owned1',True,True),('unclaimed',True,False),('music_shared',True,True),('foreign',False,False),
])
def test_legacy_permission_contract_unchanged(resources,music_id,legacy_allowed,library_allowed):
    from backend.app.services.v3.music_library_access import require_library_access, LibraryAccessDenied
    _,factory=resources
    with factory() as db:
        if legacy_allowed:
            assert service.set_favorite(db,principal(),music_id).is_favorite
        else:
            with pytest.raises(service.OwnedResourceNotFound):
                service.set_favorite(db,principal(),music_id)
        if library_allowed:
            assert require_library_access(db,internal_user_pk=7,music_id=music_id).asset.music_asset_id==music_id
        else:
            with pytest.raises(LibraryAccessDenied):
                require_library_access(db,internal_user_pk=7,music_id=music_id)


@pytest.mark.parametrize('status',['failed','cancelled','queued','running'])
def test_legacy_null_owner_with_invalid_task_still_does_not_grant_library_access(resources,status):
    from backend.app.services.v3.music_library_access import require_library_access, LibraryAccessDenied
    _,factory=resources
    with factory.begin() as db:
        db.execute(text("INSERT INTO generation_tasks(task_id,internal_user_pk,session_row_id,prescription_id,idempotency_key,status,progress_indeterminate,message_code,fallback_applied) VALUES('nonlegal',7,1,'p_ctx_a','nonlegal',:status,0,'synthetic',0)"),{'status':status})
    with factory() as db:
        service.set_favorite(db,principal(),'unclaimed')
        with pytest.raises(LibraryAccessDenied):
            require_library_access(db,internal_user_pk=7,music_id='unclaimed')


@pytest.mark.parametrize('intent',[True,False])
def test_real_feedback_and_direct_favorite_race(resources,intent):
    engine,factory=resources
    if not intent:
        with factory.begin() as db:
            db.add(Favorite(favorite_id='mixed-before',internal_user_pk=7,music_asset_id='owned1'))
    barrier=Barrier(2,timeout=10)
    connections=set()
    mutex=Lock()
    def synchronize(connection,cursor,sql,parameters,context,many):
        if sql.lower().lstrip().startswith(('insert into feedback_v3','insert into favorites','delete from favorites')):
            with mutex:
                identity=id(connection.connection.driver_connection)
                first=identity not in connections
                connections.add(identity)
            if first:
                barrier.wait()
    def direct():
        with factory() as db:
            return (service.set_favorite if intent else service.remove_favorite)(db,principal(),'owned1')
    event.listen(engine,'before_cursor_execute',synchronize)
    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            fb=workers.submit(feedback,factory,intent,'mixed')
            favorite=workers.submit(direct)
            result,replayed=fb.result(timeout=20)
            assert favorite.result(timeout=20).is_favorite is intent
    finally:
        event.remove(engine,'before_cursor_execute',synchronize)
    assert len(connections)==2 and result.status=='saved' and not replayed
    assert epoch(factory)==1
    feedback(factory,intent,'mixed')
    assert epoch(factory)==1
    with factory() as db:
        assert db.query(FeedbackV3).count()==1
        assert db.query(Favorite).filter_by(internal_user_pk=7,music_asset_id='owned1').count()==int(intent)


def test_real_first_owner_state_unique_conflict_is_not_a_favorite_success(resources):
    from sqlalchemy.exc import IntegrityError
    engine,factory=resources
    barrier=Barrier(2,timeout=10)
    connections=set()
    def synchronize(connection,cursor,sql,parameters,context,many):
        if sql.lower().lstrip().startswith('insert into owner_music_state'):
            connections.add(id(connection.connection.driver_connection))
            barrier.wait()
    def create():
        with factory() as db:
            try:
                state.lock_owner_music_state(db,internal_user_pk=7)
                db.commit()
                return 'created'
            except IntegrityError:
                db.rollback()
                return 'unique-conflict'
    event.listen(engine,'before_cursor_execute',synchronize)
    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            futures=[workers.submit(create) for _ in range(2)]
            results=[future.result(timeout=20) for future in futures]
    finally:
        event.remove(engine,'before_cursor_execute',synchronize)
    assert len(connections)==2 and sorted(results)==['created','unique-conflict']
    assert epoch(factory)==0
    with factory() as db:
        assert db.execute(text('SELECT count(*) FROM owner_music_state')).scalar_one()==1
        assert db.query(Favorite).filter_by(music_asset_id='owned1').count()==0
