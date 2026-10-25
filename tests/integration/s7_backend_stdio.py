"""Actual app/Guest auth/database peer, invoked only by the isolated launcher."""
import base64
import json
import sys
from pathlib import Path


def test_frontend_journey(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import Session
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
    seeded = False
    requests = 0
    try:
        with TestClient(app) as client:
            print('S7_READY', flush=True)
            for line in sys.stdin:
                message = json.loads(line)
                if message == {'done':True}:
                    break
                assert set(message) <= {'id','method','path','data','header'}
                assert message['method'] in {'GET','POST','PUT','PATCH','DELETE'}
                assert message['path'].startswith('/api/v3/') and '://' not in message['path']
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
        engine.dispose()
