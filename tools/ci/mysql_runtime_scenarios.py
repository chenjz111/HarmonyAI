"""Synthetic real-MySQL transactions, called only by the isolated TLS harness."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from sqlalchemy import text
from sqlalchemy.orm import Session,sessionmaker


def verify(engine):
    from tests.api.v3.test_int2_0012_contract import seed
    from tests.api.v3.test_feedback_v31_transactions import body,principal,NOW
    from backend.app.schemas.v3.feedback_v31 import FeedbackV31,EvidenceMutationRequest
    from backend.app.services.v3.feedback_v31_transactions import save_feedback
    from backend.app.services.v3.feedback_clear_service import clear_with_commit
    from backend.app.services.v3.feedback_v31_service import tombstone_owned_feedback
    from backend.app.services.v3.feedback_v31_contract import FeedbackGone
    from backend.app.services.v3.feedback_v31_queries import read_owned_feedback_page
    from backend.app.services.v3.account_session_service import AccountService,AccountDenied
    from backend.app.services.v3.account_password import PasswordPolicy
    from backend.app.models.v3.identity import UserIdentity,AuthSession
    factory=sessionmaker(bind=engine,autoflush=False)
    with engine.begin() as db:
        for owner in (7,1):
            if db.execute(text('SELECT id FROM users WHERE id=:id'),{'id':owner}).first() is None:
                db.execute(text('INSERT INTO users(id,openid) VALUES(:id,:name)'),{'id':owner,'name':f'synthetic-{owner}'})
        seed(db)
        db.execute(text("INSERT INTO music_playback_events(internal_user_pk,event_id,music_asset_id,event_type,source_context_id,occurred_at) VALUES(7,'event-a','music_shared','play_started','ctx_a','2026-10-24 00:00:00')"))
    request=FeedbackV31.model_validate(body())
    def save():return save_feedback(factory,verification_factory=factory,principal=principal(),request=request,idempotency_key='real-mysql-save',now_utc=NOW)
    save_barrier=Barrier(2)
    def concurrent_save():
        save_barrier.wait(timeout=10)
        return save()
    with ThreadPoolExecutor(max_workers=2) as pool:
        saves=[pool.submit(concurrent_save) for _ in range(2)]
        saved=[future.result(timeout=20) for future in saves]
    assert sorted(value.replayed for value in saved)==[False,True]
    first=next(value for value in saved if not value.replayed);replay=save()
    assert first.feedback_id==replay.feedback_id and not first.replayed and replay.replayed
    clear_request=EvidenceMutationRequest(expected_evidence_epoch=1)
    def clear():return clear_with_commit(factory,verification_factory=factory,principal=principal(),request=clear_request,idempotency_key='real-mysql-clear',now_utc=NOW)
    cleared=clear();assert clear()==cleared and cleared.resulting_feedback_epoch==2
    with factory() as db:
        rows,total=read_owned_feedback_page(db,principal=principal())
        assert total==1 and rows[0].feedback_id==first.feedback_id
        assert tombstone_owned_feedback(db,principal=principal(),feedback_id=first.feedback_id,expected_epoch=2,now_utc=NOW)==3
        db.commit()
    try:save()
    except FeedbackGone:pass
    else:raise AssertionError('MySQL tombstone revived by replay')
    with factory() as db:
        db.add(UserIdentity(internal_user_pk=7,public_user_id='synthetic-7',auth_type='guest',guest_expires_at=NOW+timedelta(days=7)))
        db.commit()
    service=AccountService(password_policy=PasswordPolicy(blocked_passwords={'passwordpassword'}))
    tokens=service.bind(factory,principal=principal().model_copy(update={'auth_type':'guest'}),username='Mysql_user',password='synthetic-safe-long-passphrase',platform='android',now=NOW)
    assert tokens.internal_user_pk==7
    barrier=Barrier(2)
    def rotate():
        barrier.wait(timeout=10)
        try:return service.refresh(factory,refresh_token=tokens.refresh_token,platform='android',now=NOW+timedelta(minutes=1))
        except AccountDenied:return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(rotate) for _ in range(2)]
        results=[future.result(timeout=20) for future in futures]
    assert sum(value is not None for value in results)==1
    with factory() as db:assert db.get(AuthSession,tokens.sid).revoked_at is not None
    survivor=next(value for value in results if value is not None)
    try:service.refresh(factory,refresh_token=survivor.refresh_token,platform='android',now=NOW+timedelta(minutes=2))
    except AccountDenied:pass
    else:raise AssertionError('replayed family remained active')
    login=service.login(factory,username='mysql_user',password='synthetic-safe-long-passphrase',trusted_source='192.0.2.1',platform='android',now=NOW+timedelta(minutes=3))
    service.logout(factory,owner=7,sid=login.sid,all_devices=True,now=NOW+timedelta(minutes=4))
    with factory() as db:
        assert db.get(AuthSession,login.sid).revoked_at is not None
        assert db.get(UserIdentity,7).auth_type=='registered'
        assert db.execute(text('SELECT count(*) FROM generation_tasks WHERE internal_user_pk=7')).scalar_one()==2
    return {'concurrent_feedback_save_one_write_one_replay':True,'feedback_save_replay':True,'clear_receipt_preserves_history':True,'tombstone_precedes_replay':True,'binding_keeps_history':True,'concurrent_refresh_one_winner_and_family_revoked':True,'login_logout_all':True}
