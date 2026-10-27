"""Read-only candidate: unknown never means the original write cannot arrive."""
from sqlalchemy import event,insert,select
from sqlalchemy.orm import Session
from tests.api.v3.test_feedback_v31_transactions import ready, save, principal, NOW


def test_owner_key_event_scope_and_tombstone(ready):
    from backend.app.services.v3.feedback_recovery_candidate import read_recovery_status
    from backend.app.services.v3.feedback_v31_service import tombstone_owned_feedback
    args=dict(principal=principal(),idempotency_key='recovery-key',music_id='music_shared',source_context_id='ctx_a',playback_event_id='event-a')
    with Session(ready) as db:
        assert read_recovery_status(db,**args).status=='unknown'
    saved=save(ready,key='recovery-key')
    with Session(ready) as db:
        assert read_recovery_status(db,**args).status=='record_present_unverified'
        assert read_recovery_status(db,**{**args,'principal':principal(1)}).status=='unknown'
        assert read_recovery_status(db,**{**args,'playback_event_id':'other'}).status=='unknown'
        assert read_recovery_status(db,**{**args,'source_context_id':'ctx_b'}).status=='unknown'
        assert read_recovery_status(db,**{**args,'music_id':'other'}).status=='unknown'
    from backend.app.models.v3.feedback import FeedbackV3
    with Session(ready) as db:
        table=FeedbackV3.__table__
        legacy=dict(db.execute(select(table).where(table.c.feedback_id==saved.feedback_id)).mappings().one())
        legacy.update(feedback_id='synthetic-legacy',idempotency_key='legacy-key',request_fingerprint=None)
        db.execute(insert(table).values(**legacy));db.commit()
        assert read_recovery_status(db,**{**args,'idempotency_key':'legacy-key'}).status=='unknown'
    with Session(ready) as db:
        db.connection().exec_driver_sql('BEGIN IMMEDIATE')
        tombstone_owned_feedback(db,principal=principal(),feedback_id=saved.feedback_id,expected_epoch=1,now_utc=NOW)
        db.commit()
    with Session(ready) as db:
        assert read_recovery_status(db,**args).status=='deleted'


def test_read_does_not_flush_unrelated_pending_writes(ready):
    from backend.app.models.user import User
    from backend.app.services.v3.feedback_recovery_candidate import read_recovery_status
    with Session(ready) as db:
        pending=User(openid='synthetic-unrelated')
        db.add(pending);flushes=[]
        event.listen(db,'before_flush',lambda *args:flushes.append(True))
        result=read_recovery_status(db,principal=principal(),idempotency_key='no-such-key',music_id='music_shared',source_context_id='ctx_a',playback_event_id='event-a')
        assert result.status=='unknown' and flushes==[] and pending in db.new
