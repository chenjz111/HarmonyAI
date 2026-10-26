"""Internal Owner R1 account transactions. No registration/refresh routes enabled.

Unknown commit never replays an old refresh proof: require reauthentication.
H5 stays closed until verified Origin/preauth-CSRF/cookie integration exists.
"""
from dataclasses import dataclass,field
from datetime import datetime,timedelta,timezone
from hashlib import sha256
import hmac
import ipaddress
import secrets
from threading import Lock
from uuid import uuid4
from jose import jwt
from sqlalchemy import select,update
from backend.app.core.config import settings
from backend.app.routers.v3.transport import V3APIError
from backend.app.models.v3.identity import UserIdentity,AuthSession
from backend.app.models.v3.account_security import AccountCredential,RegisteredSessionState,RefreshProof,LoginBucket
from .account_password import normalize_username,PasswordResourceBusy


class AccountDenied(Exception):
    def __init__(self):super().__init__('authentication failed')
class AccountUnavailable(Exception):pass


def utc(value):return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
def digest(value):return 'sha256:'+sha256(value.encode('ascii')).hexdigest()
def clock(value):
    if not isinstance(value,datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):raise ValueError('server UTC clock required')
    return value.replace(microsecond=0)


@dataclass(frozen=True)
class AccountTokens:
    internal_user_pk:int
    sid:str
    access_token:str=field(repr=False)
    refresh_token:str=field(repr=False)
    csrf_token:str=field(repr=False)
    access_expires_at:datetime


class AccountService:
    _dummy_hash=None
    _dummy_lock=Lock()
    def __init__(self,*,password_policy):
        self.passwords=password_policy
        with self._dummy_lock:
            if AccountService._dummy_hash is None:
                AccountService._dummy_hash=self._hash_password('synthetic-dummy-verification-only-'+secrets.token_hex(16))
        self._dummy=AccountService._dummy_hash

    def _hash_password(self,password):
        try:return self.passwords.hash(password)
        except PasswordResourceBusy:raise AccountUnavailable('password resources unavailable') from None

    def _run(self,factory,operation):
        with factory() as db:
            try:
                if db.get_bind().dialect.name == 'sqlite':db.connection().exec_driver_sql('BEGIN IMMEDIATE')
                elif db.get_bind().dialect.name != 'mysql':raise AccountUnavailable('unsupported account transaction dialect')
                result=operation(db)
            except V3APIError:
                db.rollback();raise AccountDenied() from None
            except (AccountDenied,ValueError):
                db.rollback();raise
            except Exception as error:
                db.rollback();raise AccountUnavailable('account transaction unavailable') from error
            try:db.commit()
            except Exception as error:
                try:db.rollback()
                except Exception:pass
                raise AccountUnavailable('commit unverified; reauthenticate, never retry old refresh') from error
        if isinstance(result,AccountDenied):raise result
        return result

    def _identity(self,db,owner):
        row=db.execute(select(UserIdentity).where(UserIdentity.internal_user_pk==owner).with_for_update().execution_options(populate_existing=True)).scalar_one_or_none()
        if row is None:raise AccountDenied()
        return row

    def _platform(self,platform):
        if platform != 'android':raise AccountDenied()

    def _tokens(self,identity,session,proof,csrf,now):
        if settings.JWT_ALGORITHM != "HS256":raise AccountUnavailable("approved token algorithm required")
        expiry=now+timedelta(minutes=15)
        access=jwt.encode(dict(sub=identity.public_user_id,auth_type='registered',sid=session.auth_session_id,
            auth_epoch=identity.auth_epoch,token_type='access',iat=int(now.timestamp()),exp=int(expiry.timestamp())),settings.JWT_SECRET_KEY,algorithm='HS256')
        return AccountTokens(identity.internal_user_pk,session.auth_session_id,access,proof,csrf,expiry)

    def _issue(self,db,identity,platform,now):
        proof,csrf=secrets.token_urlsafe(32),secrets.token_urlsafe(32)
        sid='sid_'+uuid4().hex
        session=AuthSession(auth_session_id=sid,internal_user_pk=identity.internal_user_pk,refresh_credential_hash=digest(proof),
            family_id='family_'+uuid4().hex,created_at=now,expires_at=now+timedelta(days=7))
        db.add(session);db.flush()
        db.add(RegisteredSessionState(auth_session_id=sid,absolute_expires_at=now+timedelta(days=14),csrf_hash=digest(csrf),platform=platform,created_at=now))
        db.add(RefreshProof(credential_hash=digest(proof),auth_session_id=sid,issued_at=now,expires_at=session.expires_at))
        db.flush()
        return self._tokens(identity,session,proof,csrf,now)

    def bind(self,factory,*,principal,username,password,platform,now):
        self._platform(platform);now=clock(now);username=normalize_username(username)
        encoded=self._hash_password(password)
        return self._run(factory,lambda db:self._bind_identity(db,principal,username,encoded,platform,now))

    def _bind_identity(self,db,principal,username,encoded,platform,now):
        identity=self._identity(db,principal.internal_user_pk)
        if (principal.auth_type != 'guest' or identity.auth_type != 'guest' or identity.public_user_id != principal.public_user_id
            or identity.guest_expires_at is None or utc(identity.guest_expires_at)<=now):raise AccountDenied()
        if db.execute(select(AccountCredential.internal_user_pk).where(AccountCredential.username==username)).first():raise AccountDenied()
        db.add(AccountCredential(internal_user_pk=identity.internal_user_pk,username=username,password_hash=encoded,created_at=now,updated_at=now))
        identity.auth_type='registered';identity.guest_expires_at=None;identity.auth_epoch+=1
        db.flush()
        return self._issue(db,identity,platform,now)

    def bind_access(self,factory,*,access_token,username,password,platform,now):
        from .auth_service import _resolve_principal
        self._platform(platform);now=clock(now);username=normalize_username(username);encoded=self._hash_password(password)
        def operation(db):
            principal=_resolve_principal(access_token,db,exclusive=True)
            return self._bind_identity(db,principal,username,encoded,platform,now)
        return self._run(factory,operation)

    def _bucket(self,db,kind,key,now):
        hashed='sha256:'+hmac.new(settings.JWT_SECRET_KEY.encode(),(kind+'\0'+key).encode(),sha256).hexdigest()
        row=db.execute(select(LoginBucket).where(LoginBucket.bucket_key==hashed).with_for_update().execution_options(populate_existing=True)).scalar_one_or_none()
        if row is None:
            row=LoginBucket(bucket_key=hashed,kind=kind,window_started_at=now,attempts=0,failures=0);db.add(row);db.flush()
        elif now >= utc(row.window_started_at)+timedelta(minutes=15):
            row.window_started_at=now;row.attempts=0;row.failures=0;row.next_allowed_at=None
        return row

    def login(self,factory,*,username,password,trusted_source,platform,now):
        self._platform(platform);now=clock(now)
        try:username=normalize_username(username);source=str(ipaddress.ip_address(trusted_source))
        except (ValueError,TypeError):raise AccountDenied() from None
        def operation(db):
            # Source is supplied only by a trusted request adapter, never X-Forwarded-For.
            source_bucket=self._bucket(db,'source',source,now)
            account=self._bucket(db,'account',username,now)
            source_bucket.attempts+=1;account.attempts+=1
            if source_bucket.attempts>30 or (account.next_allowed_at is not None and utc(account.next_allowed_at)>now):return AccountDenied()
            credential=db.execute(select(AccountCredential).where(AccountCredential.username==username)).scalar_one_or_none()
            identity=None
            if credential is not None:
                identity=self._identity(db,credential.internal_user_pk)
                db.refresh(credential,with_for_update=True)
            valid=self.passwords.verify(credential.password_hash if credential else self._dummy,password)
            if not valid or identity is None or identity.auth_type!='registered':
                account.failures+=1
                if account.failures>=5:account.next_allowed_at=now+timedelta(seconds=min(900,2**min(account.failures-5,10)))
                return AccountDenied()
            account.failures=0;account.next_allowed_at=None
            return self._issue(db,identity,platform,now)
        return self._run(factory,operation)

    def refresh(self,factory,*,refresh_token,platform,now):
        self._platform(platform);now=clock(now)
        if not isinstance(refresh_token,str) or len(refresh_token)!=43 or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_' for c in refresh_token):raise AccountDenied()
        hashed=digest(refresh_token)
        def operation(db):
            # Discovery reads never authorize. Lock identity first, then current session/proof.
            found=db.execute(select(RefreshProof.auth_session_id).where(RefreshProof.credential_hash==hashed)).scalar_one_or_none()
            if found is None:return AccountDenied()
            owner=db.execute(select(AuthSession.internal_user_pk).where(AuthSession.auth_session_id==found)).scalar_one_or_none()
            if owner is None:return AccountDenied()
            identity=self._identity(db,owner)
            session=db.execute(select(AuthSession).where(AuthSession.auth_session_id==found).with_for_update().execution_options(populate_existing=True)).scalar_one()
            proof=db.execute(select(RefreshProof).where(RefreshProof.credential_hash==hashed).with_for_update().execution_options(populate_existing=True)).scalar_one()
            state=db.execute(select(RegisteredSessionState).where(RegisteredSessionState.auth_session_id==found).with_for_update().execution_options(populate_existing=True)).scalar_one()
            if proof.consumed_at is not None:
                db.execute(update(AuthSession).where(AuthSession.family_id==session.family_id,AuthSession.internal_user_pk==owner,AuthSession.revoked_at.is_(None)).values(revoked_at=now))
                return AccountDenied()
            if (identity.auth_type!='registered' or session.revoked_at is not None or utc(session.expires_at)<=now
                or utc(proof.expires_at)<=now or utc(state.absolute_expires_at)<=now or state.platform!=platform
                or not hmac.compare_digest(session.refresh_credential_hash,hashed)):return AccountDenied()
            next_proof,csrf=secrets.token_urlsafe(32),secrets.token_urlsafe(32)
            proof.consumed_at=now;session.refresh_credential_hash=digest(next_proof)
            session.expires_at=min(utc(state.absolute_expires_at),now+timedelta(days=7));state.csrf_hash=digest(csrf)
            db.add(RefreshProof(credential_hash=digest(next_proof),auth_session_id=found,issued_at=now,expires_at=session.expires_at))
            db.flush()
            return self._tokens(identity,session,next_proof,csrf,now)
        return self._run(factory,operation)

    def logout(self,factory,*,owner,sid,all_devices,now):
        now=clock(now)
        if type(all_devices) is not bool:raise ValueError('boolean logout scope required')
        def operation(db):
            identity=self._identity(db,owner)
            session=db.execute(select(AuthSession).where(AuthSession.auth_session_id==sid,AuthSession.internal_user_pk==owner).with_for_update()).scalar_one_or_none()
            if session is None or session.revoked_at is not None or utc(session.expires_at)<=now:raise AccountDenied()
            query=update(AuthSession).where(AuthSession.internal_user_pk==owner,AuthSession.revoked_at.is_(None))
            if all_devices:identity.auth_epoch+=1
            else:query=query.where(AuthSession.auth_session_id==sid)
            db.execute(query.values(revoked_at=now));db.flush()
        return self._run(factory,operation)


    def change_password(self,factory,*,owner,current_password,new_password,now):
        now=clock(now);encoded=self._hash_password(new_password)
        def operation(db):
            identity=self._identity(db,owner)
            credential=db.execute(select(AccountCredential).where(AccountCredential.internal_user_pk==owner).with_for_update().execution_options(populate_existing=True)).scalar_one_or_none()
            if identity.auth_type!='registered' or credential is None or not self.passwords.verify(credential.password_hash,current_password):return AccountDenied()
            credential.password_hash=encoded;credential.updated_at=now;identity.auth_epoch+=1
            db.execute(update(AuthSession).where(AuthSession.internal_user_pk==owner,AuthSession.revoked_at.is_(None)).values(revoked_at=now))
            db.flush()
        return self._run(factory,operation)


    def logout_access(self,factory,*,access_token,all_devices,now):
        from .auth_service import _resolve_principal,_decode_verified_claims
        now=clock(now)
        if type(all_devices) is not bool:raise ValueError('boolean logout scope required')
        def operation(db):
            principal=_resolve_principal(access_token,db,exclusive=True)
            if principal.auth_type!='registered':raise AccountDenied()
            sid=_decode_verified_claims(access_token)['sid']
            identity=self._identity(db,principal.internal_user_pk)
            query=update(AuthSession).where(AuthSession.internal_user_pk==principal.internal_user_pk,AuthSession.revoked_at.is_(None))
            if all_devices:identity.auth_epoch+=1
            else:query=query.where(AuthSession.auth_session_id==sid)
            db.execute(query.values(revoked_at=now));db.flush()
        return self._run(factory,operation)

    def change_password_access(self,factory,*,access_token,current_password,new_password,now):
        from .auth_service import _resolve_principal
        now=clock(now);encoded=self._hash_password(new_password)
        def operation(db):
            principal=_resolve_principal(access_token,db,exclusive=True)
            if principal.auth_type!='registered':raise AccountDenied()
            identity=self._identity(db,principal.internal_user_pk)
            credential=db.execute(select(AccountCredential).where(AccountCredential.internal_user_pk==principal.internal_user_pk).with_for_update().execution_options(populate_existing=True)).scalar_one_or_none()
            if credential is None or not self.passwords.verify(credential.password_hash,current_password):return AccountDenied()
            credential.password_hash=encoded;credential.updated_at=now;identity.auth_epoch+=1
            db.execute(update(AuthSession).where(AuthSession.internal_user_pk==principal.internal_user_pk,AuthSession.revoked_at.is_(None)).values(revoked_at=now));db.flush()
        return self._run(factory,operation)
