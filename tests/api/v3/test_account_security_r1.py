"""Owner Account Security R1: synthetic tokens and isolated production metadata."""
from datetime import datetime,timedelta,timezone
from uuid import uuid4
import pytest
from jose import jwt
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.services.v3.auth_service import _resolve_principal
from backend.app.routers.v3.transport import V3APIError
from tests.api.v3.test_feedback_v31_transactions import ready


def registered(ready,*,revoked=False,session_owner=7,epoch=0,expired=False):
    from backend.app.models.v3.identity import UserIdentity,AuthSession
    from backend.app.models.user import User
    now=datetime.now(timezone.utc)
    with Session(ready) as db:
        db.add(UserIdentity(internal_user_pk=7,public_user_id='registered-a',auth_type='registered',auth_epoch=epoch))
        if session_owner != 7: db.add(User(id=session_owner,openid='other-owner'))
        db.flush()
        db.add(AuthSession(auth_session_id='sid-a',internal_user_pk=session_owner,refresh_credential_hash='sha256:'+uuid4().hex,
            family_id='family-a',created_at=now-timedelta(days=2),expires_at=now+timedelta(days=-1 if expired else 2),
            revoked_at=now-timedelta(days=1) if revoked else None))
        db.commit()
    return now


def token(now,**changes):
    claims=dict(sub='registered-a',auth_type='registered',iat=int(now.timestamp()),exp=int((now+timedelta(minutes=15)).timestamp()),
        token_type='access',sid='sid-a',auth_epoch=0)
    claims.update(changes)
    return jwt.encode(claims,settings.JWT_SECRET_KEY,algorithm='HS256')


@pytest.mark.parametrize('changes',[{'sid':None},{'sid':'missing'},{'auth_epoch':None},{'auth_epoch':True},{'auth_epoch':1},{'token_type':'refresh'}])
def test_registered_requires_server_session_epoch_and_access_type(ready,changes):
    now=registered(ready)
    with Session(ready) as db,pytest.raises(V3APIError): _resolve_principal(token(now,**changes),db)


@pytest.mark.parametrize('changes',[{'revoked':True},{'session_owner':8},{'epoch':1},{'expired':True}])
def test_registered_rejects_revoked_foreign_stale_and_expired_session(ready,changes):
    now=registered(ready,**changes)
    with Session(ready) as db,pytest.raises(V3APIError): _resolve_principal(token(now),db)


def test_registered_valid_session_resolves_without_changing_owner(ready):
    now=registered(ready)
    with Session(ready) as db: assert _resolve_principal(token(now),db).internal_user_pk == 7


def test_guest_without_new_claims_keeps_original_expiry_contract(ready):
    from backend.app.models.v3.identity import UserIdentity
    now=datetime.now(timezone.utc)
    with Session(ready) as db:
        db.add(UserIdentity(internal_user_pk=7,public_user_id='old-guest',auth_type='guest',guest_expires_at=now+timedelta(days=1)));db.commit()
        signed=jwt.encode(dict(sub='old-guest',auth_type='guest',iat=int(now.timestamp()),exp=int((now+timedelta(days=7)).timestamp())),settings.JWT_SECRET_KEY,algorithm='HS256')
        assert _resolve_principal(signed,db).internal_user_pk == 7
        row=db.get(UserIdentity,7);row.guest_expires_at=now-timedelta(seconds=1);db.commit()
        with pytest.raises(V3APIError): _resolve_principal(signed,db)


def test_guest_normal_key_rotation_accepts_configured_previous_key_only(ready,monkeypatch):
    from backend.app.models.v3.identity import UserIdentity
    now=datetime.now(timezone.utc);old_key=settings.JWT_SECRET_KEY
    with Session(ready) as db:
        db.add(UserIdentity(internal_user_pk=7,public_user_id='old-key-guest',auth_type='guest',guest_expires_at=now+timedelta(days=1)));db.commit()
        signed=jwt.encode(dict(sub='old-key-guest',auth_type='guest',iat=int(now.timestamp()),exp=int((now+timedelta(days=1)).timestamp())),old_key,algorithm='HS256')
        monkeypatch.setattr(settings,'JWT_SECRET_KEY','synthetic-new-key-for-rotation-0123456789')
        monkeypatch.setattr(settings,'JWT_PREVIOUS_SECRET_KEYS',[old_key])
        assert _resolve_principal(signed,db).internal_user_pk==7
        monkeypatch.setattr(settings,'JWT_PREVIOUS_SECRET_KEYS',[])
        with pytest.raises(V3APIError):_resolve_principal(signed,db)
