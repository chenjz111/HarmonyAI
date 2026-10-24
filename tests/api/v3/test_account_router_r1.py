"""Opt-in native integration harness; production router remains unregistered."""
from datetime import datetime,timedelta,timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session,sessionmaker
import pytest
from tests.api.v3.test_feedback_v31_transactions import ready
from tests.api.v3.test_account_session_r1 import service,PASSWORD


def app_for(ready,accepted):
    from backend.app.routers.v3.account_router import build_account_router
    from backend.app.routers.v3.transport import V3APIError,v3_api_error_handler
    app=FastAPI();app.add_exception_handler(V3APIError,v3_api_error_handler)
    app.include_router(build_account_router(factory=sessionmaker(bind=ready),service_provider=service,native_security_accepted=accepted),prefix='/api/v3')
    return TestClient(app,base_url='https://testserver',client=('192.0.2.1',1234))


def guest(ready):
    from backend.app.models.v3.identity import UserIdentity
    from backend.app.services.v3.auth_service import _encode_guest_token
    now=datetime.now(timezone.utc)
    with Session(ready) as db:
        db.add(UserIdentity(internal_user_pk=7,public_user_id='synthetic-7',auth_type='guest',guest_expires_at=now+timedelta(days=7)));db.commit()
    return _encode_guest_token('synthetic-7',now+timedelta(days=7))


def test_router_defaults_fail_closed_before_credential_processing(ready):
    response=app_for(ready,False).post('/api/v3/auth/register-bind',json={'username':'alice_123','password':PASSWORD})
    assert response.status_code==503 and PASSWORD not in response.text


def test_native_bind_refresh_logout_flow_has_registered_session_verification(ready):
    from backend.app.services.v3.auth_service import _resolve_principal
    from backend.app.routers.v3.transport import V3APIError
    client=app_for(ready,True)
    response=client.post('/api/v3/auth/register-bind',headers={'Authorization':'Bearer '+guest(ready)},json={'username':'alice_123','password':PASSWORD})
    assert response.status_code==201
    first=response.json()['data'];assert first['public_user_id']=='synthetic-7'
    assert 'internal_user_pk' not in first and 'password_hash' not in first
    second=client.post('/api/v3/auth/refresh',json={'refresh_token':first['refresh_token']})
    assert second.status_code==200
    second=second.json()['data']
    headers={'Authorization':'Bearer '+second['access_token']}
    assert client.post('/api/v3/auth/logout',headers=headers,json={'all_devices':False}).status_code==200
    with Session(ready) as db,pytest.raises(V3APIError):_resolve_principal(second['access_token'],db)


@pytest.mark.parametrize('headers',[{'Origin':'https://evil.example'},{'Cookie':'refresh=synthetic'},{'X-Forwarded-For':'192.0.2.1','Origin':'null'}])
def test_browser_cannot_bypass_csrf_by_claiming_native(headers,ready):
    response=app_for(ready,True).post('/api/v3/auth/login',headers=headers,json={'username':'alice_123','password':PASSWORD})
    assert response.status_code==503 and PASSWORD not in response.text


def test_actual_application_does_not_expose_unaccepted_account_routes():
    from backend.app.main import app
    assert not any(getattr(route,'path','') in {'/api/v3/auth/register-bind','/api/v3/auth/refresh','/api/v3/auth/login'} for route in app.routes)


def test_account_validation_response_never_echoes_password(ready):
    response=app_for(ready,True).post('/api/v3/auth/login',json={'password':PASSWORD})
    assert response.status_code==422 and PASSWORD not in response.text
