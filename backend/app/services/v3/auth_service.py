"""Guest identity creation and V3 bearer authentication."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.models.v3.identity import UserIdentity, UserProfile
from backend.app.routers.v3.transport import V3APIError
from backend.app.schemas.v3.common import AuthPrincipal, GuestAuthResponse


_bearer = HTTPBearer(auto_error=False)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _unauthenticated() -> V3APIError:
    return V3APIError(
        401,
        "UNAUTHENTICATED",
        "身份已失效，请重新进入体验。",
        next_actions=["restart_guest_session"],
    )


def _encode_guest_token(public_user_id: str, expires_at: datetime) -> str:
    now = _utc_now()
    return jwt.encode(
        {
            "sub": public_user_id,
            "auth_type": "guest",
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
        },
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_guest_principal(db: Session) -> GuestAuthResponse:
    public_user_id = f"u_guest_{uuid.uuid4().hex}"
    expires_at = _utc_now() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    user = User(openid=f"guest:{uuid.uuid4().hex}")
    try:
        db.add(user)
        db.flush()
        db.add(
            UserIdentity(
                internal_user_pk=user.id,
                public_user_id=public_user_id,
                auth_type="guest",
                guest_expires_at=expires_at,
            )
        )
        db.add(UserProfile(internal_user_pk=user.id))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return GuestAuthResponse(
        access_token=_encode_guest_token(public_user_id, expires_at),
        token_type="Bearer",
        expires_at=expires_at,
        public_user_id=public_user_id,
    )


def _resolve_principal(token: str, db: Session) -> AuthPrincipal:
    """Decode a bearer token and resolve the identity behind it.

    Any unusable token (malformed, expired, unknown subject, expired guest)
    raises the standard 401 UNAUTHENTICATED error.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except (ExpiredSignatureError, JWTError):
        raise _unauthenticated() from None

    public_user_id = payload.get("sub")
    if not isinstance(public_user_id, str) or not public_user_id:
        raise _unauthenticated()
    identity = db.query(UserIdentity).filter(
        UserIdentity.public_user_id == public_user_id
    ).one_or_none()
    if identity is None:
        raise _unauthenticated()
    if identity.auth_type == "guest" and (
        identity.guest_expires_at is None
        or _as_utc(identity.guest_expires_at) <= _utc_now()
    ):
        raise _unauthenticated()
    return AuthPrincipal(
        internal_user_pk=identity.internal_user_pk,
        public_user_id=identity.public_user_id,
        auth_type=identity.auth_type,
        guest_expires_at=(
            _as_utc(identity.guest_expires_at)
            if identity.guest_expires_at is not None
            else None
        ),
    )


def get_current_v3_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> AuthPrincipal:
    """Required V3 authentication: missing or unusable credentials are 401."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthenticated()
    return _resolve_principal(credentials.credentials, db)


def get_optional_v3_principal(
    request: Request,
    db: Session = Depends(get_db),
) -> AuthPrincipal | None:
    """Resolve the caller's V3 principal when one is presented.

    Returns ``None`` only when the request carries no Authorization header at
    all — those are legacy V2 callers that keep the historical default owner.

    A header that is present but unusable (non-bearer scheme, empty token,
    invalid/expired token, unknown identity) is rejected with the standard
    401 UNAUTHENTICATED error. It must never silently downgrade an
    authenticated request to the legacy default owner.

    The raw header is inspected here instead of relying on ``HTTPBearer``
    because that dependency returns ``None`` for a malformed header too, which
    would make "no credentials" and "bad credentials" indistinguishable.
    """
    authorization = request.headers.get("Authorization")
    if authorization is None or not authorization.strip():
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise _unauthenticated()
    return _resolve_principal(token.strip(), db)