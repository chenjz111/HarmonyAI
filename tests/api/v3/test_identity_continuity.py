"""PD001/U01: read-only identity validation, never replacement or renewal."""
from datetime import datetime,timedelta,timezone
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.orm import Session
from backend.app.main import app
from backend.app.core.config import settings
from backend.app.models.v3.identity import UserIdentity

client=TestClient(app)

def test_current_identity_preserves_owner_token_expiry_and_row_count(db_session_factory):
    issued=client.post('/api/v3/auth/guest').json()['data']
    token=issued['access_token']
    with db_session_factory() as db:
        count=db.query(UserIdentity).count()
    for _ in range(2):
        response=client.get('/api/v3/auth/identity',headers={'Authorization':'Bearer '+token})
        assert response.status_code==200
        assert response.headers.get('cache-control')=='no-store'
        # Vary is a field-name list; CORS may append Origin on hosted middleware.
        vary={name.strip().lower() for name in response.headers.get('vary','').split(',')}
        assert 'authorization' in vary
        assert '*' not in vary
        assert response.json()['data']=={'public_user_id':issued['public_user_id'],'auth_type':'guest'}
        assert 'access_token' not in response.json()['data']
    with db_session_factory() as db:
        assert db.query(UserIdentity).count()==count

def test_current_identity_denies_missing_expired_and_database_expired_guest(db_session_factory):
    assert client.get('/api/v3/auth/identity').status_code==401
    issued=client.post('/api/v3/auth/guest').json()['data']
    claims=jwt.get_unverified_claims(issued['access_token'])
    claims['exp']=int((datetime.now(timezone.utc)-timedelta(seconds=1)).timestamp())
    expired=jwt.encode(claims,settings.JWT_SECRET_KEY,algorithm='HS256')
    assert client.get('/api/v3/auth/identity',headers={'Authorization':'Bearer '+expired}).status_code==401
    with db_session_factory() as db:
        identity=db.query(UserIdentity).filter_by(public_user_id=issued['public_user_id']).one()
        identity.guest_expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)
        db.commit()
    assert client.get('/api/v3/auth/identity',headers={'Authorization':'Bearer '+issued['access_token']}).status_code==401
