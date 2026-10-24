"""Sequential compatibility through explicit candidate facades, not live routes."""
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from tests.api.v3.test_int2_feedback_0013_candidate import database, candidate
from tests.api.v3.test_int2_pf1b_contract import body, principal
from tests.api.v3.test_s7_pf1b_save import save, NOW
from tests.api.v3.test_int2_0012_contract import seed
from backend.app.schemas.v3.feedback import FeedbackV3
from backend.drafts.s7_feedback_consent.contracts import FeedbackGone, FeedbackContentUnverified
from backend.app.services.v3.feedback_v31_candidate_service import tombstone_owned_feedback
from backend.app.services.v3.feedback_service import OwnedResourceNotFound, get_latest_preference_snapshot
from backend.app.services.v3.feedback_v31_legacy_candidate import (
    CandidateSchemaUnavailable, list_legacy_history_candidate, submit_legacy_feedback_candidate,
)


@pytest.fixture
def ready(tmp_path, monkeypatch):
    """Use actual fresh app initialization, not the minimal migration fixture.

    The latter deliberately lacks some Session ORM fields and cannot stand in
    for the full legacy service's schema. No production upgrade claim is made.
    """
    from backend.app.core import database as application_db
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy-compat.sqlite'}")
    monkeypatch.setattr(application_db, "engine", engine)
    application_db.init_database()
    with engine.begin() as conn:
        conn.exec_driver_sql("INSERT INTO users(id,openid) VALUES(7,'synthetic-seven')")
        conn.exec_driver_sql("INSERT INTO sessions(id,user_id,session_id) VALUES(1,7,'sess_legacy')")
        seed(conn)
        conn.exec_driver_sql("INSERT INTO feedback_v3(feedback_id,internal_user_pk,session_row_id,music_asset_id,change_label,liked_features_json,adjustment_preferences_json,idempotency_key,preference_update_status) VALUES('old-feedback',7,1,'music_shared','no_change','[]','[]','old-key','skipped')")
        conn.exec_driver_sql("INSERT INTO user_music_preferences(profile_id,internal_user_pk,current_version_id) VALUES('profile',7,'old-version')")
        conn.exec_driver_sql("INSERT INTO user_music_preference_versions(preference_version_id,profile_id,version,feedback_count,minimum_samples_for_application) VALUES('old-version','profile',1,0,3)")
    candidate().install_sqlite(engine)
    from tests.api.v3.test_int2_pf1b_contract import play
    play(engine)
    yield engine
    engine.dispose()


def legacy_request(**changes):
    payload = body()
    for key in ("source_context_id", "playback_event_id", "expected_evidence_epoch"):
        payload.pop(key)
    payload.update(schema_version="feedback_v3.0", **changes)
    return FeedbackV3.model_validate(payload)


def test_legacy_save_replay_and_tombstone_history_total(ready):
    with Session(ready, autoflush=False) as db:
        first, replayed = submit_legacy_feedback_candidate(db, principal(), legacy_request(comment="synthetic private comment"), "legacy-new")
        assert replayed is False and first.preference_update.applied is False
        repeated, replayed = submit_legacy_feedback_candidate(db, principal(), legacy_request(), "legacy-new")
        assert replayed is True and repeated.feedback_id == first.feedback_id
        history = list_legacy_history_candidate(db, principal())
        assert history.total == 2
        db.rollback()
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        assert tombstone_owned_feedback(db, principal=principal(), feedback_id=first.feedback_id, expected_epoch=0, now_utc=NOW) == 1
        db.commit()
        history = list_legacy_history_candidate(db, principal())
        assert history.total == 1 and [r.feedback_id for r in history.items] == ["old-feedback"]
        with pytest.raises(FeedbackGone):
            submit_legacy_feedback_candidate(db, principal(), legacy_request(), "legacy-new")
        assert get_latest_preference_snapshot(db, principal()) is None
    with ready.connect() as conn:
        comment = conn.execute(text("SELECT comment_ciphertext FROM feedback_v3 WHERE feedback_id=:id"), {"id": first.feedback_id}).scalar()
        assert comment.startswith("sha256:") and "synthetic private comment" not in comment
        assert conn.exec_driver_sql("SELECT count(*) FROM feedback_v3 WHERE idempotency_key='legacy-new'").scalar() == 1
        assert conn.exec_driver_sql("SELECT current_version_id FROM user_music_preferences").scalar() == "old-version"


def test_other_owner_never_sees_or_replays_row(ready):
    with Session(ready, autoflush=False) as db:
        assert list_legacy_history_candidate(db, principal(1)).total == 0
        with pytest.raises(OwnedResourceNotFound):
            submit_legacy_feedback_candidate(db, principal(1), legacy_request(), "old-key")


def test_v31_fingerprint_cannot_be_replayed_through_legacy_body(ready):
    save(ready)
    with Session(ready, autoflush=False) as db:
        with pytest.raises(FeedbackContentUnverified):
            submit_legacy_feedback_candidate(db, principal(), legacy_request(), "new-key")


def test_legacy_facade_rejects_v31_request_instead_of_dropping_consent(ready):
    from backend.drafts.s7_feedback_consent.contracts import FeedbackV31
    request = FeedbackV31.model_validate(body(learning_consent=True, consent_policy_version="unapproved"))
    with Session(ready, autoflush=False) as db:
        with pytest.raises(TypeError):
            submit_legacy_feedback_candidate(db, principal(), request, "version-confusion")
    with ready.connect() as conn:
        assert conn.exec_driver_sql("SELECT count(*) FROM feedback_v3 WHERE idempotency_key='version-confusion'").scalar() == 0


def test_missing_candidate_schema_fails_closed_without_install(database):
    with Session(database, autoflush=False) as db:
        with pytest.raises(CandidateSchemaUnavailable):
            list_legacy_history_candidate(db, principal())
        with pytest.raises(CandidateSchemaUnavailable):
            submit_legacy_feedback_candidate(db, principal(), legacy_request(), "old-key")
    with database.connect() as conn:
        assert conn.exec_driver_sql("SELECT count(*) FROM schema_migrations").scalar() == 12
        assert conn.exec_driver_sql("SELECT count(*) FROM sqlite_schema WHERE name='int2_feedback_0013_review'").scalar() == 0
