"""PF candidate transaction behavior on independent file-SQLite connections."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from tests.api.v3.test_int2_feedback_0013_candidate import database, candidate
from tests.api.v3.test_int2_pf1b_contract import principal
from backend.drafts.s7_feedback_consent.contracts import EvidenceEpochConflict
from backend.drafts.s7_feedback_consent.models import FeedbackCandidate
from backend.app.services.v3.feedback_v31_candidate_service import tombstone_owned_feedback
from backend.app.services.v3.owner_music_state_service import advance_feedback_epoch

NOW = datetime(2026, 10, 22, tzinfo=timezone.utc)


def delete(db, expected=0):
    return tombstone_owned_feedback(db, principal=principal(), feedback_id="old-feedback",
                                    expected_epoch=expected, now_utc=NOW)


def test_stale_epoch_does_not_delete(database):
    candidate().install_sqlite(database)
    with Session(database, autoflush=False) as db:
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        advance_feedback_epoch(db, internal_user_pk=7)
        db.commit()
    with Session(database, autoflush=False) as db:
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        with pytest.raises(EvidenceEpochConflict):
            delete(db)
        db.rollback()
    with database.connect() as conn:
        assert conn.execute(text("SELECT deleted_at FROM feedback_v3 WHERE feedback_id='old-feedback'")).scalar() is None


def test_delete_rollback_restores_row_and_epoch(database):
    candidate().install_sqlite(database)
    with Session(database, autoflush=False) as db:
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        assert delete(db) == 1
        db.rollback()
    with database.connect() as conn:
        assert conn.exec_driver_sql("SELECT deleted_at FROM feedback_v3 WHERE feedback_id='old-feedback'").scalar() is None
        assert conn.exec_driver_sql("SELECT count(*) FROM owner_music_state").scalar() == 0


def test_stale_identity_map_cannot_repeat_tombstone_write(database):
    candidate().install_sqlite(database)
    with Session(database, autoflush=False, expire_on_commit=False) as stale:
        held = stale.scalar(select(FeedbackCandidate).where(FeedbackCandidate.feedback_id == "old-feedback"))
        stale.commit()
        assert held.deleted_at is None
        with Session(database, autoflush=False) as writer:
            writer.connection().exec_driver_sql("BEGIN IMMEDIATE")
            assert delete(writer) == 1
            writer.commit()
        stale.connection().exec_driver_sql("BEGIN IMMEDIATE")
        assert delete(stale, expected=1) == 1
        stale.commit()
    with database.connect() as conn:
        assert conn.exec_driver_sql("SELECT feedback_evidence_epoch FROM owner_music_state").scalar() == 1


def test_two_connections_delete_only_once(database):
    candidate().install_sqlite(database)
    gate = Barrier(2)
    def worker():
        with Session(database, autoflush=False) as db:
            gate.wait(timeout=10)
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
            result = delete(db)
            db.commit()
            return result
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker) for _ in range(2)]
        assert [f.result(timeout=20) for f in futures] == [1, 1]
    with database.connect() as conn:
        assert conn.exec_driver_sql("SELECT feedback_evidence_epoch FROM owner_music_state").scalar() == 1


def test_delete_rejects_non_utc_and_propagates_state_creation_conflict(database, monkeypatch):
    candidate().install_sqlite(database)
    from backend.app.services.v3 import feedback_v31_candidate_service as service
    with Session(database, autoflush=False) as db:
        with pytest.raises(ValueError):
            service.tombstone_owned_feedback(db, principal=principal(), feedback_id="old-feedback",
                                            expected_epoch=0, now_utc=NOW.replace(tzinfo=None))
        def competing_state(*args, **kwargs):
            raise IntegrityError("synthetic state insert conflict", {}, RuntimeError("unique"))
        monkeypatch.setattr(service, "lock_owner_music_state", competing_state)
        with pytest.raises(IntegrityError):
            delete(db)
        db.rollback()
    with database.connect() as conn:
        assert conn.exec_driver_sql("SELECT deleted_at FROM feedback_v3 WHERE feedback_id='old-feedback'").scalar() is None


@pytest.mark.parametrize("different", [False, True])
def test_two_connections_same_key_have_one_row_and_one_epoch(database, different):
    from tests.api.v3.test_int2_pf1b_contract import body, play
    from backend.drafts.s7_feedback_consent.contracts import FeedbackV31, FeedbackFingerprintConflict
    from backend.app.services.v3.feedback_v31_candidate_service import save_unconsented_feedback
    candidate().install_sqlite(database)
    play(database)
    gate = Barrier(2)
    def worker(index):
        payload = body(post_state={"change_label": "worse"}) if different and index else body()
        with Session(database, autoflush=False) as db:
            gate.wait(timeout=10)
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
            try:
                result = save_unconsented_feedback(db, principal=principal(),
                    request=FeedbackV31.model_validate(payload), idempotency_key="racing-key", now_utc=NOW)
                db.commit()
                return result
            except FeedbackFingerprintConflict:
                db.rollback()
                return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, i) for i in range(2)]
        results = [f.result(timeout=20) for f in futures]
    if different:
        assert results.count("conflict") == 1
    else:
        assert results[0].feedback_id == results[1].feedback_id
        assert sorted(r.replayed for r in results) == [False, True]
    with database.connect() as conn:
        assert conn.exec_driver_sql("SELECT count(*) FROM feedback_v3 WHERE idempotency_key='racing-key'").scalar() == 1
        assert conn.exec_driver_sql("SELECT feedback_evidence_epoch FROM owner_music_state").scalar() == 1
