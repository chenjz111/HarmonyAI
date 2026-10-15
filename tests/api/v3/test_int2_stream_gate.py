"""Stream authorization and actual HTTP bytes, on migrated temporary SQLite.

No real service/audio/patient data. Library router is mounted only on this test
application; production registration remains unchanged.
"""
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from tests.api.v3.test_int2_0012_contract import upgraded, seed
from tests.api.v3.test_generation import _mp3_bytes
from backend.app.core import v3_migrations as migrations
from backend.app.core.database import get_db
from backend.app.routers.v3 import auth_router, generation_router, music_library_router
from backend.app.routers.v3.transport import V3APIError, v3_api_error_handler
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.services.v3 import generation_service
from backend.app.services.v3.auth_service import get_current_v3_principal


@pytest.fixture
def stream_case(upgraded, tmp_path, monkeypatch):
    media = tmp_path / 'controlled-media'
    media.mkdir()
    audio = _mp3_bytes(seconds=1)
    with upgraded.begin() as connection:
        seed(connection)
        for music_id, owner in [('owned', 7), ('foreign', 1), ('unclaimed', None), ('favorite_only', None), ('success_link', None)]:
            connection.execute(text("INSERT INTO music_assets(music_asset_id,owner_internal_user_pk,source_type,catalog_track_id,title,storage_key,format,duration_seconds,checksum,playable_status,created_at,updated_at) VALUES(:id,:owner,'matched',:id,'Synthetic',:storage,'mp3',240,:checksum,'ready','2026-10-12 08:00:00','2026-10-12 08:00:00')"), {
                'id': music_id, 'owner': owner, 'storage': music_id+'.mp3', 'checksum': 'sha256:'+music_id,
            })
        connection.execute(text("INSERT INTO favorites(favorite_id,internal_user_pk,music_asset_id) VALUES('fav-only',7,'favorite_only')"))
        connection.execute(text("INSERT INTO generation_tasks(task_id,internal_user_pk,session_row_id,prescription_id,idempotency_key,status,progress_indeterminate,message_code,fallback_applied,music_asset_id) VALUES('success-task',7,1,'p_ctx_a','success-task','succeeded',0,'synthetic',0,'success_link')"))
        connection.execute(text("UPDATE music_assets SET source_type='generated',generation_task_id='success-task' WHERE music_asset_id='success_link'"))
    migrations.apply_v3_migrations(upgraded)
    for music_id in ('music_shared','owned','foreign','unclaimed','favorite_only','success_link'):
        (media / f'{music_id}.mp3').write_bytes(audio)
    monkeypatch.setenv('HARMONY_MEDIA_ROOT', str(media))
    monkeypatch.setenv('HARMONY_LIBRARY_CURSOR_SECRET', 'synthetic-stream-cursor-secret-0123456789')
    factory = sessionmaker(bind=upgraded)
    app = FastAPI()
    app.add_exception_handler(V3APIError, v3_api_error_handler)
    for module in (auth_router, generation_router, music_library_router):
        app.include_router(module.router, prefix='/api/v3')
    def test_db():
        with factory() as db:
            yield db
    def no_provider():
        raise AssertionError('Stream must not resolve a music Provider')
    app.dependency_overrides[get_db] = test_db
    app.dependency_overrides[generation_router.get_music_provider] = no_provider
    with TestClient(app) as client:
        yield client, app, factory, media, audio


def owner(app, internal_pk=7):
    app.dependency_overrides[get_current_v3_principal] = lambda: AuthPrincipal(
        internal_user_pk=internal_pk, public_user_id=f'synthetic-{internal_pk}',
        auth_type='registered', guest_expires_at=None,
    )


def url(music_id):
    return f'/api/v3/music/assets/{music_id}/stream'


def test_null_owner_without_legal_task_is_denied(stream_case):
    client, app, _, _, _ = stream_case
    owner(app)
    response = client.get(url('unclaimed'))
    assert response.status_code == 404
    assert response.json()['error']['code'] == 'RESOURCE_NOT_FOUND'


@pytest.mark.parametrize('music_id', ['owned', 'music_shared', 'success_link'])
def test_owned_or_own_terminal_task_can_stream_real_bytes(stream_case, music_id):
    client, app, _, media, audio = stream_case
    owner(app)
    response = client.get(url(music_id))
    assert response.status_code == 200 and response.content == audio
    assert response.headers['content-type'] == 'audio/mpeg'
    assert int(response.headers['content-length']) == len(audio)
    assert response.headers['accept-ranges'] == 'bytes'
    assert str(media) not in str(response.headers)


@pytest.mark.parametrize('music_id,principal', [('foreign',7), ('owned',1), ('favorite_only',7), ('unclaimed',7), ('music_shared',999)])
def test_absent_and_unauthorized_share_404_without_probing_files(stream_case, monkeypatch, music_id, principal):
    from backend.app.services.v3 import music_library_access
    client, app, _, _, _ = stream_case
    owner(app, principal)
    def forbidden_probe(*args, **kwargs):
        pytest.fail('unauthorized stream must not inspect availability or storage')
    monkeypatch.setattr(music_library_access, 'library_availability', forbidden_probe)
    monkeypatch.setattr(generation_service, '_resolve_asset_path', forbidden_probe)
    missing = client.get(url('absent'))
    denied = client.get(url(music_id), headers={'Range':'bytes=0-31'})
    assert missing.status_code == denied.status_code == 404
    assert missing.json()['error'] == denied.json()['error']
    assert denied.json()['error']['code'] == 'RESOURCE_NOT_FOUND'


@pytest.mark.parametrize('status', ['failed','cancelled','queued','running'])
def test_nonterminal_or_failed_task_never_grants_catalog_access(stream_case, status):
    from sqlalchemy.exc import IntegrityError
    client, app, factory, _, _ = stream_case
    owner(app)
    sql=text("INSERT INTO generation_tasks(task_id,internal_user_pk,session_row_id,prescription_id,idempotency_key,status,progress_indeterminate,message_code,fallback_applied,music_asset_id) VALUES('invalid-task',7,1,'p_ctx_a','invalid-task',:status,0,'synthetic',0,:asset)")
    with factory.begin() as db:
        db.execute(sql, {'status':status, 'asset':None})
    # Real existing CHECK forbids falsely linked unsuccessful task fixtures.
    with pytest.raises(IntegrityError):
        with factory.begin() as db:
            db.execute(text("UPDATE generation_tasks SET music_asset_id='unclaimed' WHERE task_id='invalid-task'"))
    assert client.get(url('unclaimed')).status_code == 404


@pytest.mark.parametrize('status,expired,expected', [
    ('ready',True,'expired'), ('expired',False,'expired'),
    ('deleted',True,'deleted'), ('quarantined',True,'quarantined'),
])
def test_list_detail_stream_agree_on_unavailable_status(stream_case, status, expired, expected):
    client, app, factory, _, _ = stream_case
    owner(app)
    with factory.begin() as db:
        db.execute(text("UPDATE music_assets SET playable_status=:status,retention_expires_at=:expiry WHERE music_asset_id='owned'"), {
            'status':status, 'expiry':'2000-01-01 00:00:00' if expired else None,
        })
    card=next(c for c in client.get('/api/v3/me/music-assets').json()['data']['items'] if c['music_id']=='owned')
    detail=client.get('/api/v3/music/assets/owned').json()['data']
    assert card['availability'] == detail['audio']['availability'] == expected
    response=client.get(url('owned'), headers={'Range':'bytes=0-31'})
    assert response.status_code == 404
    assert response.json()['error']['code'] == 'RESOURCE_NOT_AVAILABLE'


@pytest.mark.parametrize('kind', ['missing','directory','empty','traversal','absolute_outside','url','unc','device','ads'])
def test_unsafe_or_missing_storage_is_never_streamed(stream_case, kind, monkeypatch):
    client, app, factory, media, _ = stream_case
    owner(app)
    outside=media.parent/'outside.mp3'
    outside.write_bytes(b'private synthetic sentinel')
    directory=media/'directory.mp3'
    directory.mkdir()
    keys={'missing':'missing.mp3','directory':'directory.mp3','empty':'',
          'traversal':'../outside.mp3','absolute_outside':str(outside),
          'url':'https://example.invalid/audio.mp3','unc':r'\\example.invalid\share\audio.mp3',
          'device':r'\\?\C:\synthetic.mp3','ads':'owned.mp3:hidden'}
    with factory.begin() as db:
        db.execute(text("UPDATE music_assets SET storage_key=:key WHERE music_asset_id='owned'"), {'key':keys[kind]})
    original_open=Path.open
    def protected_open(path,*args,**kwargs):
        assert path != outside, 'must not open unapproved storage'
        return original_open(path,*args,**kwargs)
    monkeypatch.setattr(Path,'open',protected_open)
    detail=client.get('/api/v3/music/assets/owned').json()['data']
    assert detail['card']['availability'] == detail['audio']['availability'] == 'missing'
    response=client.get(url('owned'))
    assert response.status_code == 404
    assert response.json()['error']['code'] == 'RESOURCE_NOT_AVAILABLE'
    assert b'private synthetic sentinel' not in response.content


def test_actual_read_failure_is_safe_on_windows(stream_case, monkeypatch):
    client, app, _, media, _ = stream_case
    owner(app)
    original_open=Path.open
    def denied_open(path,*args,**kwargs):
        if path == (media/'owned.mp3'):
            raise PermissionError('synthetic read denied')
        return original_open(path,*args,**kwargs)
    monkeypatch.setattr(Path,'open',denied_open)
    response=client.get(url('owned'))
    assert response.status_code==404 and response.json()['error']['code']=='RESOURCE_NOT_AVAILABLE'


def test_absolute_path_inside_controlled_media_remains_supported(stream_case):
    client, app, factory, media, audio = stream_case
    owner(app)
    with factory.begin() as db:
        db.execute(text("UPDATE music_assets SET storage_key=:key WHERE music_asset_id='owned'"), {'key':str(media/'owned.mp3')})
    assert client.get(url('owned')).content == audio


def test_symlink_escape_is_denied_without_opening_target(stream_case, monkeypatch):
    client, app, factory, media, _ = stream_case
    owner(app)
    outside=media.parent/'private.mp3'
    outside.write_bytes(b'private synthetic sentinel')
    link=media/'escape.mp3'
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip('Windows symlink creation privilege unavailable; canonical escape tested separately')
    with factory.begin() as db:
        db.execute(text("UPDATE music_assets SET storage_key='escape.mp3' WHERE music_asset_id='owned'"))
    original_open=Path.open
    def protected_open(path,*args,**kwargs):
        assert path.resolve() != outside.resolve(), 'must not open escaped symlink target'
        return original_open(path,*args,**kwargs)
    monkeypatch.setattr(Path,'open',protected_open)
    assert client.get(url('owned')).status_code==404


def test_canonical_escape_rejected_without_symlink_privilege(stream_case, monkeypatch):
    client, app, _, media, _ = stream_case
    owner(app)
    outside=media.parent/'outside.mp3'
    outside.write_bytes(b'private synthetic sentinel')
    original_resolve=Path.resolve
    def redirect(path,*args,**kwargs):
        if path == (media/'owned.mp3'):
            return outside
        return original_resolve(path,*args,**kwargs)
    monkeypatch.setattr(Path,'resolve',redirect)
    original_open=Path.open
    def protected_open(path,*args,**kwargs):
        assert path != outside, 'canonical escape must be denied before opening'
        return original_open(path,*args,**kwargs)
    monkeypatch.setattr(Path,'open',protected_open)
    assert client.get(url('owned')).status_code==404


def test_authenticated_jwt_required_and_valid_guest_can_stream(stream_case):
    from backend.app.models.v3.identity import UserIdentity
    client, app, factory, _, audio = stream_case
    assert client.get(url('owned')).status_code==401
    assert client.get(url('owned'),headers={'Authorization':'Bearer invalid-synthetic-token'}).status_code==401
    issued=client.post('/api/v3/auth/guest').json()['data']
    with factory.begin() as db:
        identity=db.query(UserIdentity).filter(UserIdentity.public_user_id==issued['public_user_id']).one()
        db.execute(text("UPDATE music_assets SET owner_internal_user_pk=:owner WHERE music_asset_id='owned'"), {'owner':identity.internal_user_pk})
    response=client.get(url('owned'),headers={'Authorization':'Bearer '+issued['access_token']})
    assert response.status_code==200 and response.content==audio


def test_ranges_resume_retry_and_no_writes_or_path_leaks(stream_case, caplog):
    client, app, factory, media, audio = stream_case
    owner(app)
    protected=('users','music_assets','generation_tasks','diagnosis_runs','prescription_v3','music_playback_events','owner_music_state','music_library_state')
    def snapshot():
        with factory() as db:
            return {table:db.execute(text(f'SELECT * FROM {table} ORDER BY 1')).all() for table in protected}
    before=snapshot()
    first=client.get(url('owned'))
    for header,start,end in [('bytes=0-99',0,100),('bytes=100-',100,len(audio)),('bytes=-64',len(audio)-64,len(audio))]:
        response=client.get(url('owned'),headers={'Range':header})
        assert response.status_code==206
        assert response.content==audio[start:end]
        assert response.headers['content-range']==f'bytes {start}-{end-1}/{len(audio)}'
        assert int(response.headers['content-length'])==end-start
    prefix=client.get(url('owned'),headers={'Range':'bytes=0-99'}).content
    suffix=client.get(url('owned'),headers={'Range':'bytes=100-'}).content
    assert prefix+suffix==audio
    retry=client.get(url('owned'))
    assert retry.status_code==200 and retry.content==first.content==audio
    invalid=client.get(url('owned'),headers={'Range':f'bytes={len(audio)}-'})
    assert invalid.status_code==416 and invalid.headers['content-range']==f'bytes */{len(audio)}'
    reversed_range=client.get(url('owned'),headers={'Range':'bytes=10-5'})
    assert reversed_range.status_code==400
    matching=client.get(url('owned'),headers={'Range':'bytes=0-99','If-Range':first.headers['etag']})
    assert matching.status_code==206 and matching.content==audio[:100]
    mismatch=client.get(url('owned'),headers={'Range':'bytes=0-99','If-Range':'"synthetic-stale-etag"'})
    assert mismatch.status_code==200 and mismatch.content==audio
    # Existing APIRouter GET is not an implicit HEAD route (known framework contract).
    head=client.head(url('owned'))
    assert head.status_code==405 and head.content==b''
    assert snapshot()==before
    assert str(media) not in caplog.text
    assert str(media) not in str(first.headers)
    assert first.headers['content-type']=='audio/mpeg'
