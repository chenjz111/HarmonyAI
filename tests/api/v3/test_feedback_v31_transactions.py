"""Production metadata, exact playback proofs and caller-owned transactions."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.schemas.v3.common import AuthPrincipal
from tests.api.v3.test_int2_0012_contract import seed

NOW = datetime(2026, 10, 24, tzinfo=timezone.utc)


def principal(owner=7):
    return AuthPrincipal(internal_user_pk=owner, public_user_id=f'synthetic-{owner}',
                         auth_type='registered', guest_expires_at=None)


def body(**changes):
    return dict(schema_version='feedback_v3.1', session_id='sess_legacy',
                music_ref=dict(music_id='music_shared', source_type='matched'),
                source_context_id='ctx_a', playback_event_id='event-a', expected_evidence_epoch=0,
                pre_state_snapshot=dict(snapshot_id='synthetic', source='player_session', captured_at='2026-10-24T00:00:00Z'),
                post_state=dict(change_label='no_change'), **changes)


@pytest.fixture
def ready(tmp_path, monkeypatch):
    from backend.app.core import database
    from backend.app import models  # noqa: F401
    engine = create_engine(f'sqlite:///{tmp_path / "transactions.sqlite"}', connect_args={'check_same_thread':False})
    monkeypatch.setattr(database, 'engine', engine)
    database.init_database()
    with engine.begin() as db:
        db.exec_driver_sql("INSERT INTO users(id,openid) VALUES(7,'synthetic-owner')")
        db.exec_driver_sql("INSERT INTO sessions(id,user_id,session_id,status) VALUES(1,7,'sess_legacy','active')")
        seed(db)
        db.exec_driver_sql("INSERT INTO music_playback_events(internal_user_pk,event_id,music_asset_id,event_type,source_context_id,occurred_at) VALUES(7,'event-a','music_shared','play_started','ctx_a','2026-10-24 00:00:00')")
    yield engine
    engine.dispose()


def save(engine, *, key='new-key', changes=None, owner=7):
    from backend.app.services.v3 import feedback_v31_service as service
    from backend.app.schemas.v3.feedback_v31 import FeedbackV31
    with Session(engine, autoflush=False) as db:
        db.connection().exec_driver_sql('BEGIN IMMEDIATE')
        result = service.save_unconsented_feedback(db, principal=principal(owner),
            request=FeedbackV31.model_validate({**body(), **(changes or {})}), idempotency_key=key, now_utc=NOW)
        db.commit()
        return result


def test_save_exact_replay_and_favorite_have_one_epoch_transition(ready):
    first = save(ready, changes={'favorite':False})
    second = save(ready, changes={'favorite':False})
    assert first.feedback_id == second.feedback_id
    assert (first.replayed, second.replayed) == (False, True)
    assert (first.current_feedback_epoch, second.current_feedback_epoch) == (1, 1)
    with ready.connect() as db:
        assert db.exec_driver_sql('SELECT library_epoch,feedback_evidence_epoch FROM owner_music_state').one() == (1, 1)
        assert db.exec_driver_sql('SELECT count(*) FROM favorites').scalar_one() == 0
        assert db.exec_driver_sql('SELECT count(*) FROM feedback_v3').scalar_one() == 1


def test_replay_after_other_save_returns_current_epoch_without_changing_favorite(ready):
    first = save(ready, changes={'favorite':False})
    save(ready, key='next', changes={'expected_evidence_epoch':1, 'favorite':True})
    replay = save(ready, changes={'favorite':False})
    assert replay.feedback_id == first.feedback_id and replay.current_feedback_epoch == 2
    with ready.connect() as db:
        assert db.exec_driver_sql('SELECT count(*) FROM favorites').scalar_one() == 1


@pytest.mark.parametrize('changes', [{'playback_event_id':'wrong'}, {'source_context_id':'ctx_b'},
                                   {'session_id':'synthetic-other'}])
def test_wrong_specific_event_context_or_session_rolls_back_state(ready, changes):
    from backend.app.services.v3.feedback_v31_contract import PlaybackProofUnavailable
    with pytest.raises(PlaybackProofUnavailable):
        save(ready, changes=changes)
    with ready.connect() as db:
        assert db.exec_driver_sql('SELECT count(*) FROM feedback_v3').scalar_one() == 0
        assert db.exec_driver_sql('SELECT count(*) FROM owner_music_state').scalar_one() == 0


def test_tombstone_hides_detail_list_total_and_precedes_changed_replay(ready):
    from backend.app.services.v3 import feedback_v31_service as service, feedback_v31_queries as queries
    from backend.app.services.v3.feedback_v31_contract import FeedbackGone
    saved = save(ready)
    for _ in range(2):
        with Session(ready, autoflush=False) as db:
            db.connection().exec_driver_sql('BEGIN IMMEDIATE')
            epoch = service.tombstone_owned_feedback(db, principal=principal(), feedback_id=saved.feedback_id,
                                                     expected_epoch=1, now_utc=NOW)
            db.commit()
        assert epoch == 2
    with Session(ready) as db:
        assert queries.read_owned_feedback_page(db, principal=principal()) == ([], 0)
        with pytest.raises(service.FeedbackNotFound):
            queries.get_owned_feedback(db, principal=principal(), feedback_id=saved.feedback_id)
    with pytest.raises(FeedbackGone):
        save(ready, changes={'post_state':{'change_label':'worse'}})


def test_cas_failure_rolls_back_feedback_favorite_and_state(ready, monkeypatch):
    from backend.app.services.v3 import feedback_v31_service as service
    def fail(*args, **kwargs):
        raise RuntimeError('synthetic final CAS failure')
    monkeypatch.setattr(service, '_compare_and_advance', fail)
    with pytest.raises(RuntimeError, match='synthetic final CAS failure'):
        save(ready, changes={'favorite':False})
    with ready.connect() as db:
        assert db.exec_driver_sql('SELECT count(*) FROM feedback_v3').scalar_one() == 0
        assert db.exec_driver_sql('SELECT count(*) FROM owner_music_state').scalar_one() == 0
        assert db.exec_driver_sql('SELECT count(*) FROM favorites').scalar_one() == 1


def test_commit_unknown_requires_independent_exact_database_witness(ready):
    from backend.app.services.v3 import feedback_v31_transactions as transactions
    from backend.app.schemas.v3.feedback_v31 import FeedbackV31
    class AckLost(Session):
        def commit(self):
            super().commit()
            raise OSError('synthetic lost commit acknowledgment')
    result = transactions.save_feedback(sessionmaker(bind=ready, class_=AckLost),
        verification_factory=sessionmaker(bind=ready), principal=principal(),
        request=FeedbackV31.model_validate(body()), idempotency_key='unknown', now_utc=NOW)
    assert result.replayed and result.current_feedback_epoch == 1
    with ready.connect() as db:
        assert db.exec_driver_sql('SELECT count(*) FROM feedback_v3').scalar_one() == 1


def test_commit_failure_without_witness_is_unknown_and_never_retries_mutation(ready):
    from backend.app.services.v3 import feedback_v31_transactions as transactions
    from backend.app.schemas.v3.feedback_v31 import FeedbackV31
    class CommitFailed(Session):
        def commit(self):
            raise OSError('synthetic failure before commit')
    with pytest.raises(transactions.FeedbackCommitUnknown):
        transactions.save_feedback(sessionmaker(bind=ready, class_=CommitFailed),
            verification_factory=sessionmaker(bind=ready), principal=principal(),
            request=FeedbackV31.model_validate(body()), idempotency_key='unknown', now_utc=NOW)
    with ready.connect() as db:
        assert db.exec_driver_sql('SELECT count(*) FROM feedback_v3').scalar_one() == 0
        assert db.exec_driver_sql('SELECT count(*) FROM owner_music_state').scalar_one() == 0


def test_unknown_commit_uses_witness_id_when_identical_competitor_committed(ready):
    from backend.app.services.v3 import feedback_v31_transactions as transactions
    from backend.app.schemas.v3.feedback_v31 import FeedbackV31
    witness = []
    class CommitFailed(Session):
        def commit(self):
            raise OSError('synthetic commit did not reach server')
    def verification_factory():
        witness.append(save(ready, key='same-key'))
        return Session(ready)
    result = transactions.save_feedback(sessionmaker(bind=ready, class_=CommitFailed),
        verification_factory=verification_factory, principal=principal(),
        request=FeedbackV31.model_validate(body()), idempotency_key='same-key', now_utc=NOW)
    assert result.feedback_id == witness[0].feedback_id


def test_legacy_history_and_replay_cannot_revive_tombstone_or_v31_key(ready):
    from backend.app.services.v3 import feedback_service as legacy, feedback_v31_service as service
    from backend.app.schemas.v3.feedback import FeedbackV3
    saved = save(ready)
    old = {k:v for k,v in body().items() if k not in {'source_context_id','playback_event_id','expected_evidence_epoch'}}
    old['schema_version'] = 'feedback_v3.0'
    with Session(ready) as db:
        with pytest.raises(legacy.FeedbackConflict):
            legacy.submit_feedback(db, principal(), FeedbackV3.model_validate(old), 'new-key')
    with Session(ready, autoflush=False) as db:
        db.connection().exec_driver_sql('BEGIN IMMEDIATE')
        service.tombstone_owned_feedback(db, principal=principal(), feedback_id=saved.feedback_id,
                                         expected_epoch=1, now_utc=NOW)
        db.commit()
    with Session(ready) as db:
        assert legacy.list_feedback_history(db, principal()).total == 0
        with pytest.raises(legacy.FeedbackConflict):
            legacy.submit_feedback(db, principal(), FeedbackV3.model_validate(old), 'new-key')


def test_legacy_new_save_advances_feedback_epoch_once_and_replay_does_not(ready):
    from backend.app.services.v3 import feedback_service as legacy
    from backend.app.schemas.v3.feedback import FeedbackV3
    old = {k:v for k,v in body().items() if k not in {'source_context_id','playback_event_id','expected_evidence_epoch'}}
    old['schema_version'] = 'feedback_v3.0'
    for replayed in (False, True):
        with Session(ready) as db:
            result, actual = legacy.submit_feedback(db, principal(), FeedbackV3.model_validate(old), 'legacy-new')
            assert actual is replayed and result.status == 'saved'
        with ready.connect() as db:
            assert db.exec_driver_sql('SELECT feedback_evidence_epoch FROM owner_music_state').scalar_one() == 1


@pytest.mark.parametrize('operation', ['replay', 'repeat-delete'])
def test_mysql_replay_and_delete_issue_current_locking_reads_after_owner_lock(ready, operation):
    from sqlalchemy import event
    from sqlalchemy.dialects import mysql
    from backend.app.services.v3 import feedback_v31_service as service
    saved = save(ready)
    if operation == 'repeat-delete':
        with Session(ready, autoflush=False) as db:
            db.connection().exec_driver_sql('BEGIN IMMEDIATE')
            service.tombstone_owned_feedback(db, principal=principal(), feedback_id=saved.feedback_id,
                                             expected_epoch=1, now_utc=NOW)
            db.commit()
    statements = []
    def observe(connection, clause, multiparams, params, options):
        if getattr(clause, 'is_select', False):
            statements.append(str(clause.compile(dialect=mysql.dialect())))
    event.listen(ready, 'before_execute', observe)
    try:
        if operation == 'replay':
            assert save(ready).replayed
        else:
            with Session(ready, autoflush=False) as db:
                db.connection().exec_driver_sql('BEGIN IMMEDIATE')
                assert service.tombstone_owned_feedback(db, principal=principal(), feedback_id=saved.feedback_id,
                    expected_epoch=1, now_utc=NOW) == 2
    finally:
        event.remove(ready, 'before_execute', observe)
    owner_reads = [i for i,sql in enumerate(statements) if 'FROM owner_music_state' in sql]
    assert owner_reads
    # After acquiring the shared owner lock, every owner/feedback reread must
    # bypass any earlier caller-established MySQL REPEATABLE READ snapshot.
    current = [sql for sql in statements[owner_reads[0]:]
               if 'FROM owner_music_state' in sql or 'FROM feedback_v3' in sql]
    assert current and all(sql.rstrip().endswith('FOR UPDATE') for sql in current)


def test_delete_unknown_commit_requires_independent_tombstone_witness(ready):
    from backend.app.services.v3.feedback_v31_transactions import delete_feedback
    saved = save(ready)
    class AckLost(Session):
        def commit(self):
            super().commit()
            raise OSError('synthetic lost delete ACK')
    result = delete_feedback(sessionmaker(bind=ready,class_=AckLost),
        verification_factory=sessionmaker(bind=ready),principal=principal(),
        feedback_id=saved.feedback_id,expected_epoch=1,now_utc=NOW)
    assert result.current_feedback_epoch == 2 and result.feedback_id == saved.feedback_id
