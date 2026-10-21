"""The production app must expose the existing, owner-authorized Library API.

No include_router, Principal override, business response fake or Provider call.
Only get_db is replaced with a temporary FK-enforced file database. TestClient
is ASGI/in-process; a separate review probe covers real loopback HTTP.
"""
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import wave

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.app.models.v3.identity import UserIdentity
from backend.app.models.v3.music import MusicAsset
from backend.app.models.v3.music_library import MusicPlaybackEvent, OwnerMusicState
from backend.app.routers.v3.generation_router import get_music_provider


ENDPOINTS = [
    ('GET', '/api/v3/me/music-assets'),
    ('GET', '/api/v3/me/music-favorites'),
    ('GET', '/api/v3/music/assets/{music_id}'),
    ('PATCH', '/api/v3/music/assets/{music_id}/title'),
    ('POST', '/api/v3/music/assets/{music_id}/playback-events'),
]
CARD_FIELDS = {
    'music_id', 'source_type', 'default_title', 'user_title', 'display_title',
    'metadata_version', 'playable_created_at', 'last_played_at', 'activity_at',
    'duration_seconds', 'availability', 'is_favorite', 'primary_instrument_code',
    'primary_instrument_origin', 'source_summary',
}


class RealAppCase:
    def __repr__(self):
        return '<RealAppCase synthetic credentials redacted>'

    def call(self, method, path, *, headers=None, body=None):
        response = self.client.request(method, path, headers=headers, json=body)
        row = {'method': method, 'path': path, 'status': response.status_code}
        if response.content and 'application/json' in response.headers.get('content-type', ''):
            payload = response.json()
            # Never retain the guest-auth credential response.
            if path != '/api/v3/auth/guest':
                row['body'] = payload
        self.requests.append(row)
        return response

    def epoch(self, owner=None):
        with self.factory() as db:
            state = db.get(OwnerMusicState, self.owner if owner is None else owner)
            return state.library_epoch if state else 0


def data(response, status=200):
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {'ok', 'data', 'request_id', 'schema_version'}
    assert body['ok'] is True and body['schema_version'] == 'harmonyai_v3.0'
    assert body['request_id']
    return body['data']


def error(response, status, code):
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {'ok', 'error', 'request_id', 'schema_version'}
    assert body['ok'] is False and body['error']['code'] == code
    assert body['schema_version'] == 'harmonyai_v3.0'


@pytest.fixture
def real_app(tmp_path, monkeypatch, request):
    engine = create_engine(f'sqlite:///{tmp_path / "real-app.sqlite"}', connect_args={'check_same_thread': False})
    request.addfinalizer(engine.dispose)

    @event.listens_for(engine, 'connect')
    def foreign_keys(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')

    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    previous_db = app.dependency_overrides.get(get_db)
    previous_provider = app.dependency_overrides.get(get_music_provider)

    def restore_override(key, previous):
        if previous is None:
            app.dependency_overrides.pop(key, None)
        else:
            app.dependency_overrides[key] = previous

    # Pytest also runs these finalizers when fixture setup or evidence I/O fails.
    request.addfinalizer(lambda: restore_override(get_db, previous_db))
    request.addfinalizer(lambda: restore_override(get_music_provider, previous_provider))

    def isolated_db():
        with factory() as db:
            yield db

    def forbidden_provider():
        pytest.fail('Library/Stream must not resolve a music Provider')

    app.dependency_overrides[get_db] = isolated_db
    app.dependency_overrides[get_music_provider] = forbidden_provider
    media = tmp_path / 'media'
    media.mkdir()
    out = io.BytesIO()
    with wave.open(out, 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b'\0\0' * 800)
    (media / 'synthetic.wav').write_bytes(out.getvalue())
    monkeypatch.setenv('HARMONY_MEDIA_ROOT', str(media))
    monkeypatch.setenv('HARMONY_LIBRARY_CURSOR_SECRET', 'synthetic-wiring-cursor-secret-0123456789')
    case = RealAppCase()
    case.client = TestClient(app)  # Do not run the normal database lifespan.
    request.addfinalizer(lambda: case.client.close())
    case.factory, case.requests, case.audio = factory, [], out.getvalue()
    issued = [data(case.call('POST', '/api/v3/auth/guest'), 201) for _ in range(2)]
    case.headers = {'Authorization': 'Bearer ' + issued[0]['access_token']}
    case.other_headers = {'Authorization': 'Bearer ' + issued[1]['access_token']}
    with factory() as db:
        case.owner = db.query(UserIdentity).filter_by(public_user_id=issued[0]['public_user_id']).one().internal_user_pk
        other = db.query(UserIdentity).filter_by(public_user_id=issued[1]['public_user_id']).one().internal_user_pk
        for name, owner in [('own-a', case.owner), ('own-b', case.owner), ('foreign', other), ('unclaimed', None)]:
            db.add(MusicAsset(
                music_asset_id=name, owner_internal_user_pk=owner, source_type='matched',
                catalog_track_id=name, title='Synthetic original', storage_key='synthetic.wav',
                format='wav', duration_seconds=240, checksum='sha256:' + name,
                playable_status='ready', created_at=datetime(2026, 10, 12, tzinfo=timezone.utc),
                updated_at=datetime(2026, 10, 12, tzinfo=timezone.utc),
            ))
        db.commit()
    try:
        yield case
    finally:
        evidence = os.environ.get('ROUTER_WIRING_EVIDENCE_DIR')
        if evidence:
            target = Path(evidence)
            target.mkdir(parents=True, exist_ok=True)
            name = ''.join(c if c.isalnum() or c in '-_' else '_' for c in request.node.name)
            (target / (name + '.json')).write_text(json.dumps(case.requests, indent=2), encoding='utf8')


@pytest.mark.parametrize('method,path', ENDPOINTS)
def test_real_app_exposes_library_contract(method, path):
    assert method.lower() in app.openapi()['paths'].get(path, {}), (method, path)


@pytest.mark.parametrize('method,path', ENDPOINTS)
def test_real_app_library_requires_real_principal(real_app, method, path):
    path = path.replace('{music_id}', 'own-a')
    for headers in [None, {'Authorization': 'Bearer invalid-synthetic'}]:
        error(real_app.call(method, path, headers=headers), 401, 'UNAUTHENTICATED')


def test_real_app_history_detail_and_favorites_are_owner_scoped(real_app):
    h = real_app.headers
    page = data(real_app.call('GET', '/api/v3/me/music-assets', headers=h))
    assert {card['music_id'] for card in page['items']} == {'own-a', 'own-b'}
    assert all(set(card) == CARD_FIELDS and card['duration_seconds'] is None for card in page['items'])
    detail = data(real_app.call('GET', '/api/v3/music/assets/own-a', headers=h))
    assert set(detail) == {'card', 'audio', 'source_contexts', 'selected_context_id', 'history_explanation'}
    assert detail['audio'] == {'availability': 'ready', 'duration_seconds': None, 'format': 'wav'}
    assert detail['source_contexts'] == [] and detail['selected_context_id'] is None
    assert detail['history_explanation'] is None
    assert data(real_app.call('GET', '/api/v3/me/music-favorites', headers=h))['items'] == []
    assert real_app.epoch() == 0


@pytest.mark.parametrize('music_id', ['foreign', 'unclaimed', 'absent'])
def test_real_app_cross_owner_and_missing_reads_writes_are_same_404(real_app, music_id):
    h = real_app.headers
    for method, suffix, body in [
        ('GET', '', None), ('PATCH', '/title', {'user_title': 'Synthetic', 'expected_version': 0}),
        ('POST', '/playback-events', {'event_id': 'synthetic-event', 'event_type': 'play_started', 'source_context_id': None}),
    ]:
        error(real_app.call(method, '/api/v3/music/assets/' + music_id + suffix, headers=h, body=body), 404, 'RESOURCE_NOT_FOUND')
    assert real_app.epoch() == 0


def test_real_app_expired_identity_is_denied(real_app):
    with real_app.factory.begin() as db:
        db.execute(text("UPDATE user_identities SET guest_expires_at='2000-01-01' WHERE internal_user_pk=:owner"), {'owner': real_app.owner})
    error(real_app.call('GET', '/api/v3/me/music-assets', headers=real_app.headers), 401, 'UNAUTHENTICATED')


def test_real_app_favorite_epoch_cursor_scope_and_staleness(real_app):
    h = real_app.headers
    first = data(real_app.call('GET', '/api/v3/me/music-assets?limit=1', headers=h))
    assert len(first['items']) == 1 and first['has_more'] is True
    cursor = first['next_cursor']
    second = data(real_app.call('GET', '/api/v3/me/music-assets?limit=1&cursor=' + cursor, headers=h))
    assert len(second['items']) == 1 and second['items'][0]['music_id'] != first['items'][0]['music_id']
    error(real_app.call('GET', '/api/v3/me/music-assets?limit=1&cursor=' + cursor, headers=real_app.other_headers), 400, 'INVALID_CURSOR')
    error(real_app.call('GET', '/api/v3/me/music-favorites?limit=1&cursor=' + cursor, headers=h), 400, 'INVALID_CURSOR')
    error(real_app.call('GET', '/api/v3/me/music-assets?cursor=malformed', headers=h), 400, 'INVALID_CURSOR')
    favorite = {'music_ref': {'music_id': 'own-a', 'source_type': 'matched'}}
    data(real_app.call('PUT', '/api/v3/favorites', headers=h, body=favorite))
    assert real_app.epoch() == 1
    data(real_app.call('PUT', '/api/v3/favorites', headers=h, body=favorite))
    assert real_app.epoch() == 1
    error(real_app.call('GET', '/api/v3/me/music-assets?limit=1&cursor=' + cursor, headers=h), 409, 'LIBRARY_CURSOR_STALE')
    assert [c['music_id'] for c in data(real_app.call('GET', '/api/v3/me/music-favorites', headers=h))['items']] == ['own-a']
    data(real_app.call('DELETE', '/api/v3/favorites/own-a', headers=h))
    assert real_app.epoch() == 2
    data(real_app.call('DELETE', '/api/v3/favorites/own-a', headers=h))
    assert real_app.epoch() == 2


def test_real_app_title_cas_and_event_idempotency_keep_asset_immutable(real_app):
    h = real_app.headers
    before = data(real_app.call('GET', '/api/v3/music/assets/own-a', headers=h))['card']
    title = data(real_app.call('PATCH', '/api/v3/music/assets/own-a/title', headers=h, body={'user_title': 'Synthetic alias', 'expected_version': 0}))
    assert title['metadata_version'] == 1 and title['display_title'] == 'Synthetic alias'
    error(real_app.call('PATCH', '/api/v3/music/assets/own-a/title', headers=h, body={'user_title': 'stale', 'expected_version': 0}), 409, 'TITLE_VERSION_CONFLICT')
    cleared = data(real_app.call('PATCH', '/api/v3/music/assets/own-a/title', headers=h, body={'user_title': None, 'expected_version': 1}))
    assert cleared['metadata_version'] == 2 and cleared['user_title'] is None
    assert cleared['display_title'] == before['default_title']
    event = {'event_id': 'synthetic-onplay', 'event_type': 'play_started', 'source_context_id': None}
    epoch = real_app.epoch()
    first = data(real_app.call('POST', '/api/v3/music/assets/own-a/playback-events', headers=h, body=event), 201)
    assert first['replayed'] is False and real_app.epoch() == epoch + 1
    repeat = data(real_app.call('POST', '/api/v3/music/assets/own-a/playback-events', headers=h, body=event))
    assert repeat['replayed'] is True and repeat['occurred_at'] == first['occurred_at']
    assert real_app.epoch() == epoch + 1
    error(real_app.call('POST', '/api/v3/music/assets/own-b/playback-events', headers=h, body=event), 409, 'PLAYBACK_EVENT_CONFLICT')
    bad_context = {**event, 'event_id': 'synthetic-wrong-context', 'source_context_id': 'other-context'}
    error(real_app.call('POST', '/api/v3/music/assets/own-a/playback-events', headers=h, body=bad_context), 422, 'CONTEXT_NOT_AVAILABLE')
    with real_app.factory() as db:
        asset = db.get(MusicAsset, 'own-a')
        assert asset.title == 'Synthetic original' and asset.checksum == 'sha256:own-a'
        assert db.query(MusicPlaybackEvent).count() == 1


@pytest.mark.parametrize('status,expiry,availability', [('deleted', None, 'deleted'), ('quarantined', None, 'quarantined'), ('ready', '2000-01-01', 'expired')])
def test_real_app_unavailable_detail_stream_and_event_agree(real_app, status, expiry, availability):
    with real_app.factory.begin() as db:
        db.execute(text('UPDATE music_assets SET playable_status=:status,retention_expires_at=:expiry WHERE music_asset_id=\'own-a\''), {'status': status, 'expiry': expiry})
    h = real_app.headers
    detail = data(real_app.call('GET', '/api/v3/music/assets/own-a', headers=h))
    assert detail['card']['availability'] == detail['audio']['availability'] == availability
    error(real_app.call('GET', '/api/v3/music/assets/own-a/stream', headers=h), 404, 'RESOURCE_NOT_AVAILABLE')
    error(real_app.call('POST', '/api/v3/music/assets/own-a/playback-events', headers=h, body={'event_id': 'unavailable', 'event_type': 'play_started'}), 404, 'RESOURCE_NOT_AVAILABLE')
    assert real_app.epoch() == 0


def test_real_app_stream_range_and_old_route_auth_contracts(real_app):
    h = real_app.headers
    path = '/api/v3/music/assets/own-a/stream'
    response = real_app.call('GET', path, headers=h)
    assert response.status_code == 200 and response.content == real_app.audio
    part = real_app.call('GET', path, headers={**h, 'Range': 'bytes=0-31'})
    assert part.status_code == 206 and part.content == real_app.audio[:32]
    assert part.headers['content-range'] == f'bytes 0-31/{len(real_app.audio)}'
    over = real_app.call('GET', path, headers={**h, 'Range': f'bytes={len(real_app.audio)}-'})
    assert over.status_code == 416 and over.headers['content-range'] == f'bytes */{len(real_app.audio)}'
    assert real_app.call('GET', path, headers={**h, 'Range': 'bytes=10-5'}).status_code == 400
    assert real_app.call('HEAD', path, headers=h).status_code == 405
    for method, route in [('GET', '/api/v3/music/generations/unknown'), ('POST', '/api/v3/music/generations/unknown/cancel'), ('POST', '/api/v3/feedback'), ('PUT', '/api/v3/favorites')]:
        error(real_app.call(method, route), 401, 'UNAUTHENTICATED')
    assert real_app.epoch() == 0
