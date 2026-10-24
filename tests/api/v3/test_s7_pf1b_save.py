"""Real candidate persistence, proof, idempotency and transaction boundaries."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.api.v3.test_int2_feedback_0013_candidate import database, candidate
from tests.api.v3.test_int2_pf1b_contract import body, play, principal
from backend.drafts.s7_feedback_consent.contracts import (
    FeedbackV31, FeedbackFingerprintConflict, FeedbackGone,
    LegacyFingerprintUnavailable, PlaybackProofUnavailable, FeedbackContentUnverified,
)
from backend.app.services.v3 import feedback_v31_candidate_service as service

NOW = datetime(2026, 10, 22, tzinfo=timezone.utc)


@pytest.fixture
def ready(database):
    candidate().install_sqlite(database)
    play(database)
    return database


def save(engine, *, key="new-key", payload=None, owner=7):
    with Session(engine, autoflush=False) as db:
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        result = service.save_unconsented_feedback(db, principal=principal(owner),
            request=FeedbackV31.model_validate(payload or body()), idempotency_key=key, now_utc=NOW)
        db.commit()
        return result


def test_save_replays_same_result_without_duplicate_row_or_epochs(ready, monkeypatch):
    from backend.app.services.v3 import feedback_service
    def forbidden(*args, **kwargs):
        pytest.fail("candidate invoked learning")
    monkeypatch.setattr(feedback_service, "_learn_preferences", forbidden)
    first = save(ready, payload=body(favorite=False))
    repeated = save(ready, payload=body(favorite=False))
    assert first.feedback_id == repeated.feedback_id
    assert first.replayed is False and repeated.replayed is True
    assert first.learning_applied is False and repeated.learning_applied is False
    assert (first.current_feedback_epoch, repeated.current_feedback_epoch) == (1, 1)
    with ready.connect() as conn:
        row = conn.execute(text("SELECT learning_consent,consent_policy_version,consented_at,evidence_epoch,preference_update_status FROM feedback_v3 WHERE feedback_id=:id"), {"id": first.feedback_id}).one()
        assert tuple(row) == (0, None, None, 0, "skipped")
        assert conn.exec_driver_sql("SELECT count(*) FROM feedback_v3 WHERE idempotency_key='new-key'").scalar() == 1
        assert conn.exec_driver_sql("SELECT library_epoch FROM owner_music_state WHERE owner_internal_user_pk=7").scalar() == 1


def test_false_policy_echo_and_selection_order_normalize_for_replay(ready):
    first = save(ready, payload=body(liked_features=["relaxing", "focus"], consent_policy_version="old"))
    second = save(ready, payload=body(liked_features=["focus", "relaxing"], learning_consent=False))
    assert first.feedback_id == second.feedback_id and second.replayed


@pytest.mark.parametrize("changes", [
    {"post_state": {"change_label": "worse"}}, {"expected_evidence_epoch": 1},
])
def test_same_key_changed_request_conflicts(ready, changes):
    save(ready)
    with pytest.raises(FeedbackFingerprintConflict):
        save(ready, payload=body(**changes))
    with ready.connect() as conn:
        assert conn.exec_driver_sql("SELECT count(*) FROM feedback_v3 WHERE idempotency_key='new-key'").scalar() == 1
        assert conn.exec_driver_sql("SELECT feedback_evidence_epoch FROM owner_music_state").scalar() == 1


def test_exact_replay_ignores_stale_expected_epoch_but_returns_current(ready):
    first = save(ready)
    save(ready, key="next-key", payload=body(expected_evidence_epoch=1))
    replay = save(ready)
    assert replay.feedback_id == first.feedback_id
    assert replay.current_feedback_epoch == 2 and replay.replayed


def test_legacy_and_tombstone_precede_replay(ready):
    with pytest.raises(LegacyFingerprintUnavailable):
        save(ready, key="old-key")
    first = save(ready)
    with Session(ready, autoflush=False) as db:
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        service.tombstone_owned_feedback(db, principal=principal(), feedback_id=first.feedback_id,
                                        expected_epoch=1, now_utc=NOW)
        db.commit()
    with pytest.raises(FeedbackGone):
        save(ready, payload=body(post_state={"change_label": "worse"}))


@pytest.mark.parametrize("owner,changes", [
    (1, {}), (7, {"playback_event_id": "missing"}),
    (7, {"source_context_id": "ctx_b"}), (7, {"session_id": "synthetic-other"}),
    (7, {"music_ref": {"music_id": "missing", "source_type": "matched"}}),
    (7, {"music_ref": {"music_id": "music_shared", "source_type": "generated"}}),
])
def test_invalid_proof_or_asset_rejected_without_feedback(ready, owner, changes):
    with pytest.raises(PlaybackProofUnavailable):
        save(ready, owner=owner, payload=body(**changes))
    with ready.connect() as conn:
        assert conn.exec_driver_sql("SELECT count(*) FROM feedback_v3 WHERE idempotency_key='new-key'").scalar() == 0
        assert conn.exec_driver_sql("SELECT count(*) FROM owner_music_state").scalar() == 0


def test_same_key_is_owner_scoped(ready):
    first = save(ready)
    play(ready, owner=1, event="event-b", context="ctx_other")
    second = save(ready, owner=1, payload=body(session_id="synthetic-other",
                    source_context_id="ctx_other", playback_event_id="event-b"))
    assert first.feedback_id != second.feedback_id
    with ready.connect() as conn:
        assert conn.exec_driver_sql("SELECT count(*) FROM feedback_v3 WHERE idempotency_key='new-key'").scalar() == 2


def test_save_is_uncommitted_and_caller_rollback_removes_all_writes(ready):
    with Session(ready, autoflush=False) as db:
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        result = service.save_unconsented_feedback(db, principal=principal(), request=FeedbackV31.model_validate(body(favorite=False)),
                                                  idempotency_key="rollback-key", now_utc=NOW)
        with ready.connect() as other:
            assert other.execute(text("SELECT count(*) FROM feedback_v3 WHERE feedback_id=:id"), {"id": result.feedback_id}).scalar() == 0
        db.rollback()
    with ready.connect() as conn:
        assert conn.exec_driver_sql("SELECT count(*) FROM owner_music_state").scalar() == 0
        assert conn.exec_driver_sql("SELECT count(*) FROM favorites WHERE internal_user_pk=7").scalar() == 1


def test_failed_post_flush_content_verification_rolls_back(ready, monkeypatch):
    def reject(row, request):
        assert row["feedback_id"] and row["created_at"]
        assert row["source_task_id"] == "ctx_a"
        raise FeedbackContentUnverified("synthetic validation failure")
    monkeypatch.setattr(service, "verify_persisted_feedback_content", reject)
    with pytest.raises(FeedbackContentUnverified):
        save(ready)
    with ready.connect() as conn:
        assert conn.exec_driver_sql("SELECT count(*) FROM feedback_v3 WHERE idempotency_key='new-key'").scalar() == 0
        assert conn.exec_driver_sql("SELECT count(*) FROM owner_music_state").scalar() == 0


@pytest.mark.parametrize("payload", [body(learning_consent=True, consent_policy_version="unapproved")])
def test_true_consent_stays_gated(ready, payload):
    with pytest.raises(service.CandidateConsentNotEnabled):
        save(ready, payload=payload)


@pytest.mark.parametrize("key", ["", " ", "x" * 129])
def test_invalid_key_rejected(ready, key):
    with pytest.raises(ValueError):
        save(ready, key=key)


def test_service_requires_exact_dto(ready):
    with Session(ready, autoflush=False) as db:
        with pytest.raises(TypeError):
            service.save_unconsented_feedback(db, principal=principal(), request=body(),
                                              idempotency_key="raw", now_utc=NOW)


def test_backend_proof_failure_prevents_candidate_save(ready, monkeypatch):
    from backend.app.services.v3 import music_library_access
    def deny(db, **kwargs):
        assert kwargs["playback_event_id"] == "event-a"
        assert kwargs["principal"].internal_user_pk == 7
        raise music_library_access.PlaybackProofUnavailable
    monkeypatch.setattr(music_library_access, "resolve_feedback_playback_proof", deny)
    with pytest.raises(PlaybackProofUnavailable):
        save(ready)
    with ready.connect() as conn:
        assert conn.exec_driver_sql("SELECT count(*) FROM feedback_v3 WHERE idempotency_key='new-key'").scalar() == 0


def test_backend_atomic_cas_failure_rolls_back_candidate_save(ready, monkeypatch):
    from backend.app.services.v3 import owner_music_state_service as owner_state
    from backend.drafts.s7_feedback_consent.contracts import EvidenceEpochConflict
    def conflict(db, *, internal_user_pk, expected_epoch):
        assert (internal_user_pk, expected_epoch) == (7, 0)
        raise owner_state.FeedbackEpochConflict
    monkeypatch.setattr(owner_state, "compare_and_advance_feedback_epoch", conflict)
    with pytest.raises(EvidenceEpochConflict):
        save(ready)
    with ready.connect() as conn:
        assert conn.exec_driver_sql("SELECT count(*) FROM feedback_v3 WHERE idempotency_key='new-key'").scalar() == 0
        assert conn.exec_driver_sql("SELECT count(*) FROM owner_music_state").scalar() == 0
