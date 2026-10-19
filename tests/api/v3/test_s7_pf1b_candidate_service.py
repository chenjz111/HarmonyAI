"""PF-owned behavior against the isolated 0013 candidate, never app startup."""

from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from tests.api.v3.test_int2_feedback_0013_candidate import database, candidate
from tests.api.v3.test_int2_pf1b_contract import principal
from backend.app.services.v3.feedback_v31_candidate_service import (
    FeedbackNotFound,
    list_owned_feedback,
    tombstone_owned_feedback,
)


def test_owner_list_excludes_other_owner_and_tombstone_without_writing(database):
    candidate().install_sqlite(database)
    with Session(database, autoflush=False) as db:
        assert [row.feedback_id for row in list_owned_feedback(db, principal(7))] == ["old-feedback"]
        assert list_owned_feedback(db, principal(8)) == []
        db.rollback()
    with database.connect() as conn:
        assert conn.exec_driver_sql("SELECT count(*) FROM owner_music_state WHERE owner_internal_user_pk=8").scalar() == 0


def test_first_tombstone_bumps_epoch_once_and_repeat_does_not(database):
    candidate().install_sqlite(database)
    now = datetime(2026, 10, 20, tzinfo=timezone.utc)
    with Session(database, autoflush=False) as db:
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        first = tombstone_owned_feedback(db, principal=principal(7), feedback_id="old-feedback", expected_epoch=0, now_utc=now)
        assert first == 1
        db.commit()
    with Session(database, autoflush=False) as db:
        assert list_owned_feedback(db, principal(7)) == []
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        assert tombstone_owned_feedback(db, principal=principal(7), feedback_id="old-feedback", expected_epoch=1, now_utc=now) == 1
        db.commit()
    with database.connect() as conn:
        assert conn.exec_driver_sql("SELECT feedback_evidence_epoch FROM owner_music_state WHERE owner_internal_user_pk=7").scalar() == 1
        assert conn.exec_driver_sql("SELECT current_version_id FROM user_music_preferences WHERE internal_user_pk=7").scalar() == "old-version"


def test_cross_owner_tombstone_does_not_change_state(database):
    candidate().install_sqlite(database)
    with Session(database, autoflush=False) as db:
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        with pytest.raises(FeedbackNotFound):
            tombstone_owned_feedback(db, principal=principal(8), feedback_id="old-feedback", expected_epoch=0, now_utc=datetime(2026, 10, 20, tzinfo=timezone.utc))
        db.rollback()
    with database.connect() as conn:
        assert conn.exec_driver_sql("SELECT deleted_at FROM feedback_v3 WHERE feedback_id='old-feedback'").scalar() is None
        assert conn.exec_driver_sql("SELECT count(*) FROM owner_music_state WHERE owner_internal_user_pk=8").scalar() == 0
