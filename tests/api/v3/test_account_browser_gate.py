"""Synthetic browser gate; no deployment-Origin or actual HTTPS acceptance."""
from datetime import timedelta
from starlette.responses import Response
from sqlalchemy.orm import Session
import pytest
from tests.api.v3.test_feedback_v31_transactions import ready
from tests.api.v3.test_account_session_r1 import bind,NOW


def test_cookie_has_host_secure_http_only_lax_and_no_domain():
    from backend.app.services.v3.account_browser_gate import set_refresh_cookie
    response=Response();set_refresh_cookie(response,'A'*43,expires_at=NOW+timedelta(days=7),now=NOW)
    cookie=response.headers['set-cookie']
    assert '__Host-harmonyai-refresh=' in cookie and 'HttpOnly' in cookie and 'Secure' in cookie
    assert 'SameSite=lax' in cookie and 'Path=/' in cookie and 'Domain' not in cookie


@pytest.mark.parametrize('origins',[[],['*'],['http://test.invalid'],['https://test.invalid/path'],['https://user@test.invalid']])
def test_unverified_origin_inventory_fails_closed(origins):
    from backend.app.services.v3.account_browser_gate import BrowserMutationGate
    with pytest.raises(ValueError):BrowserMutationGate(approved_origins=origins)


def test_csrf_is_session_bound_and_origin_is_exact(ready):
    from backend.app.services.v3.account_browser_gate import BrowserMutationGate
    from backend.app.services.v3.account_session_service import AccountDenied
    from backend.app.models.v3.account_security import RegisteredSessionState
    s,tokens=bind(ready)
    with Session(ready) as db:
        # Explicit fixture bypass of the still-closed production H5 issuer.
        db.get(RegisteredSessionState,tokens.sid).platform='h5';db.commit()
        gate=BrowserMutationGate(approved_origins=['https://test.invalid'])
        gate.verify(db,sid=tokens.sid,origin='https://test.invalid',csrf_token=tokens.csrf_token,scheme='https',now=NOW)
        for changes in ({'origin':'https://test.invalid.evil'},{'origin':'null'},{'csrf_token':'B'*43},{'sid':'missing'},{'scheme':'http'}):
            values=dict(sid=tokens.sid,origin='https://test.invalid',csrf_token=tokens.csrf_token,scheme='https',now=NOW);values.update(changes)
            with pytest.raises(AccountDenied):gate.verify(db,**values)
