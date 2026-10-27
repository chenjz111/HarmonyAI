"""Synthetic local artifacts only; no distribution is approved by these tests."""
import hashlib
import json
import pytest
from tests.api.v3.test_feedback_v31_transactions import ready


def artifact(tmp_path):
    data=json.dumps(['synthetic-compromised-passphrase','synthetic-café-passphrase'],ensure_ascii=False).encode()
    (tmp_path/'blocked.json').write_bytes(data)
    manifest=dict(format='harmonyai.password-blocklist.v1',version='synthetic-v1',approval_ref='TEST-ONLY',license_ref='SYNTHETIC',passwords_file='blocked.json',passwords_sha256=hashlib.sha256(data).hexdigest(),entry_count=2)
    path=tmp_path/'manifest.json';path.write_text(json.dumps(manifest),encoding='utf-8')
    return path,hashlib.sha256(path.read_bytes()).hexdigest(),manifest


def test_reviewed_source_matches_pinned_bytes_and_existing_nfc_casefold_policy(tmp_path):
    from backend.app.services.v3.account_password_source import load_reviewed_password_policy
    path,digest,_=artifact(tmp_path)
    policy=load_reviewed_password_policy(path,approved_manifest_sha256=digest)
    for value in ['SYNTHETIC-COMPROMISED-PASSPHRASE','synthetic-cafe\u0301-passphrase']:
        with pytest.raises(ValueError):policy.validate(value)
    assert policy.validate('synthetic-independent-passphrase')=='synthetic-independent-passphrase'
    assert policy.source_info['version']=='synthetic-v1'
    assert policy.source_info['manifest_sha256']==digest


@pytest.mark.parametrize('fault',['missing_approval','changed_manifest','changed_dataset','escaping_path','entry_count','empty'])
def test_source_failures_do_not_create_a_policy_or_fallback_to_test_list(tmp_path,fault):
    from backend.app.services.v3.account_password_source import load_reviewed_password_policy
    path,digest,manifest=artifact(tmp_path)
    if fault=='missing_approval':digest=None
    elif fault=='changed_manifest':path.write_text('{}',encoding='utf-8')
    elif fault=='changed_dataset':(tmp_path/'blocked.json').write_text('[]')
    else:
        if fault=='escaping_path':manifest['passwords_file']='../blocked.json'
        elif fault=='entry_count':manifest['entry_count']=3
        elif fault=='empty':
            (tmp_path/'blocked.json').write_bytes(b'[]');manifest['passwords_sha256']=hashlib.sha256(b'[]').hexdigest();manifest['entry_count']=0
        path.write_text(json.dumps(manifest),encoding='utf-8');digest=hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError,match='reviewed password source unavailable'):
        load_reviewed_password_policy(path,approved_manifest_sha256=digest)


@pytest.mark.parametrize('approved',[False,True])
def test_reviewed_source_composes_existing_router_without_default_activation(tmp_path,ready,approved):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker
    from backend.app.routers.v3.account_router import build_reviewed_native_account_router
    from backend.app.routers.v3.transport import V3APIError,v3_api_error_handler
    from tests.api.v3.test_account_router_r1 import guest
    path,digest,_=artifact(tmp_path)
    app=FastAPI();app.add_exception_handler(V3APIError,v3_api_error_handler)
    app.include_router(build_reviewed_native_account_router(factory=sessionmaker(bind=ready),manifest_path=path,approved_manifest_sha256=digest,native_security_accepted=approved),prefix='/api/v3')
    client=TestClient(app,base_url='https://testserver')
    response=client.post('/api/v3/auth/register-bind',headers={'Authorization':'Bearer '+guest(ready)},json={'username':'source_user','password':'synthetic-independent-passphrase'})
    assert response.status_code==(201 if approved else 503)


def test_missing_reviewed_source_never_uses_inline_fixture_list(tmp_path,ready):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker
    from backend.app.routers.v3.account_router import build_reviewed_native_account_router
    from backend.app.routers.v3.transport import V3APIError,v3_api_error_handler
    app=FastAPI();app.add_exception_handler(V3APIError,v3_api_error_handler)
    app.include_router(build_reviewed_native_account_router(factory=sessionmaker(bind=ready),manifest_path=tmp_path/'missing.json',approved_manifest_sha256=None,native_security_accepted=True),prefix='/api/v3')
    response=TestClient(app,base_url='https://testserver').post('/api/v3/auth/login',json={'username':'source_user','password':'synthetic-independent-passphrase'})
    assert response.status_code==503
    assert response.json()['error']['code']=='ACCOUNT_UNAVAILABLE'
