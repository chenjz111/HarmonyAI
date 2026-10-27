"""Bounded shared Argon2 work, deterministic saturation and real API refusal."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier,Event
from types import SimpleNamespace
import pytest

from tests.api.v3.test_account_password_r1 import policy


@pytest.mark.parametrize('operation',['hash','verify'])
def test_all_policies_share_a_bounded_nonblocking_password_budget(operation,monkeypatch):
    from backend.app.services.v3.account_password import PasswordResourceBusy
    p=policy();encoded=p.hash('synthetic-budget-password')
    entered=Barrier(5);release=Event()
    original=getattr(p._hasher,operation)
    def slow(*args,**kwargs):
        entered.wait(timeout=5);assert release.wait(5)
        return original(*args,**kwargs)
    adapter=SimpleNamespace(hash=p._hasher.hash,verify=p._hasher.verify)
    setattr(adapter,operation,slow)
    monkeypatch.setattr(p,'_hasher',adapter)
    call=lambda:p.hash('synthetic-budget-password') if operation=='hash' else p.verify(encoded,'synthetic-budget-password')
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(call) for _ in range(4)]
        try:
            entered.wait(timeout=5)
            another=policy()
            with pytest.raises(PasswordResourceBusy):getattr(another,operation)(*(['synthetic-budget-password'] if operation=='hash' else [encoded,'synthetic-budget-password']))
        finally:release.set()
        assert all(f.result(timeout=10) for f in futures)
    # Every slot is reusable after completion; actual R1 hashes/verification ran.
    assert policy().verify(encoded,'synthetic-budget-password')


def test_password_compute_failure_releases_the_slot(monkeypatch):
    p=policy()
    def fail(*args):raise RuntimeError('synthetic computation error')
    with monkeypatch.context() as patch:
        patch.setattr(p,'_hasher',SimpleNamespace(hash=fail))
        for _ in range(8):
            with pytest.raises(RuntimeError,match='synthetic computation error'):p.hash('synthetic-budget-password')
    assert p.verify(p.hash('synthetic-budget-password'),'synthetic-budget-password')


def test_busy_password_hash_returns_503_without_converting_guest(ready,monkeypatch):
    from backend.app.services.v3.account_password import PasswordResourceBusy
    from backend.app.models.v3.identity import UserIdentity
    from backend.app.models.v3.account_security import AccountCredential
    from sqlalchemy.orm import Session
    from tests.api.v3.test_account_router_r1 import app_for,guest,PASSWORD
    token=guest(ready);client=app_for(ready,True)
    from tests.api.v3.test_account_session_r1 import service
    service()  # initialize the existing dummy hash before saturating work
    def busy(self,password):raise PasswordResourceBusy()
    monkeypatch.setattr(__import__('backend.app.services.v3.account_password',fromlist=['PasswordPolicy']).PasswordPolicy,'hash',busy)
    response=client.post('/api/v3/auth/register-bind',headers={'Authorization':'Bearer '+token},json={'username':'budget_user','password':PASSWORD})
    assert response.status_code==503 and response.json()['error']['code']=='ACCOUNT_UNAVAILABLE'
    assert PASSWORD not in response.text
    with Session(ready) as db:
        assert db.get(UserIdentity,7).auth_type=='guest' and db.query(AccountCredential).count()==0


@pytest.mark.parametrize('operation',['login','password'])
def test_busy_verify_rolls_back_login_and_password_state(ready,monkeypatch,operation):
    from backend.app.services.v3.account_password import PasswordPolicy,PasswordResourceBusy
    from backend.app.models.v3.identity import UserIdentity,AuthSession
    from backend.app.models.v3.account_security import AccountCredential,LoginBucket
    from sqlalchemy.orm import Session
    from tests.api.v3.test_account_router_r1 import app_for,guest,PASSWORD
    client=app_for(ready,True)
    registered=client.post('/api/v3/auth/register-bind',headers={'Authorization':'Bearer '+guest(ready)},json={'username':'budget_user','password':PASSWORD})
    assert registered.status_code==201
    access=registered.json()['data']['access_token']
    with Session(ready) as db:
        before=(db.get(UserIdentity,7).auth_epoch,db.get(AccountCredential,7).password_hash,
            [(r.auth_session_id,r.revoked_at) for r in db.query(AuthSession).all()],db.query(LoginBucket).count())
    def busy(*args):raise PasswordResourceBusy()
    with monkeypatch.context() as patch:
        patch.setattr(PasswordPolicy,'verify',busy)
        payload={'username':'budget_user','password':PASSWORD} if operation=='login' else {'current_password':PASSWORD,'new_password':'synthetic-new-budget-password'}
        response=client.post('/api/v3/auth/'+operation,json=payload,headers={'Authorization':'Bearer '+access} if operation=='password' else {})
    assert response.status_code==503 and response.json()['error']['code']=='ACCOUNT_UNAVAILABLE'
    assert PASSWORD not in response.text
    with Session(ready) as db:
        after=(db.get(UserIdentity,7).auth_epoch,db.get(AccountCredential,7).password_hash,
            [(r.auth_session_id,r.revoked_at) for r in db.query(AuthSession).all()],db.query(LoginBucket).count())
        assert before==after
    assert client.post('/api/v3/auth/login',json={'username':'budget_user','password':PASSWORD}).status_code==200


from tests.api.v3.test_feedback_v31_transactions import ready
