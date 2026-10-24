"""Unexposed H5 integration primitives, not a production cookie/Origin approval."""
from datetime import timedelta
import hmac,re
from urllib.parse import urlsplit
from sqlalchemy import select
from backend.app.models.v3.identity import AuthSession,UserIdentity
from backend.app.models.v3.account_security import RegisteredSessionState
from .account_session_service import AccountDenied,utc,clock,digest


class BrowserMutationGate:
    def __init__(self,*,approved_origins):
        if not approved_origins:raise ValueError('verified HTTPS Origin inventory required')
        for origin in approved_origins:
            parsed=urlsplit(origin)
            if (parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment
                or '*' in origin or any(c.isspace() for c in origin)):
                raise ValueError('exact HTTPS Origin required')
            try:
                if parsed.port is not None and not 1<=parsed.port<=65535:raise ValueError('invalid Origin port')
            except ValueError:raise ValueError('invalid Origin port') from None
        self.origins=frozenset(approved_origins)

    def verify(self,db,*,sid,origin,csrf_token,scheme,now):
        now=clock(now)
        if scheme!='https' or origin not in self.origins or not isinstance(csrf_token,str) or re.fullmatch('[A-Za-z0-9_-]{43}',csrf_token) is None:raise AccountDenied()
        owner=db.execute(select(AuthSession.internal_user_pk).where(AuthSession.auth_session_id==sid)).scalar_one_or_none()
        if owner is None:raise AccountDenied()
        identity=db.execute(select(UserIdentity).where(UserIdentity.internal_user_pk==owner).with_for_update(read=True).execution_options(populate_existing=True)).scalar_one_or_none()
        if identity is None or identity.auth_type!='registered':raise AccountDenied()
        session=db.execute(select(AuthSession).where(AuthSession.auth_session_id==sid).with_for_update(read=True).execution_options(populate_existing=True)).scalar_one_or_none()
        state=db.execute(select(RegisteredSessionState).where(RegisteredSessionState.auth_session_id==sid).with_for_update(read=True).execution_options(populate_existing=True)).scalar_one_or_none()
        if (session is None or state is None or session.revoked_at is not None or utc(session.expires_at)<=now
            or utc(state.absolute_expires_at)<=now or state.platform!='h5' or not hmac.compare_digest(state.csrf_hash,digest(csrf_token))):raise AccountDenied()
        # This validates CSRF only; it never authenticates a principal or replaces refresh proof verification.


def set_refresh_cookie(response,proof,*,expires_at,now):
    now=clock(now);expires_at=utc(expires_at)
    if not isinstance(proof,str) or re.fullmatch('[A-Za-z0-9_-]{43}',proof) is None or not now<expires_at<=now+timedelta(days=7):raise ValueError('bounded refresh cookie required')
    response.set_cookie('__Host-harmonyai-refresh',proof,max_age=int((expires_at-now).total_seconds()),expires=expires_at,
        path='/',secure=True,httponly=True,samesite='lax')
