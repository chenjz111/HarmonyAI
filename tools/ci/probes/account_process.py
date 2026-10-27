"""Explicit guarded process roles; all credentials here are synthetic test data."""
import json,os,time
from pathlib import Path
from datetime import timedelta


def test_account_process_role(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session,sessionmaker
    from backend.app.core import database
    from backend.app import models
    from backend.app.models.user import User
    from backend.app.models.v3.identity import UserIdentity,AuthSession
    from backend.app.models.v3.account_security import AccountCredential,RefreshProof,LoginBucket
    from backend.app.services.v3 import account_session_service as module
    from backend.app.services.v3.account_password import PasswordPolicy
    from tests.api.v3.test_account_session_r1 import NOW,PASSWORD
    from tests.api.v3.test_feedback_v31_transactions import principal
    root=Path(os.environ['CI_DB_SANDBOX']);role=os.environ['HARMONY_FEEDBACK_ROLE'];scenario=os.environ['HARMONY_FEEDBACK_SCENARIO']
    assert role in {'setup','a','b','verify'} and scenario in {'refresh','bind','limit'}
    engine=create_engine('sqlite:///'+str(root/'shared.sqlite'),connect_args={'timeout':20})
    factory=sessionmaker(bind=engine,autoflush=False)
    service=module.AccountService(password_policy=PasswordPolicy(blocked_passwords={'passwordpassword'}))
    try:
        if role=='setup':
            monkeypatch.setattr(database,'engine',engine);database.init_database()
            with Session(engine) as db:
                for owner in (7,8):
                    db.add(User(id=owner,openid=f'synthetic-process-{owner}'));db.flush()
                    db.add(UserIdentity(internal_user_pk=owner,public_user_id=f'synthetic-{owner}',auth_type='guest',guest_expires_at=NOW+timedelta(days=7)))
                db.commit()
            if scenario!='bind':
                synthetic=iter(['A'*43,'C'*43]);monkeypatch.setattr(module.secrets,'token_urlsafe',lambda size:next(synthetic))
                service.bind(factory,principal=principal().model_copy(update={'auth_type':'guest'}),username='race_user',password=PASSWORD,platform='android',now=NOW)
            if scenario=='limit':
                with Session(engine) as db:
                    row=service._bucket(db,'source','192.0.2.1',NOW);row.attempts=29;db.commit()
            return
        if role=='verify':
            with Session(engine) as db:
                if scenario=='refresh':
                    assert db.query(RefreshProof).count()==2
                    assert db.query(AuthSession).one().revoked_at is not None
                elif scenario=='bind':
                    assert db.query(AccountCredential).count()==1
                    assert db.query(UserIdentity).filter(UserIdentity.auth_type=='registered').count()==1
                else:
                    assert db.query(AuthSession).count()==2
                    assert db.query(LoginBucket).filter(LoginBucket.kind=='source').one().attempts==31
            return
        (root/f'{role}.ready').write_text('ready')
        deadline=time.monotonic()+20
        while not all((root/f'{r}.ready').exists() for r in ('a','b')):
            assert time.monotonic()<deadline,'second process did not reach barrier';time.sleep(.01)
        try:
            if scenario=='refresh':service.refresh(factory,refresh_token='A'*43,platform='android',now=NOW)
            elif scenario=='bind':service.bind(factory,principal=principal(7 if role=='a' else 8).model_copy(update={'auth_type':'guest'}),username='race_user',password=PASSWORD,platform='android',now=NOW)
            else:service.login(factory,username='race_user',password=PASSWORD,trusted_source='192.0.2.1',platform='android',now=NOW)
            status='success'
        except module.AccountDenied:status='denied'
        (root/f'{role}.result.json').write_text(json.dumps({'status':status}))
    finally:engine.dispose()
