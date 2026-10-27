"""Opt-in isolated USB Guest acceptance server; never used for production.

Initial creation requires a NEW external runtime directory. Resume requires its
marker and private test key; it never reads project .env or provider credentials.
"""
import argparse
import asyncio
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import socket
import sqlite3
import subprocess
import sys
import wave

ROOT = Path(__file__).resolve().parents[2]
ID = r'[A-Za-z0-9_-]{1,128}'
RULES = (
    ('GET', r'/health'), ('POST', r'/api/v3/auth/guest'), ('GET', r'/api/v3/auth/identity'),
    ('POST', r'/api/v3/sessions'), ('GET', rf'/api/v3/sessions/{ID}'),
    ('GET', r'/api/v3/me/music-assets'), ('GET', r'/api/v3/me/music-favorites'),
    ('PUT', r'/api/v3/favorites'), ('DELETE', rf'/api/v3/favorites/{ID}'),
    ('GET', rf'/api/v3/music/assets/{ID}'), ('GET', rf'/api/v3/music/assets/{ID}/(?:stream|analysis)'),
    ('PATCH', rf'/api/v3/music/assets/{ID}/title'), ('POST', rf'/api/v3/music/assets/{ID}/playback-events'),
    ('POST', r'/api/v3/feedback-records'), ('GET', r'/api/v3/feedback-records'),
    ('GET', rf'/api/v3/feedback-records/{ID}'), ('DELETE', rf'/api/v3/feedback-records/{ID}'),
    ('POST', r'/api/v3/me/feedback-evidence/clear'),
)


def allowed_request(method, path):
    return any(method == m and re.fullmatch(pattern, path) for m, pattern in RULES)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime',required=True,type=Path)
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args()
    runtime=args.runtime.resolve()
    evidence_root=(Path.home()/'HarmonyAI-s7-m1-evidence-20261024').resolve()
    if not runtime.is_relative_to(evidence_root) or runtime == evidence_root or runtime.is_relative_to(ROOT):
        parser.error('runtime must be a separate direct or nested path under the dedicated evidence root')
    marker=runtime/'usb-guest-library.json';keypath=runtime/'private'/'jwt.key';dbpath=runtime/'library.sqlite'
    def reject_links():
        for path in (runtime, marker, runtime/'private', keypath, runtime/'media', runtime/'media'/'music_shared.wav',dbpath):
            if path.is_symlink() or (hasattr(path,'is_junction') and path.is_junction()):parser.error('runtime links are forbidden')
            if path.exists() and not path.resolve().is_relative_to(runtime):parser.error('runtime path escaped')
    if args.resume:
        reject_links()
        if not marker.is_file() or not keypath.is_file() or not dbpath.is_file():parser.error('existing isolated marker, database and key required')
        record=json.loads(marker.read_text(encoding='utf8'))
        if set(record)!={'schema','runtime','instance'} or record['schema']!='s7-usb-guest-library-v1' or record['runtime']!=str(runtime):parser.error('runtime marker mismatch')
        try:
            with sqlite3.connect(dbpath.as_uri()+'?mode=ro',uri=True) as check:
                if check.execute('PRAGMA quick_check').fetchone()!=('ok',):parser.error('isolated database integrity failure')
                row=check.execute('SELECT instance,key_hash FROM usb_runtime_identity').fetchone()
                supplied=hashlib.sha256(keypath.read_bytes()).hexdigest()
                if not row or row[0]!=record['instance'] or not hmac.compare_digest(row[1],supplied):parser.error('isolated database or test key identity mismatch')
                owner=check.execute('SELECT id FROM users WHERE id=7').fetchone()
                seeded=check.execute("SELECT 1 FROM music_assets WHERE music_asset_id='music_shared'").fetchone()
                if bool(owner)!=bool(seeded):parser.error('interrupted synthetic guest provisioning requires manual investigation')
        except sqlite3.Error:parser.error('isolated database unavailable or incomplete')
    else:
        if runtime.exists():parser.error('new runtime must not already exist')
        runtime.mkdir(parents=True);private=runtime/'private';private.mkdir();(runtime/'media').mkdir()
        if os.name=='nt':
            import getpass
            subprocess.run(['icacls',str(runtime),'/inheritance:r','/grant:r',getpass.getuser()+':(OI)(CI)F','SYSTEM:(OI)(CI)F'],check=True,capture_output=True)
        keypath.write_text(secrets.token_urlsafe(48),encoding='utf8')
        instance=secrets.token_hex(24)
        with sqlite3.connect(dbpath) as initial:
            initial.execute('CREATE TABLE usb_runtime_identity(instance TEXT NOT NULL,key_hash TEXT NOT NULL)')
            initial.execute('INSERT INTO usb_runtime_identity(instance,key_hash) VALUES(?,?)',(instance,hashlib.sha256(keypath.read_bytes()).hexdigest()))
        marker.write_text(json.dumps({'schema':'s7-usb-guest-library-v1','runtime':str(runtime),'instance':instance}),encoding='utf8')
        reject_links()
    secret=keypath.read_text(encoding='utf8')
    if len(secret)<32:parser.error('invalid isolated test key')
    allowed={'PATH','SYSTEMROOT','WINDIR','PATHEXT','TEMP','TMP','LANG','LC_ALL','LC_CTYPE','TZ'}
    clean={k:v for k,v in os.environ.items() if k.upper() in allowed}
    os.environ.clear();os.environ.update(clean)
    os.environ.update(APP_ENV='test',DEBUG='false',DATABASE_URL='sqlite:///'+str(runtime/'library.sqlite'),
        JWT_SECRET_KEY=secret,JWT_PREVIOUS_SECRET_KEYS='[]',JWT_ALGORITHM='HS256',CORS_ORIGINS='[]',
        HARMONYAI_REAL_AGENTS='false',MUSIC_PROVIDER='not-configured',HARMONY_MEDIA_ROOT=str(runtime/'media'),
        HARMONY_LIBRARY_CURSOR_SECRET=hashlib.sha256(('usb-cursor:'+secret).encode()).hexdigest(),PYTHONDONTWRITEBYTECODE='1')
    os.chdir(runtime);sys.path.insert(0,str(ROOT));sys.dont_write_bytecode=True
    spec=importlib.util.spec_from_file_location('sqlite_containment',ROOT/'tools/ci/guarded_pytest.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    guard=module.OfflineGuard(runtime,False);guard.protect_sqlite_constructors()
    if sys.platform=='win32':
        import platform
        def no_wmi(*unused,**kwargs):raise OSError('WMI disabled in isolated runtime')
        platform._wmi_query=no_wmi
        native=sys.getwindowsversion();version='.'.join(map(str,native.platform_version or native[:3]))
        platform._syscmd_ver=lambda *unused,**kwargs:('Windows','',version)
    def audit(event,values):
        if event.startswith('sqlite3.'):return guard.audit(event,values)
        if event in module.SOCKET_PROCESS_EVENTS:
            if guard.internal_socketpair(event,values,sys._getframe(1)):return
            if event=='socket.bind' and values[1]==('127.0.0.1',8000) and values[0].family==socket.AF_INET:return
            raise RuntimeError('USB acceptance denies outbound network and subprocesses')
    sys.addaudithook(audit)
    from backend.app.main import app
    from backend.app.core.database import engine
    from backend.app.services.v3.auth_service import _resolve_principal
    from sqlalchemy.orm import Session
    from tests.api.v3.test_int2_0012_contract import seed
    from starlette.responses import JSONResponse
    wav=ROOT/'frontend/static/music/jiao-demo.wav'
    audio=wav.read_bytes()
    with wave.open(str(wav),'rb') as w:duration=round(w.getnframes()/w.getframerate())
    media_file=runtime/'media'/'music_shared.wav'
    if media_file.exists():
        if media_file.read_bytes()!=audio:raise RuntimeError('isolated media differs from approved fixture')
    else:
        with media_file.open('xb') as output:output.write(audio)
    lock=asyncio.Lock()

    class Scope:
        async def __call__(self,scope,receive,send):
            if scope['type']!='http':return await app(scope,receive,send)
            if not allowed_request(scope['method'],scope['path']):
                return await JSONResponse({'ok':False,'error':{'code':'USB_SCOPE_CLOSED','message':'此非生产验收不开放该操作'}},status_code=503)(scope,receive,send)
            if scope['method']!='POST' or scope['path']!='/api/v3/auth/guest':return await app(scope,receive,send)
            async with lock:
                with engine.begin() as db:
                    owner=db.exec_driver_sql('SELECT id FROM users WHERE id=7').first()
                    seeded=db.exec_driver_sql("SELECT 1 FROM music_assets WHERE music_asset_id='music_shared'").first()
                    if bool(owner)!=bool(seeded):
                        return await JSONResponse({'ok':False,'error':{'code':'USB_PROVISIONING_INCOMPLETE','message':'测试身份初始化未完成，请检查隔离环境'}},status_code=503)(scope,receive,send)
                    if not db.exec_driver_sql('SELECT id FROM users WHERE id=6').first():
                        db.exec_driver_sql("INSERT INTO users(id,openid) VALUES(6,'usb-reserved')")
                response=[]
                async def collect(message):response.append(message)
                await app(scope,receive,collect)
                start=next((m for m in response if m['type']=='http.response.start'),{})
                if start.get('status')==201:
                    payload=b''.join(m.get('body',b'') for m in response if m['type']=='http.response.body')
                    token=json.loads(payload)['data']['access_token']
                    with Session(engine) as db:principal=_resolve_principal(token,db)
                    if principal.internal_user_pk==7:
                        with engine.begin() as db:
                            if not db.exec_driver_sql("SELECT 1 FROM music_assets WHERE music_asset_id='music_shared'").first():
                                db.exec_driver_sql("INSERT INTO sessions(id,user_id,session_id,status) VALUES(1,7,'usb-synthetic-session','active')")
                                seed(db)
                                db.exec_driver_sql("UPDATE music_assets SET title='测试音频（非生成结果）',storage_key=?,format='wav',duration_seconds=?,checksum=? WHERE music_asset_id='music_shared'",('music_shared.wav',duration,'sha256:'+hashlib.sha256(audio).hexdigest()))
                                db.exec_driver_sql("INSERT INTO music_library_state(owner_internal_user_pk,music_asset_id,user_title) VALUES(7,'music_shared','测试音频（非生成结果）')")
                for message in response:await send(message)
    import uvicorn
    uvicorn.run(Scope(),host='127.0.0.1',port=8000,proxy_headers=False,access_log=False,log_level='warning',loop='asyncio',ws='none',lifespan='on')


if __name__=='__main__':main()
