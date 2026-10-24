from datetime import timedelta

import pytest
from sqlalchemy.orm import Session, sessionmaker

from tests.api.v3.test_feedback_v31_transactions import ready, save, principal, NOW


def clear(engine, *, key='clear-key', expected=0, now=NOW):
    from backend.app.services.v3.feedback_clear_service import clear_feedback_evidence
    from backend.app.schemas.v3.feedback_v31 import EvidenceMutationRequest
    with Session(engine, autoflush=False) as db:
        db.connection().exec_driver_sql('BEGIN IMMEDIATE')
        result = clear_feedback_evidence(db, principal=principal(),
            request=EvidenceMutationRequest(expected_evidence_epoch=expected),
            idempotency_key=key, now_utc=now)
        db.commit()
        return result


def test_clear_receipt_cutoff_and_epoch_commit_together_and_replay_original(ready):
    saved = save(ready)
    first = clear(ready, expected=1)
    save(ready, key='after', changes={'expected_evidence_epoch':2})
    replay = clear(ready, expected=1, now=NOW+timedelta(days=1))
    assert replay == first
    assert first.resulting_feedback_epoch == 2 and first.operation_id and first.cutoff == NOW
    from backend.app.services.v3.feedback_v31_queries import read_owned_feedback_page
    with Session(ready) as db:
        rows, total = read_owned_feedback_page(db, principal=principal())
        assert total == 2 and saved.feedback_id in {r.feedback_id for r in rows}
    with ready.connect() as db:
        assert db.exec_driver_sql('SELECT count(*) FROM feedback_clear_receipts').scalar_one() == 1
        assert db.exec_driver_sql('SELECT feedback_evidence_epoch FROM owner_music_state').scalar_one() == 3


def test_changed_request_cannot_reuse_clear_key(ready):
    from backend.app.services.v3.feedback_v31_contract import FeedbackFingerprintConflict
    clear(ready)
    with pytest.raises(FeedbackFingerprintConflict):
        clear(ready, expected=1)


def test_clear_failure_rolls_back_cutoff_receipt_and_owner_epoch(ready, monkeypatch):
    from backend.app.services.v3 import feedback_clear_service as service
    def fail(*args, **kwargs):
        raise RuntimeError('synthetic receipt insert failure')
    monkeypatch.setattr(service, '_insert_receipt', fail)
    with pytest.raises(RuntimeError, match='synthetic receipt insert failure'):
        clear(ready)
    with ready.connect() as db:
        assert db.exec_driver_sql('SELECT count(*) FROM feedback_clear_receipts').scalar_one() == 0
        assert db.exec_driver_sql('SELECT count(*) FROM owner_music_state').scalar_one() == 0


def test_clear_receipt_has_no_expiry_and_is_immutable(ready):
    from sqlalchemy import inspect
    from sqlalchemy.exc import IntegrityError
    result = clear(ready)
    assert not {'expires_at','ttl'}.intersection(c['name'] for c in inspect(ready).get_columns('feedback_clear_receipts'))
    for sql in ("UPDATE feedback_clear_receipts SET resulting_feedback_epoch=99",
                "DELETE FROM feedback_clear_receipts",
                "INSERT OR REPLACE INTO feedback_clear_receipts SELECT * FROM feedback_clear_receipts"):
        with pytest.raises(IntegrityError):
            with ready.begin() as db:
                db.exec_driver_sql(sql)
    assert clear(ready) == result


def test_clear_commit_unknown_recovers_exact_original_receipt(ready):
    from backend.app.services.v3.feedback_clear_service import clear_with_commit
    from backend.app.schemas.v3.feedback_v31 import EvidenceMutationRequest
    class AckLost(Session):
        def commit(self):
            super().commit()
            raise OSError('synthetic lost ACK')
    result = clear_with_commit(sessionmaker(bind=ready,class_=AckLost),
        verification_factory=sessionmaker(bind=ready), principal=principal(),
        request=EvidenceMutationRequest(expected_evidence_epoch=0),
        idempotency_key='unknown-clear', now_utc=NOW)
    assert result == clear(ready, key='unknown-clear') and result.resulting_feedback_epoch == 1
