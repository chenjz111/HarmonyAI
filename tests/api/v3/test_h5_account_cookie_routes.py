"""Real ASGI/SQLite cookie routes, not HTTPS/browser/platform acceptance."""
from datetime import datetime,timedelta,timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session,sessionmaker
import pytest
from tests.api.v3.test_feedback_v31_transactions import ready
from tests.api.v3.test_account_router_r1 import guest,PASSWORD

ORIGIN='https://h5.test.invalid'
REFRESH='__Host-harmonyai-refresh';CSRF='__Host-harmonyai-csrf'


def browser(engine,accepted=True,origins=None):
    from backend.app.services.v3.account_browser_gate import BrowserMutationGate
    from backend.app.services.v3.account_session_service import AccountService
    from backend.app.services.v3.account_password import PasswordPolicy
    from backend.app.routers.v3.account_browser_router import build_browser_account_router
    from backend.app.routers.v3.transport import V3APIError,v3_api_error_handler
    gate=BrowserMutationGate(approved_origins=[ORIGIN],preauth_secret='synthetic-csrf-signing-secret-0123456789')
    service=AccountService(password_policy=PasswordPolicy(blocked_passwords={'passwordpassword'}),browser_gate=gate)
    app=FastAPI();app.add_exception_handler(V3APIError,v3_api_error_handler)
    app.state.synthetic_browser_gate=gate
    app.add_middleware(CORSMiddleware,allow_origins=origins or [ORIGIN],allow_credentials=True,allow_methods=['POST'],allow_headers=['Authorization','Content-Type','X-CSRF-Token'])
    app.include_router(build_browser_account_router(factory=sessionmaker(bind=engine),service_provider=lambda:service,browser_gate=gate,browser_security_accepted=accepted),prefix='/api/v3')
    return TestClient(app,base_url=ORIGIN,client=('192.0.2.1',1234))


def bootstrap(client,*,action='login',token=None):
    response=client.post('/api/v3/auth/browser/bootstrap',headers={'Origin':ORIGIN,**({'Authorization':'Bearer '+token} if token else {})},json={'action':action})
    assert response.status_code==200
    return response.json()['data']['csrf_token']


def bind(client,engine):
    token=guest(engine);csrf=bootstrap(client,action='bind',token=token)
    return client.post('/api/v3/auth/browser/register-bind',headers={'Origin':ORIGIN,'X-CSRF-Token':csrf,'Authorization':'Bearer '+token},json={'username':'browser_user','password':PASSWORD})


def test_default_browser_gate_and_wildcard_cors_never_enable_routes(ready):
    for client in (browser(ready,False),browser(ready,True,['*'])):
        response=client.post('/api/v3/auth/browser/bootstrap',headers={'Origin':ORIGIN},json={'action':'login'})
        assert response.status_code==503


def test_binding_refresh_logout_uses_only_server_refresh_cookie(ready):
    from backend.app.services.v3.auth_service import _resolve_principal
    from backend.app.models.v3.identity import AuthSession
    client=browser(ready);response=bind(client,ready)
    assert response.status_code==201
    first=response.json()['data'];assert first['public_user_id']=='synthetic-7'
    assert not {'refresh_token','csrf_token','internal_user_pk'}.intersection(first)
    cookie=next(value for value in response.headers.get_list('set-cookie') if value.startswith(REFRESH+'='))
    assert 'HttpOnly' in cookie and 'Secure' in cookie and 'SameSite=lax' in cookie and 'Path=/' in cookie and 'Domain' not in cookie
    original=client.cookies.get(REFRESH)
    response=client.post('/api/v3/auth/browser/refresh',headers={'Origin':ORIGIN,'X-CSRF-Token':client.cookies.get(CSRF)},json={})
    assert response.status_code==200 and client.cookies.get(REFRESH)!=original
    assert 'refresh_token' not in response.json()['data']
    access=response.json()['data']['access_token']
    with Session(ready) as db:assert _resolve_principal(access,db).internal_user_pk==7
    response=client.post('/api/v3/auth/browser/logout',headers={'Origin':ORIGIN,'X-CSRF-Token':client.cookies.get(CSRF),'Authorization':'Bearer '+access},json={'all_devices':False})
    assert response.status_code==200 and client.cookies.get(REFRESH) is None
    with Session(ready) as db:assert all(row.revoked_at is not None for row in db.query(AuthSession).all())


@pytest.mark.parametrize('change',[{'Origin':'https://evil.invalid'},{'Origin':'null'},{'X-CSRF-Token':'B'*43}])
def test_untrusted_mutation_does_not_consume_refresh_or_revoke_session(ready,change):
    from backend.app.models.v3.account_security import RefreshProof
    from backend.app.models.v3.identity import AuthSession
    client=browser(ready);assert bind(client,ready).status_code==201
    before=client.cookies.get(REFRESH)
    headers={'Origin':ORIGIN,'X-CSRF-Token':client.cookies.get(CSRF),**change}
    response=client.post('/api/v3/auth/browser/refresh',headers=headers,json={})
    assert response.status_code in (401,403,503)
    assert client.cookies.get(REFRESH)==before
    with Session(ready) as db:
        assert all(row.consumed_at is None for row in db.query(RefreshProof).all())
        assert all(row.revoked_at is None for row in db.query(AuthSession).all())


def test_authenticated_consumed_cookie_replay_revokes_family(ready):
    from backend.app.models.v3.identity import AuthSession
    client=browser(ready);assert bind(client,ready).status_code==201
    old=client.cookies.get(REFRESH)
    assert client.post('/api/v3/auth/browser/refresh',headers={'Origin':ORIGIN,'X-CSRF-Token':client.cookies.get(CSRF)},json={}).status_code==200
    csrf=client.cookies.get(CSRF)
    response=client.post('/api/v3/auth/browser/refresh',headers={'Origin':ORIGIN,'X-CSRF-Token':csrf,'Cookie':f'{REFRESH}={old}; {CSRF}={csrf}'},json={})
    assert response.status_code==401
    with Session(ready) as db:assert all(row.revoked_at is not None for row in db.query(AuthSession).all())


def test_old_refresh_and_its_original_session_csrf_revoke_family(ready):
    from backend.app.models.v3.identity import AuthSession
    client=browser(ready);assert bind(client,ready).status_code==201
    old,csrf=client.cookies.get(REFRESH),client.cookies.get(CSRF)
    assert client.post('/api/v3/auth/browser/refresh',headers={'Origin':ORIGIN,'X-CSRF-Token':csrf},json={}).status_code==200
    response=client.post('/api/v3/auth/browser/refresh',headers={'Origin':ORIGIN,'X-CSRF-Token':csrf,'Cookie':f'{REFRESH}={old}; {CSRF}={csrf}'},json={})
    assert response.status_code==401
    with Session(ready) as db:assert all(row.revoked_at is not None for row in db.query(AuthSession).all())


def test_binding_challenge_cannot_be_reused_for_other_guest(ready):
    from backend.app.models.user import User
    from backend.app.models.v3.identity import UserIdentity
    from backend.app.services.v3.auth_service import _encode_guest_token
    client=browser(ready);a=guest(ready);csrf=bootstrap(client,action='bind',token=a)
    now=datetime.now(timezone.utc)
    with Session(ready) as db:
        db.add(User(id=8,openid='synthetic-browser-other'));db.flush()
        db.add(UserIdentity(internal_user_pk=8,public_user_id='synthetic-8',auth_type='guest',guest_expires_at=now+timedelta(days=7)));db.commit()
    b=_encode_guest_token('synthetic-8',now+timedelta(days=7))
    response=client.post('/api/v3/auth/browser/register-bind',headers={'Origin':ORIGIN,'X-CSRF-Token':csrf,'Authorization':'Bearer '+b},json={'username':'other_user','password':PASSWORD})
    assert response.status_code==401
    with Session(ready) as db:assert all(row.auth_type=='guest' for row in db.query(UserIdentity).all())


def test_signed_out_marker_cannot_abandon_a_usable_httponly_session(ready):
    client=browser(ready);response=bind(client,ready);assert response.status_code==201
    access=response.json()['data']['access_token'];proof=client.cookies.get(REFRESH)
    response=client.post('/api/v3/auth/browser/signed-out',headers={'Origin':ORIGIN},json={})
    assert response.status_code==401 and client.cookies.get(REFRESH)==proof
    assert client.post('/api/v3/auth/browser/logout',headers={'Origin':ORIGIN,'X-CSRF-Token':client.cookies.get(CSRF),'Authorization':'Bearer '+access},json={}).status_code==200
    assert client.post('/api/v3/auth/browser/signed-out',headers={'Origin':ORIGIN},json={}).json()['data']['status']=='signed_out'


def test_expired_or_tampered_preauth_never_authenticates_or_changes_guest(ready,monkeypatch):
    client=browser(ready);token=guest(ready);csrf=bootstrap(client,action='bind',token=token)
    expired=client.app.state.synthetic_browser_gate.preauth(action='bind',binding_token=token,now=datetime.now(timezone.utc)-timedelta(minutes=16))
    for value in (csrf+'x','é',csrf.replace('.bind.','.login.'),expired):
        response=client.post('/api/v3/auth/browser/register-bind',headers={'Origin':ORIGIN,'X-CSRF-Token':value.encode('utf8'),'Cookie':('__Host-harmonyai-preauth='+value).encode('utf8'),'Authorization':'Bearer '+token},json={'username':'browser_user','password':PASSWORD})
        assert response.status_code==401
    from backend.app.models.v3.identity import UserIdentity
    with Session(ready) as db:assert db.get(UserIdentity,7).auth_type=='guest'


def test_default_application_does_not_mount_browser_account_candidates():
    from backend.app.main import app
    assert not any(getattr(route,'path','').startswith('/api/v3/auth/browser/') for route in app.routes)


@pytest.mark.parametrize('accepted',[False,True])
def test_browser_composition_missing_reviewed_source_stays_unavailable(tmp_path,accepted):
    from backend.app.routers.v3.account_browser_router import build_reviewed_browser_account_router
    from backend.app.services.v3.account_browser_gate import BrowserMutationGate
    from backend.app.routers.v3.transport import V3APIError,v3_api_error_handler
    gate=BrowserMutationGate(approved_origins=[ORIGIN],preauth_secret='synthetic-signing-key-0123456789012345')
    app=FastAPI();app.add_exception_handler(V3APIError,v3_api_error_handler)
    app.include_router(build_reviewed_browser_account_router(factory=lambda:None,manifest_path=tmp_path/'missing.json',
        approved_manifest_sha256='0'*64,browser_gate=gate,browser_security_accepted=accepted),prefix='/api/v3')
    response=TestClient(app,base_url=ORIGIN).post('/api/v3/auth/browser/bootstrap',headers={'Origin':ORIGIN},json={})
    assert response.status_code==503 and 'set-cookie' not in response.headers
