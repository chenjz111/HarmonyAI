"""Synthetic account lifecycle; no public route or device acceptance implied."""
from datetime import datetime,timedelta,timezone
import pytest
from sqlalchemy.orm import Session,sessionmaker
from tests.api.v3.test_feedback_v31_transactions import ready,principal

NOW=datetime(2026,10,24,tzinfo=timezone.utc)
PASSWORD='synthetic-safe-long-passphrase'


def service():
    from backend.app.services.v3.account_password import PasswordPolicy
    from backend.app.services.v3.account_session_service import AccountService
    return AccountService(password_policy=PasswordPolicy(blocked_passwords={'passwordpassword'}))


def seed_guest(engine):
    from backend.app.models.v3.identity import UserIdentity
    with Session(engine) as db:
        db.add(UserIdentity(internal_user_pk=7,public_user_id='synthetic-7',auth_type='guest',guest_expires_at=NOW+timedelta(days=7)));db.commit()


def bind(engine,*,username='Alice_123'):
    seed_guest(engine)
    s=service()
    result=s.bind(sessionmaker(bind=engine),principal=principal().model_copy(update={'auth_type':'guest','public_user_id':'synthetic-7'}),
        username=username,password=PASSWORD,platform='android',now=NOW)
    return s,result


def test_binding_keeps_owner_and_persists_only_hashes(ready):
    from backend.app.models.v3.account_security import AccountCredential,RefreshProof
    s,result=bind(ready)
    with Session(ready) as db:
        c=db.get(AccountCredential,7)
        assert c.username == 'alice_123' and PASSWORD not in c.password_hash
        assert db.query(RefreshProof).count() == 1
        assert result.refresh_token not in repr(db.query(RefreshProof).first().__dict__)
        assert db.execute(__import__('sqlalchemy').text('SELECT count(*) FROM feedback_v3')).scalar() == 0
    assert result.internal_user_pk == 7


def test_login_existing_account_does_not_merge_guest_owner(ready):
    s,first=bind(ready)
    result=s.login(sessionmaker(bind=ready),username='ALICE_123',password=PASSWORD,trusted_source='192.0.2.1',platform='android',now=NOW)
    assert result.internal_user_pk == first.internal_user_pk == 7
    assert result.sid != first.sid


def test_rotation_consumes_once_and_replay_revokes_family(ready):
    from backend.app.services.v3.account_session_service import AccountDenied
    from backend.app.models.v3.identity import AuthSession
    s,first=bind(ready);factory=sessionmaker(bind=ready)
    second=s.refresh(factory,refresh_token=first.refresh_token,platform='android',now=NOW+timedelta(days=1))
    assert second.refresh_token != first.refresh_token and second.sid == first.sid
    with pytest.raises(AccountDenied):s.refresh(factory,refresh_token=first.refresh_token,platform='android',now=NOW+timedelta(days=1))
    with Session(ready) as db: assert db.get(AuthSession,first.sid).revoked_at is not None
    with pytest.raises(AccountDenied):s.refresh(factory,refresh_token=second.refresh_token,platform='android',now=NOW+timedelta(days=1))


@pytest.mark.parametrize('days',[7,14,15])
def test_refresh_idle_or_absolute_expiry_denies(ready,days):
    from backend.app.services.v3.account_session_service import AccountDenied
    s,result=bind(ready)
    with pytest.raises(AccountDenied):s.refresh(sessionmaker(bind=ready),refresh_token=result.refresh_token,platform='android',now=NOW+timedelta(days=days))


def test_refresh_never_extends_absolute_expiry(ready):
    from backend.app.models.v3.identity import AuthSession
    s,result=bind(ready);factory=sessionmaker(bind=ready)
    for day in (6,12,13):result=s.refresh(factory,refresh_token=result.refresh_token,platform='android',now=NOW+timedelta(days=day))
    with Session(ready) as db:assert db.get(AuthSession,result.sid).expires_at.replace(tzinfo=timezone.utc) == NOW+timedelta(days=14)


def test_single_and_global_logout(ready):
    from backend.app.models.v3.identity import AuthSession,UserIdentity
    s,first=bind(ready);factory=sessionmaker(bind=ready)
    second=s.login(factory,username='alice_123',password=PASSWORD,trusted_source='192.0.2.1',platform='android',now=NOW)
    s.logout(factory,owner=7,sid=first.sid,all_devices=False,now=NOW)
    with Session(ready) as db:
        assert db.get(AuthSession,first.sid).revoked_at is not None and db.get(AuthSession,second.sid).revoked_at is None
    s.logout(factory,owner=7,sid=second.sid,all_devices=True,now=NOW)
    with Session(ready) as db:
        assert db.get(UserIdentity,7).auth_epoch == 2
        assert db.get(AuthSession,second.sid).revoked_at is not None


def test_wrong_password_and_unknown_username_have_same_failure(ready):
    from backend.app.services.v3.account_session_service import AccountDenied
    s,_=bind(ready);factory=sessionmaker(bind=ready)
    errors=[]
    for name in ('alice_123','unknown_user'):
        with pytest.raises(AccountDenied) as caught:s.login(factory,username=name,password='wrong-synthetic-long-passphrase',trusted_source='192.0.2.1',platform='android',now=NOW)
        errors.append(str(caught.value))
    assert errors[0] == errors[1]


def test_h5_without_verified_origin_csrf_gate_fails_closed(ready):
    from backend.app.services.v3.account_session_service import AccountDenied
    s,result=bind(ready)
    with pytest.raises(AccountDenied):s.refresh(sessionmaker(bind=ready),refresh_token=result.refresh_token,platform='h5',now=NOW)


def test_account_delay_and_source_attempt_limits_are_server_state(ready):
    from backend.app.services.v3.account_session_service import AccountDenied
    s,_=bind(ready);factory=sessionmaker(bind=ready)
    for _ in range(5):
        with pytest.raises(AccountDenied):s.login(factory,username='alice_123',password='wrong-synthetic-long-passphrase',trusted_source='192.0.2.1',platform='android',now=NOW)
    with pytest.raises(AccountDenied):s.login(factory,username='alice_123',password=PASSWORD,trusted_source='192.0.2.2',platform='android',now=NOW)
    assert s.login(factory,username='alice_123',password=PASSWORD,trusted_source='192.0.2.2',platform='android',now=NOW+timedelta(seconds=1)).internal_user_pk == 7
    for i in range(30):
        with pytest.raises(AccountDenied):s.login(factory,username=f'unknown_{i}',password=PASSWORD,trusted_source='192.0.2.3',platform='android',now=NOW)
    with pytest.raises(AccountDenied):s.login(factory,username='alice_123',password=PASSWORD,trusted_source='192.0.2.3',platform='android',now=NOW+timedelta(seconds=2))


def test_duplicate_binding_does_not_convert_or_merge_second_guest(ready):
    from backend.app.models.user import User
    from backend.app.models.v3.identity import UserIdentity
    from backend.app.services.v3.account_session_service import AccountDenied
    s,_=bind(ready);factory=sessionmaker(bind=ready)
    with Session(ready) as db:
        db.add(User(id=8,openid='synthetic-second'));db.flush()
        db.add(UserIdentity(internal_user_pk=8,public_user_id='synthetic-8',auth_type='guest',guest_expires_at=NOW+timedelta(days=7)));db.commit()
    with pytest.raises(AccountDenied):s.bind(factory,principal=principal(8).model_copy(update={'auth_type':'guest'}),username='alice_123',password=PASSWORD,platform='android',now=NOW)
    with Session(ready) as db:assert db.get(UserIdentity,8).auth_type == 'guest'


def test_password_change_revokes_every_session_and_advances_epoch(ready):
    from backend.app.models.v3.identity import AuthSession,UserIdentity
    from backend.app.services.v3.account_session_service import AccountDenied
    s,result=bind(ready);factory=sessionmaker(bind=ready)
    s.change_password(factory,owner=7,current_password=PASSWORD,new_password='new-synthetic-safe-long-passphrase',now=NOW)
    with Session(ready) as db:
        assert db.get(UserIdentity,7).auth_epoch==2
        assert db.get(AuthSession,result.sid).revoked_at is not None
    with pytest.raises(AccountDenied):s.login(factory,username='alice_123',password=PASSWORD,trusted_source='192.0.2.1',platform='android',now=NOW)
    assert s.login(factory,username='alice_123',password='new-synthetic-safe-long-passphrase',trusted_source='192.0.2.1',platform='android',now=NOW).internal_user_pk==7


def test_refresh_commit_unknown_requires_reauthentication_without_second_issuance(ready):
    from backend.app.services.v3.account_session_service import AccountUnavailable,AccountDenied
    from backend.app.models.v3.account_security import RefreshProof
    from backend.app.models.v3.identity import AuthSession
    s,result=bind(ready)
    class AckLost(Session):
        def commit(self):super().commit();raise OSError('synthetic lost ACK')
    with pytest.raises(AccountUnavailable,match='reauthenticate'):
        s.refresh(sessionmaker(bind=ready,class_=AckLost),refresh_token=result.refresh_token,platform='android',now=NOW)
    with Session(ready) as db:assert db.query(RefreshProof).count()==2
    with pytest.raises(AccountDenied):s.refresh(sessionmaker(bind=ready),refresh_token=result.refresh_token,platform='android',now=NOW)
    with Session(ready) as db:
        assert db.query(RefreshProof).count()==2 and db.get(AuthSession,result.sid).revoked_at is not None


def test_failed_rotation_rolls_back_consumption_hash_and_new_proof(ready):
    from backend.app.services.v3.account_session_service import AccountUnavailable
    from backend.app.models.v3.account_security import RefreshProof
    s,result=bind(ready)
    class FlushFailure(Session):
        def flush(self,*args,**kwargs):
            if any(isinstance(row,RefreshProof) for row in self.new):raise RuntimeError('synthetic flush failure')
            return super().flush(*args,**kwargs)
    with pytest.raises(AccountUnavailable):s.refresh(sessionmaker(bind=ready,class_=FlushFailure),refresh_token=result.refresh_token,platform='android',now=NOW)
    assert s.refresh(sessionmaker(bind=ready),refresh_token=result.refresh_token,platform='android',now=NOW).sid==result.sid
    with Session(ready) as db:assert db.query(RefreshProof).count()==2
