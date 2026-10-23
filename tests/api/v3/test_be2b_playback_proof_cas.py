"""Backend proof and CAS on real, FK-enforced SQLite; no HTTP or Provider."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from threading import Barrier, Lock

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from backend.app.core.database import Base
from backend.app.models.user import User
from backend.app.models.v3.music import GenerationTask
from backend.app.models.v3.music_library import OwnerMusicState
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.services.v3 import music_library_access as access
from backend.app.services.v3 import owner_music_state_service as state
from tests.api.v3.test_int2_0012_contract import seed


def principal(owner=7):
    return AuthPrincipal(internal_user_pk=owner, public_user_id=f'synthetic-{owner}',
                         auth_type='registered', guest_expires_at=None)


def proof(db, **changes):
    resolver = getattr(access, 'resolve_feedback_playback_proof', None)
    assert callable(resolver), 'Backend must provide the specified-event authority'
    arguments = dict(principal=principal(), music_id='music_shared',
                     source_context_id='ctx_a', playback_event_id='play-a',
                     session_id='synthetic-session')
    arguments.update(changes)
    return resolver(db, **arguments)


def cas(db, expected=0, owner=7):
    operation = getattr(state, 'compare_and_advance_feedback_epoch', None)
    assert callable(operation), 'Backend must provide atomic expected-epoch CAS'
    return operation(db, internal_user_pk=owner, expected_epoch=expected)


@pytest.fixture
def resources(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "proof-cas.sqlite"}',
                           connect_args={'check_same_thread': False, 'timeout': 10},
                           poolclass=NullPool)

    @event.listens_for(engine, 'connect')
    def enforce_fk(connection, record):
        connection.execute('PRAGMA foreign_keys=ON')

    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO users(id,openid) VALUES(1,'synthetic-one'),(7,'synthetic-seven')"))
        connection.execute(text("INSERT INTO sessions(id,user_id,session_id) VALUES(1,7,'synthetic-session')"))
        seed(connection)
        connection.execute(text("INSERT INTO sessions(id,user_id,session_id) VALUES(3,7,'synthetic-another')"))
        for owner, event_id, context in [(7, 'play-a', 'ctx_a'), (7, 'play-b', 'ctx_b'),
                                          (1, 'play-a', 'ctx_other'), (7, 'no-context', None)]:
            connection.execute(text("INSERT INTO music_playback_events(internal_user_pk,event_id,music_asset_id,event_type,source_context_id,occurred_at) VALUES(:owner,:event,'music_shared','play_started',:context,'2026-10-23 00:00:00')"),
                               {'owner': owner, 'event': event_id, 'context': context})
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    try:
        yield engine, factory
    finally:
        engine.dispose()


@pytest.mark.parametrize('terminal', ['succeeded', 'matched_fallback'])
def test_proof_uses_specified_persisted_relations_and_is_immutable(resources, terminal):
    engine, factory = resources
    with engine.begin() as connection:
        connection.execute(text("UPDATE generation_tasks SET status=:status,fallback_applied=:fallback WHERE task_id='ctx_a'"),
                           {'status': terminal, 'fallback': int(terminal == 'matched_fallback')})
    with factory() as db:
        result = proof(db)
        assert (result.internal_user_pk, result.music_asset_id, result.source_context_id,
                result.playback_event_id, result.session_row_id) == (7, 'music_shared', 'ctx_a', 'play-a', 1)
        actual = db.execute(text("SELECT playback_event_row_id FROM music_playback_events WHERE internal_user_pk=7 AND event_id='play-a'")).scalar_one()
        assert result.playback_event_row_id == actual
        assert result.occurred_at.replace(tzinfo=timezone.utc) == datetime(2026, 10, 23, tzinfo=timezone.utc)
        with pytest.raises(FrozenInstanceError):
            result.source_context_id = 'ctx_b'
        assert state.current_owner_music_state(db, internal_user_pk=7) is None


@pytest.mark.parametrize('changes', [
    {'playback_event_id': 'missing'}, {'playback_event_id': 'play-b'},
    {'source_context_id': 'ctx_b'}, {'playback_event_id': 'no-context'},
    {'source_context_id': 'ctx_other'}, {'source_context_id': 'missing'},
    {'session_id': 'synthetic-other'}, {'session_id': 'synthetic-another'},
    {'session_id': 'missing'}, {'music_id': 'missing'}, {'principal': principal(1)},
    {'source_context_id': None}, {'playback_event_id': ''}, {'session_id': ''},
])
def test_wrong_specified_proof_fails_even_with_other_valid_plays(resources, changes):
    _, factory = resources
    with factory() as db:
        error = getattr(access, 'PlaybackProofUnavailable', RuntimeError)
        with pytest.raises(error):
            proof(db, **changes)
        assert state.current_owner_music_state(db, internal_user_pk=7) is None


def test_unplayed_task_cannot_borrow_other_event_or_favorite(resources):
    engine, factory = resources
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM music_playback_events WHERE internal_user_pk=7 AND source_context_id='ctx_a'"))
    with factory() as db:
        error = getattr(access, 'PlaybackProofUnavailable', RuntimeError)
        with pytest.raises(error):
            proof(db)


def test_proof_does_not_flush_pending_changes_or_finish_caller_transaction(resources):
    engine, factory = resources
    with sessionmaker(bind=engine, autoflush=True)() as db:
        pending = User(id=99, openid='synthetic-unflushed')
        db.add(pending)
        completed = []
        event.listen(db, 'after_commit', lambda db: completed.append('commit'))
        event.listen(db, 'after_rollback', lambda db: completed.append('rollback'))
        proof(db)
        assert pending in db.new
        assert completed == []
        assert db.connection().execute(text('SELECT count(*) FROM users WHERE id=99')).scalar_one() == 0
        db.rollback()
    with factory() as db:
        assert state.current_owner_music_state(db, internal_user_pk=7) is None


def test_pending_task_and_non_play_event_are_rejected_by_real_constraints(resources):
    engine, factory = resources
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM music_playback_events WHERE source_context_id='ctx_a'"))
        connection.execute(text("UPDATE generation_tasks SET status='running',music_asset_id=NULL,fallback_applied=0 WHERE task_id='ctx_a'"))
    with factory() as db:
        error = getattr(access, 'PlaybackProofUnavailable', RuntimeError)
        with pytest.raises(error):
            proof(db)
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO music_playback_events(internal_user_pk,event_id,music_asset_id,event_type,occurred_at) VALUES(7,'not-play','music_shared','page_view','2026-10-23')"))


def test_legacy_context_behavior_is_unchanged(resources):
    _, factory = resources
    with factory() as db:
        assert access.resolve_feedback_context(db, internal_user_pk=7, music_id='music_shared', context_id='ctx_b') == 'ctx_b'


def test_cas_first_write_and_replay_conflict_do_not_commit(resources):
    _, factory = resources
    with factory() as db:
        assert cas(db) == 1
        assert state.feedback_evidence_epoch_for(db, internal_user_pk=7) == 1
        error = getattr(state, 'FeedbackEpochConflict', RuntimeError)
        with pytest.raises(error):
            cas(db)
        assert state.library_epoch_for(db, internal_user_pk=7) == 0
        db.rollback()
    with factory() as db:
        assert state.current_owner_music_state(db, internal_user_pk=7) is None


def test_cas_stale_identity_cannot_bypass_database_condition(resources):
    engine, factory = resources
    with engine.begin() as connection:
        connection.execute(text('INSERT INTO owner_music_state(owner_internal_user_pk) VALUES(7)'))
    with factory() as stale:
        cached = stale.get(OwnerMusicState, 7)
        assert cached.feedback_evidence_epoch == 0
        # Separate connection commits a newer authoritative value.
        with factory.begin() as fresh:
            assert cas(fresh) == 1
        error = getattr(state, 'FeedbackEpochConflict', RuntimeError)
        with pytest.raises(error):
            cas(stale, 0)
        assert cas(stale, 1) == 2
        assert cached.feedback_evidence_epoch == 2
        stale.commit()


@pytest.mark.parametrize('expected', [-1, True, '0', 1.5, None, 9223372036854775807])
def test_invalid_or_overflowing_epoch_is_rejected_without_state(resources, expected):
    _, factory = resources
    with factory() as db:
        with pytest.raises(ValueError):
            cas(db, expected)
        assert state.current_owner_music_state(db, internal_user_pk=7) is None


def test_missing_state_with_nonzero_expected_is_not_created(resources):
    _, factory = resources
    with factory() as db:
        error = getattr(state, 'FeedbackEpochConflict', RuntimeError)
        with pytest.raises(error):
            cas(db, 4)
        assert state.current_owner_music_state(db, internal_user_pk=7) is None


@pytest.mark.parametrize('preexisting', [False, True], ids=['first-state-race', 'existing-state-race'])
def test_two_physical_connections_same_epoch_have_one_winner(resources, preexisting):
    engine, factory = resources
    if preexisting:
        with engine.begin() as connection:
            connection.execute(text('INSERT INTO owner_music_state(owner_internal_user_pk) VALUES(7)'))
    start = Barrier(2, timeout=10)
    connection_ids, lock = [], Lock()

    def contender():
        with factory() as db:
            raw = db.connection().connection.driver_connection
            with lock:
                connection_ids.append(id(raw))
            start.wait()
            try:
                value = cas(db)
                db.commit()
                return ('won', value)
            except getattr(state, 'FeedbackEpochConflict', RuntimeError):
                db.rollback()
                return ('conflict', None)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: contender(), range(2)))
    assert len(set(connection_ids)) == 2
    assert sorted(results, key=lambda row: row[0]) == [('conflict', None), ('won', 1)]
    with factory() as db:
        assert db.query(OwnerMusicState).count() == 1
        assert state.feedback_evidence_epoch_for(db, internal_user_pk=7) == 1


def test_different_owners_advance_independently(resources):
    _, factory = resources
    start = Barrier(2, timeout=10)

    def write(owner):
        with factory() as db:
            db.connection()
            start.wait()
            result = cas(db, owner=owner)
            db.commit()
            return result

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(write, [1, 7])) == [1, 1]
    with factory() as db:
        assert [state.feedback_evidence_epoch_for(db, internal_user_pk=pk) for pk in [1, 7]] == [1, 1]


@pytest.mark.parametrize('failure', ['injected', 'real-fk'])
def test_caller_failure_rolls_back_epoch_and_business_data(resources, failure):
    _, factory = resources
    with factory() as db:
        with pytest.raises(RuntimeError if failure == 'injected' else IntegrityError):
            assert cas(db) == 1
            db.execute(text('DELETE FROM favorites WHERE internal_user_pk=7'))
            db.execute(text("INSERT INTO favorites(favorite_id,internal_user_pk,music_asset_id) VALUES('business',7,'music_shared')"))
            if failure == 'injected':
                raise RuntimeError('synthetic caller failure after CAS')
            db.execute(text("INSERT INTO favorites(favorite_id,internal_user_pk,music_asset_id) VALUES('invalid-owner',999,'music_shared')"))
        db.rollback()
    with factory() as db:
        assert state.current_owner_music_state(db, internal_user_pk=7) is None
        assert db.execute(text("SELECT count(*) FROM favorites WHERE favorite_id='business'")).scalar_one() == 0


def test_read_helpers_and_proof_replay_do_not_create_owner_state(resources):
    _, factory = resources
    with factory() as db:
        assert state.feedback_evidence_epoch_for(db, internal_user_pk=7) == 0
        assert state.library_epoch_for(db, internal_user_pk=7) == 0
        assert proof(db) == proof(db)
        assert db.query(OwnerMusicState).count() == 0


@pytest.mark.parametrize('pending', ['delete', 'move-owner'])
def test_pending_state_removal_or_owner_change_cannot_erase_successful_cas(resources, pending):
    engine, factory = resources
    with engine.begin() as connection:
        connection.execute(text('INSERT INTO owner_music_state(owner_internal_user_pk) VALUES(7)'))
    with factory() as db:
        row = db.get(OwnerMusicState, 7)
        if pending == 'delete':
            db.delete(row)
        else:
            row.owner_internal_user_pk = 1
        with pytest.raises(ValueError):
            cas(db)
        assert db.connection().execute(text('SELECT feedback_evidence_epoch FROM owner_music_state WHERE owner_internal_user_pk=7')).scalar_one() == 0
        db.rollback()


@pytest.mark.parametrize('pending', ['new', 'dirty-epoch'])
def test_pending_epoch_cannot_compete_with_core_cas(resources, pending):
    engine, factory = resources
    with factory() as db:
        if pending == 'new':
            db.add(OwnerMusicState(owner_internal_user_pk=7, library_epoch=0, feedback_evidence_epoch=0))
        else:
            with engine.begin() as connection:
                connection.execute(text('INSERT INTO owner_music_state(owner_internal_user_pk) VALUES(7)'))
            db.get(OwnerMusicState, 7).feedback_evidence_epoch = 8
        with pytest.raises(ValueError):
            cas(db)
        db.rollback()


def test_cas_with_autoflush_does_not_flush_unrelated_business_work(resources):
    engine, _ = resources
    with sessionmaker(bind=engine, autoflush=True)() as db:
        pending = User(id=99, openid='synthetic-pending-business')
        db.add(pending)
        assert cas(db) == 1
        assert pending in db.new
        assert db.connection().execute(text('SELECT count(*) FROM users WHERE id=99')).scalar_one() == 0
        db.rollback()


def test_proof_uses_database_task_not_locally_edited_identity_map(resources):
    engine, _ = resources
    with sessionmaker(bind=engine, autoflush=True)() as db:
        cached = db.get(GenerationTask, 'ctx_a')
        cached.status = 'running'
        cached.session_row_id = 3
        assert proof(db).session_row_id == 1
        assert cached.status == 'running' and cached.session_row_id == 3
        db.rollback()


@pytest.mark.parametrize('session', ['synthetic-session', 'synthetic-other'])
def test_task_linked_to_other_owners_session_is_not_proof(resources, session):
    engine, factory = resources
    with engine.begin() as connection:
        connection.execute(text("UPDATE generation_tasks SET session_row_id=2 WHERE task_id='ctx_a'"))
    with factory() as db:
        with pytest.raises(access.PlaybackProofUnavailable):
            proof(db, session_id=session)


def test_existing_wrong_asset_cannot_reuse_valid_event(resources):
    engine, factory = resources
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO music_assets(music_asset_id,owner_internal_user_pk,source_type,title,storage_key,format,duration_seconds,checksum,playable_status) VALUES('other',7,'matched','Synthetic','unused.wav','wav',1,'sha256:other','ready')"))
    with factory() as db:
        with pytest.raises(access.PlaybackProofUnavailable):
            proof(db, music_id='other')


def test_unknown_owner_cas_propagates_real_foreign_key_failure(resources):
    _, factory = resources
    with factory() as db:
        with pytest.raises(IntegrityError):
            cas(db, owner=999)
        db.rollback()
        assert db.query(OwnerMusicState).count() == 0
