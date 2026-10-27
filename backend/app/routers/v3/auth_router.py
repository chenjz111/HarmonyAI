"""V3 guest authentication endpoints."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.routers.v3.transport import v3_success
from backend.app.schemas.v3.common import GuestAuthResponse, AuthPrincipal
from backend.app.schemas.v3.envelope import V3SuccessEnvelope
from backend.app.services.v3.auth_service import create_guest_principal, get_current_v3_principal


router = APIRouter()


@router.get('/auth/identity')
def read_identity(response: Response, principal: AuthPrincipal = Depends(get_current_v3_principal)):
    """Validate the existing credential; never issue/renew tokens or create rows."""
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Vary'] = 'Authorization'
    return v3_success(dict(public_user_id=principal.public_user_id, auth_type=principal.auth_type))


@router.post(
    "/auth/guest",
    response_model=V3SuccessEnvelope[GuestAuthResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_guest(
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[GuestAuthResponse]:
    return v3_success(create_guest_principal(db))
