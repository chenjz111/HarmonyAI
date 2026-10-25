"""Actual app/Guest auth/database peer, invoked only by the isolated launcher."""
import base64
import json
import sys
from pathlib import Path


def test_frontend_journey(tmp_path, monkeypatch):
    serve_journey(tmp_path,monkeypatch)


def serve_journey(tmp_path,monkeypatch,*,account=False):
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import Session,sessionmaker
    from fastapi.testclient import TestClient
    from backend.app.core import database
    from backend.app.main import app
    from backend.app.core.database import get_db
    from tests.api.v3.test_int2_0012_contract import seed

    engine = create_engine(f'sqlite:///{tmp_path / "journey.sqlite"}', connect_args={'check_same_thread':False})
    @event.listens_for(engine,'connect')
    def enable_foreign_keys(connection, _record):
        connection.execute('PRAGMA foreign_keys=ON')
    monkeypatch.setattr(database, 'engine', engine)
    database.init_database()
    with engine.begin() as db:
        db.exec_driver_sql("INSERT INTO users(id,openid) VALUES(6,'synthetic-reserved')")
    media = tmp_path / 'media'
    media.mkdir()
    # Resolve the approved test WAV from the source manifest, never a Provider.
    manifest = json.loads(Path('docs/sprint7/S6_ASSET_RESTORE_MANIFEST_20261025.json').read_text(encoding='utf8'))
    audio = next(Path(row['path']) for row in manifest['restored_files'] if row['path'].endswith('.wav'))
    (media / 'music_shared.mp3').write_bytes(audio.read_bytes())
    monkeypatch.setenv('HARMONY_MEDIA_ROOT', str(media))
    monkeypatch.setenv('HARMONY_LIBRARY_CURSOR_SECRET', 'synthetic-integration-cursor-key-0123456789')
    previous = dict(app.dependency_overrides)
    def isolated_db():
        with Session(engine, autoflush=False) as db:
            yield db
    app.dependency_overrides[get_db] = isolated_db
    routes_before=list(app.router.routes)
    if account:
        from backend.app.routers.v3.account_router import build_account_router
        from tests.api.v3.test_account_session_r1 import service
        app.include_router(build_account_router(factory=sessionmaker(bind=engine),service_provider=service,
            native_security_accepted=True),prefix='/api/v3')
    seeded = False
    requests = 0
    try:
        with TestClient(app,base_url='https://testserver',client=('192.0.2.1',1234)) as client:
            print('S7_READY', flush=True)
            for line in sys.stdin:
                message = json.loads(line)
                if message == {'done':True}:
                    break
                assert set(message) <= {'id','method','path','data','header'}
                assert message['method'] in {'GET','POST','PUT','PATCH','DELETE'}
                assert message['path'].startswith('/api/v3/') and '://' not in message['path']
                if account and message['path']=='/api/v3/__test__/expire-guest':
                    from datetime import datetime,timedelta,timezone
                    from backend.app.services.v3.auth_service import _resolve_principal
                    from backend.app.models.v3.identity import UserIdentity
                    token=message['header']['Authorization'].split()[1]
                    with Session(engine) as db:
                        principal=_resolve_principal(token,db)
                        assert principal.auth_type=='guest'
                        db.get(UserIdentity,principal.internal_user_pk).guest_expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)
                        db.commit()
                    print('S7_RESPONSE '+json.dumps({'id':message['id'],'statusCode':200,'data':{'ok':True}}),flush=True)
                    continue
                if account and message['path']=='/api/v3/__test__/expire-session':
                    # Fixed test-only fault; not a route, arbitrary SQL or auth override.
                    from datetime import datetime,timedelta,timezone
                    from backend.app.services.v3.auth_service import _resolve_principal,_decode_verified_claims
                    from backend.app.models.v3.identity import AuthSession
                    token=message['header']['Authorization'].split()[1]
                    with Session(engine) as db:
                        _resolve_principal(token,db)
                        sid=_decode_verified_claims(token)['sid']
                        session=db.get(AuthSession,sid)
                        session.created_at=datetime.now(timezone.utc)-timedelta(days=2)
                        session.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)
                        db.commit()
                    print('S7_RESPONSE '+json.dumps({'id':message['id'],'statusCode':200,'data':{'ok':True}}),flush=True)
                    continue
                response = client.request(message['method'], message['path'],
                    json=message.get('data'), headers=message.get('header', {}))
                requests += 1
                if message['path'] == '/api/v3/auth/guest' and not seeded:
                    assert response.status_code == 201
                    with engine.begin() as db:
                        db.exec_driver_sql("INSERT INTO sessions(id,user_id,session_id,status) VALUES(1,7,'sess_legacy','active')")
                        seed(db)
                    seeded = True
                if response.headers.get('content-type','').startswith('application/json'):
                    data = response.json()
                else:
                    data = {'bytes_base64':base64.b64encode(response.content).decode()}
                print('S7_RESPONSE '+json.dumps({'id':message['id'],'statusCode':response.status_code,
                    'data':data,'headers':dict(response.headers)}), flush=True)
            else:
                raise AssertionError('frontend disconnected without completion')
        assert requests >= 20 and seeded
        with engine.connect() as db:
            assert db.exec_driver_sql('PRAGMA foreign_keys').scalar_one() == 1
            assert db.exec_driver_sql('PRAGMA foreign_key_check').fetchall() == []
            assert db.exec_driver_sql('SELECT count(*) FROM generation_tasks').scalar_one() == 3
            assert db.exec_driver_sql('SELECT count(*) FROM music_assets').scalar_one() == 1
        print('S7_BACKEND_VERIFIED', flush=True)
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
        app.router.routes[:]=routes_before
        engine.dispose()
