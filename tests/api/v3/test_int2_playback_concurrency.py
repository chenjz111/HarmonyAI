"""Real independent SQLite connections, plus explicitly labelled exception tests.

Breaks caught: duplicate event insertion, duplicate epoch bump, false cross-asset
replay, and treating an owner-state conflict as a stored playback event.
SQL listeners synchronize timing only: they never replace DML or inject errors.
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from tests.api.v3.test_int2_0012_contract import upgraded, seed
from backend.app.core import v3_migrations as migrations
from backend.app.core.database import get_db
from backend.app.models.v3.music_library import OwnerMusicState
from backend.app.routers.v3 import music_library_router
from backend.app.routers.v3.transport import V3APIError, v3_api_error_handler
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.services.v3.auth_service import get_current_v3_principal
from backend.app.services.v3.music_library_service import replayed_playback_event
from backend.app.services.v3.owner_music_state_service import lock_owner_music_state


@pytest.fixture
def migrated_library(upgraded, tmp_path, monkeypatch):
    with upgraded.begin() as connection:
        seed(connection)
        connection.execute(text("INSERT INTO music_assets(music_asset_id,owner_internal_user_pk,source_type,title,storage_key,format,duration_seconds,checksum,playable_status) VALUES('second',7,'matched','Synthetic','second.mp3','mp3',240,'sha256:second','ready')"))
    migrations.apply_v3_migrations(upgraded)
    media = tmp_path / 'media'
    media.mkdir()
    for name in ('music_shared', 'second'):
        (media / f'{name}.mp3').write_bytes(b'synthetic audio fixture')
    monkeypatch.setenv('HARMONY_MEDIA_ROOT', str(media))
    factory = sessionmaker(bind=upgraded)
    sessions = []
    app = FastAPI()
    app.add_exception_handler(V3APIError, v3_api_error_handler)
    app.include_router(music_library_router.router, prefix='/api/v3')

    def isolated_db():
        with factory() as db:
            sessions.append(db)
            yield db

    app.dependency_overrides[get_db] = isolated_db
    app.dependency_overrides[get_current_v3_principal] = lambda: AuthPrincipal(
        internal_user_pk=7, public_user_id='synthetic-owner',
        auth_type='registered', guest_expires_at=None,
    )
    with TestClient(app) as client:
        yield upgraded, factory, client, sessions


@pytest.mark.parametrize('preexisting_state', [False, True])
@pytest.mark.parametrize('repetition', range(3))
def test_real_concurrent_same_event_is_one_insert_and_one_epoch(
    migrated_library, preexisting_state, repetition,
):
    _concurrent_requests(migrated_library, preexisting_state, different_asset=False)


@pytest.mark.parametrize('preexisting_state', [False, True])
def test_real_concurrent_cross_asset_event_is_not_a_successful_replay(
    migrated_library, preexisting_state,
):
    _concurrent_requests(migrated_library, preexisting_state, different_asset=True)


def _concurrent_requests(resources, preexisting_state, *, different_asset):
    engine, factory, client, sessions = resources
    if preexisting_state:
        with factory.begin() as db:
            db.add(OwnerMusicState(owner_internal_user_pk=7))
    barrier = Barrier(2, timeout=10)
    connections = set()
    capture_lock = Lock()

    def synchronize_insert(connection, cursor, statement, parameters, context, many):
        if statement.lower().lstrip().startswith('insert into music_playback_events'):
            with capture_lock:
                connections.add(id(connection.connection.driver_connection))
            barrier.wait()

    event.listen(engine, 'before_cursor_execute', synchronize_insert)

    def post(music_id):
        return client.post(f'/api/v3/music/assets/{music_id}/playback-events', json={
            'event_id': 'real-concurrent-event', 'event_type': 'play_started',
            'source_context_id': 'ctx_a' if music_id == 'music_shared' else None,
        })

    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            first = workers.submit(post, 'music_shared')
            second = workers.submit(post, 'second' if different_asset else 'music_shared')
            responses = [first.result(timeout=20), second.result(timeout=20)]
    finally:
        event.remove(engine, 'before_cursor_execute', synchronize_insert)

    assert len(connections) == 2
    assert len(sessions) == 2 and sessions[0] is not sessions[1]
    assert sorted(r.status_code for r in responses) == ([201, 409] if different_asset else [200, 201])
    with engine.connect() as connection:
        rows = connection.execute(text('SELECT music_asset_id, occurred_at FROM music_playback_events')).all()
        assert len(rows) == 1
        winner = rows[0].music_asset_id
        assert connection.execute(text('SELECT library_epoch FROM owner_music_state WHERE owner_internal_user_pk=7')).scalar_one() == 1
        assert connection.execute(text('PRAGMA foreign_key_check')).all() == []
    if different_asset:
        rejected = next(r for r in responses if r.status_code == 409)
        assert rejected.json()['error']['code'] == 'PLAYBACK_EVENT_CONFLICT'
    else:
        assert sorted(r.json()['data']['replayed'] for r in responses) == [False, True]
        assert responses[0].json()['data']['occurred_at'] == responses[1].json()['data']['occurred_at']
    replay = post(winner)
    assert replay.status_code == 200 and replay.json()['data']['replayed'] is True
    with engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM music_playback_events')).scalar_one() == 1
        assert connection.execute(text('SELECT library_epoch FROM owner_music_state WHERE owner_internal_user_pk=7')).scalar_one() == 1


def test_real_first_owner_state_unique_conflict_has_no_playback_to_replay(migrated_library):
    engine, factory, _, _ = migrated_library
    barrier = Barrier(2, timeout=10)
    connections = set()

    def synchronize_insert(connection, cursor, statement, parameters, context, many):
        if statement.lower().lstrip().startswith('insert into owner_music_state'):
            connections.add(id(connection.connection.driver_connection))
            barrier.wait()

    def create_state():
        with factory() as db:
            try:
                lock_owner_music_state(db, internal_user_pk=7)
                db.commit()
                return 'created'
            except IntegrityError:
                db.rollback()
                assert replayed_playback_event(db, internal_user_pk=7, music_id='music_shared', event_id='absent-event') is None
                return 'unique-conflict-no-event'

    event.listen(engine, 'before_cursor_execute', synchronize_insert)
    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            futures = [workers.submit(create_state) for _ in range(2)]
            results = [future.result(timeout=20) for future in futures]
    finally:
        event.remove(engine, 'before_cursor_execute', synchronize_insert)
    assert sorted(results) == ['created', 'unique-conflict-no-event']
    assert len(connections) == 2
    with engine.connect() as connection:
        assert connection.execute(text('SELECT count(*), max(library_epoch) FROM owner_music_state')).one() == (1, 0)
        assert connection.execute(text('SELECT count(*) FROM music_playback_events')).scalar_one() == 0


def test_simulated_owner_state_integrity_error_is_retryable_not_a_replay(migrated_library, monkeypatch):
    engine, factory, client, _ = migrated_library
    with factory.begin() as db:
        db.add(OwnerMusicState(owner_internal_user_pk=7))

    def owner_state_conflict(*args, **kwargs):
        raise IntegrityError('INSERT INTO owner_music_state', {}, Exception('synthetic owner PK conflict'))

    monkeypatch.setattr(music_library_router, 'record_playback_event', owner_state_conflict)
    response = client.post('/api/v3/music/assets/music_shared/playback-events', json={
        'event_id': 'absent-event', 'event_type': 'play_started',
    })
    assert response.status_code == 409
    assert response.json()['error']['code'] == 'PLAYBACK_EVENT_CONFLICT'
    assert response.json()['error']['retryable'] is True
    with engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM music_playback_events')).scalar_one() == 0
        assert connection.execute(text('SELECT library_epoch FROM owner_music_state')).scalar_one() == 0
