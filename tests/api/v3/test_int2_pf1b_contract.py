"""Unregistered DTO/proof/transaction contract samples for PF Phase B."""
import importlib
from datetime import datetime,timezone,timedelta
import pytest
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.orm import Session
from tests.api.v3.test_int2_feedback_0013_candidate import database,snapshot,candidate
from backend.app.schemas.v3.common import AuthPrincipal


def contract():return importlib.import_module('backend.drafts.s7_feedback_consent.contracts')


def test_public_synthetic_json_fixture_matches_actual_dtos_and_envelope():
    import json
    from pathlib import Path
    from backend.app.routers.v3.transport import v3_success
    fixture=json.loads((Path(__file__).parents[2]/'fixtures/s7/feedback_v31_contract.json').read_text())
    c=contract()
    request=c.FeedbackV31.model_validate(fixture['request'])
    assert request.learning_consent is False
    saved=c.FeedbackSavedV31.model_validate(fixture['saved'])
    record=c.FeedbackReadV31.model_validate(fixture['record'])
    page=c.FeedbackPageV31(items=[record],total=1,next_cursor=None,current_feedback_epoch=1)
    c.EvidenceMutationRequest.model_validate(fixture['clear_request'])
    c.EvidenceMutationResult.model_validate(fixture['clear_result'])
    assert v3_success(saved).data.learning_applied is False
    assert page.items[0].playback_event_id==request.playback_event_id


def principal(owner=7):
    return AuthPrincipal(internal_user_pk=owner,public_user_id=f'synthetic-{owner}',auth_type='registered',guest_expires_at=None)


def body(**changes):
    value=dict(schema_version='feedback_v3.1',session_id='sess_legacy',
        music_ref=dict(music_id='music_shared',source_type='matched'),
        source_context_id='ctx_a',playback_event_id='event-a',expected_evidence_epoch=0,
        pre_state_snapshot=dict(snapshot_id='synthetic',source='player_session',captured_at='2026-10-19T00:00:00Z'),
        post_state=dict(change_label='no_change'))
    return {**value,**changes}


def play(database,*,event='event-a',owner=7,context='ctx_a'):
    with database.begin() as db:
        db.execute(text("INSERT INTO music_playback_events(internal_user_pk,event_id,music_asset_id,event_type,source_context_id,occurred_at) VALUES(:o,:e,'music_shared','play_started',:c,'2026-10-19 00:00:00')"),{'o':owner,'e':event,'c':context})


def test_full_dto_reuses_phase_a_and_fingerprint_is_dto_only():
    c=contract();dto=c.FeedbackV31.model_validate(body())
    assert dto.learning_consent is False
    assert c.request_fingerprint(dto)==c.request_fingerprint(c.FeedbackV31.model_validate(body(learning_consent=False)))
    assert c.request_fingerprint(dto)!=c.request_fingerprint(c.FeedbackV31.model_validate(body(playback_event_id='another')))
    with pytest.raises(TypeError):c.request_fingerprint(body())


@pytest.mark.parametrize('changes',[{'learning_consent':1},{'learning_consent':'true'},
    {'comment':'new reversible text'},{'playback_event_id':None},{'source_context_id':None},
    {'expected_evidence_epoch':True},{'expected_evidence_epoch':-1}])
def test_dto_rejects_unsafe_inputs(changes):
    with pytest.raises(ValidationError):contract().FeedbackV31.model_validate(body(**changes))


def test_policy_authority_window_revocation_and_false_without_policy():
    c=contract();now=datetime(2026,10,19,tzinfo=timezone.utc)
    false=c.FeedbackV31.model_validate(body())
    assert c.consent_decision(false,None,now).learning_consent is False
    true=c.FeedbackV31.model_validate(body(learning_consent=True,consent_policy_version='synthetic-v1'))
    with pytest.raises(ValueError):c.consent_decision(true,None,now)
    policy=c.PolicySnapshot(version='synthetic-v1',body_sha256='a'*64,approval_ref='synthetic-only',
        effective_at=now-timedelta(days=1),revoked_at=None)
    assert c.consent_decision(true,policy,now).policy_version=='synthetic-v1'
    from dataclasses import replace
    for invalid in (replace(policy,effective_at=now+timedelta(seconds=1)),replace(policy,revoked_at=now),replace(policy,body_sha256=''),replace(policy,approval_ref='')):
        with pytest.raises(ValueError):c.consent_decision(true,invalid,now)


@pytest.mark.parametrize('owner,context,event,allowed',[(7,'ctx_a','event-a',True),
    (7,'ctx_b','event-a',False),(1,'ctx_other','event-a',False),
    (7,'ctx_a','missing',False)])
def test_specific_event_not_substituted_by_some_other_play(database,owner,context,event,allowed):
    c=contract();play(database)
    before=snapshot(database)
    with Session(database,autoflush=False) as db:
        kwargs=dict(principal=principal(owner),music_id='music_shared',source_context_id=context,playback_event_id=event,session_id='sess_legacy')
        if allowed:
            proof=c.resolve_feedback_playback_proof(db,**kwargs)
            assert proof.playback_event_row_id>0 and proof.source_context_id=='ctx_a'
        else:
            with pytest.raises(c.PlaybackProofUnavailable):c.resolve_feedback_playback_proof(db,**kwargs)
    assert snapshot(database)==before


def test_event_without_context_cannot_be_retroactively_attributed(database):
    c=contract();play(database,context=None)
    with Session(database,autoflush=False) as db:
        with pytest.raises(c.PlaybackProofUnavailable):c.resolve_feedback_playback_proof(db,principal=principal(),music_id='music_shared',source_context_id='ctx_a',playback_event_id='event-a',session_id='sess_legacy')


def test_clear_cutoff_epoch_cas_rollback_and_historical_pointer(database):
    c=contract();candidate().install_sqlite(database)
    now=datetime(2026,10,19,tzinfo=timezone.utc)
    before=snapshot(database)
    with Session(database,autoflush=False) as db:
        db.connection().exec_driver_sql('BEGIN IMMEDIATE')
        assert c.clear_evidence(db,principal=principal(),expected_epoch=0,now_utc=now)==1
        db.rollback()
    assert snapshot(database)==before
    with Session(database,autoflush=False) as db:
        db.connection().exec_driver_sql('BEGIN IMMEDIATE')
        assert c.clear_evidence(db,principal=principal(),expected_epoch=0,now_utc=now)==1
        db.commit()
    with Session(database,autoflush=False) as db:
        db.connection().exec_driver_sql('BEGIN IMMEDIATE')
        with pytest.raises(c.EvidenceEpochConflict):c.clear_evidence(db,principal=principal(),expected_epoch=0,now_utc=now)
        db.rollback()
    with database.connect() as db:
        assert db.exec_driver_sql('SELECT feedback_evidence_epoch FROM owner_music_state').scalar()==1
        assert db.exec_driver_sql('SELECT current_version_id FROM user_music_preferences').scalar()=='old-version'
        assert db.exec_driver_sql('SELECT evidence_epoch FROM user_music_preference_versions').scalar() is None
    assert c.m1_preference_application_enabled() is False


def test_replay_tombstone_precedes_fingerprint_and_legacy_unknown():
    c=contract()
    with pytest.raises(c.FeedbackGone):c.replay_decision(deleted_at='tombstone',stored_fingerprint=None,incoming_fingerprint='sha256:new')
    with pytest.raises(c.LegacyFingerprintUnavailable):c.replay_decision(deleted_at=None,stored_fingerprint=None,incoming_fingerprint='sha256:new')
    with pytest.raises(c.FeedbackFingerprintConflict):c.replay_decision(deleted_at=None,stored_fingerprint='old',incoming_fingerprint='new')
    with pytest.raises(c.FeedbackContentUnverified):
        c.replay_decision(deleted_at=None,stored_fingerprint='same',incoming_fingerprint='same')


@pytest.mark.parametrize('field,value',[
    ('change_label','worse'),('pre_state_snapshot_json','{}'),('post_state_json','{}'),
    ('experience_json','{"overall_rating":1}'),('continue_use','no'),
    ('liked_features_json','["different"]'),('adjustment_preferences_json','["slower_tempo"]'),
    ('playback_json','{"played_seconds":1,"completed":false}'),('comment_ciphertext','new-hash'),
    ('source_task_id','ctx_b'),('evidence_epoch',1),('request_fingerprint','sha256:'+'f'*64)
])
def test_r1_save_and_replay_require_real_persisted_content_not_only_fingerprint(database,field,value):
    import json
    c=contract();candidate().install_sqlite(database);play(database)
    dto=c.FeedbackV31.model_validate(body())
    fingerprint=c.request_fingerprint(dto)
    with database.begin() as db:
        db.execute(text("""INSERT INTO feedback_v3(feedback_id,internal_user_pk,session_row_id,music_asset_id,
            change_label,pre_state_snapshot_json,post_state_json,liked_features_json,adjustment_preferences_json,
            idempotency_key,preference_update_status,request_fingerprint,source_task_id,playback_event_row_id,evidence_epoch)
            VALUES('r1-replay',7,1,'music_shared','no_change',:pre,:post,'[]','[]','r1-replay-key','skipped',:fp,'ctx_a',1,0)"""),
            {'pre':json.dumps(dto.pre_state_snapshot.model_dump(mode='json')),'post':json.dumps(dto.post_state.model_dump(mode='json')),'fp':fingerprint})
    with database.connect() as db:
        row=dict(db.exec_driver_sql("SELECT * FROM feedback_v3 WHERE feedback_id='r1-replay'").mappings().one())
    c.verify_persisted_feedback_content(row,dto)
    assert c.replay_decision(deleted_at=None,stored_fingerprint=fingerprint,incoming_fingerprint=fingerprint,
        persisted_content=row,request=dto)=='replay'
    corrupt={**row,field:value}
    with pytest.raises(c.FeedbackContentUnverified):c.verify_persisted_feedback_content(corrupt,dto)
    with pytest.raises(c.FeedbackContentUnverified):
        c.replay_decision(deleted_at=None,stored_fingerprint=fingerprint,incoming_fingerprint=fingerprint,
            persisted_content=corrupt,request=dto)


def test_r1_save_verification_failure_rolls_back_new_row(database):
    import json
    c=contract();candidate().install_sqlite(database);play(database)
    dto=c.FeedbackV31.model_validate(body())
    before=snapshot(database)
    with pytest.raises(c.FeedbackContentUnverified):
        with database.begin() as db:
            db.execute(text("""INSERT INTO feedback_v3(feedback_id,internal_user_pk,session_row_id,music_asset_id,
                change_label,pre_state_snapshot_json,post_state_json,liked_features_json,adjustment_preferences_json,
                idempotency_key,preference_update_status,request_fingerprint,source_task_id,playback_event_row_id,evidence_epoch)
                VALUES('bad-save',7,1,'music_shared','worse',:pre,:post,'[]','[]','bad-save-key','pending',:fp,'ctx_a',1,0)"""),
                {'pre':json.dumps(dto.pre_state_snapshot.model_dump(mode='json')),
                 'post':json.dumps(dto.post_state.model_dump(mode='json')),'fp':c.request_fingerprint(dto)})
            row=db.exec_driver_sql("SELECT * FROM feedback_v3 WHERE feedback_id='bad-save'").mappings().one()
            c.verify_persisted_feedback_content(row,dto)  # before transaction commit
    assert snapshot(database)==before


def test_two_connections_clear_expected_epoch_has_one_winner(database):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    c=contract();candidate().install_sqlite(database)
    barrier=Barrier(2)
    def clear(_):
        with Session(database,autoflush=False) as db:
            barrier.wait(timeout=10)
            db.connection().exec_driver_sql('BEGIN IMMEDIATE')
            try:
                epoch=c.clear_evidence(db,principal=principal(),expected_epoch=0,now_utc=datetime(2026,10,19,tzinfo=timezone.utc))
                db.commit()
                return epoch
            except c.EvidenceEpochConflict:
                db.rollback();return 'conflict'
    with ThreadPoolExecutor(2) as pool:answers=list(pool.map(clear,range(2)))
    assert answers.count(1)==1 and answers.count('conflict')==1
    with database.connect() as db:
        assert db.exec_driver_sql('SELECT count(*) FROM owner_music_state').scalar()==1
        assert db.exec_driver_sql('SELECT feedback_evidence_epoch FROM owner_music_state').scalar()==1


def test_clear_epoch_is_owner_scoped_and_old_computation_is_rejected(database):
    c=contract();candidate().install_sqlite(database)
    with Session(database,autoflush=False) as db:
        db.connection().exec_driver_sql('BEGIN IMMEDIATE')
        c.clear_evidence(db,principal=principal(),expected_epoch=0,now_utc=datetime(2026,10,19,tzinfo=timezone.utc));db.commit()
    with Session(database,autoflush=False) as db:
        db.connection().exec_driver_sql('BEGIN IMMEDIATE')
        assert c.lock_expected_epoch(db,principal=principal(1),expected_epoch=0).feedback_evidence_epoch==0
        with pytest.raises(c.EvidenceEpochConflict):c.lock_expected_epoch(db,principal=principal(),expected_epoch=0)
        db.rollback()


def test_specific_event_with_different_asset_never_proves_feedback(database):
    c=contract();play(database)
    with database.begin() as db:
        db.exec_driver_sql("INSERT INTO music_assets(music_asset_id,source_type,title,storage_key,format,duration_seconds,checksum,playable_status) VALUES('other-asset','matched','Synthetic','missing','wav',1,'sha256:other','ready')")
    with Session(database,autoflush=False) as db:
        with pytest.raises(c.PlaybackProofUnavailable):c.resolve_feedback_playback_proof(db,principal=principal(),music_id='other-asset',source_context_id='ctx_a',playback_event_id='event-a',session_id='sess_legacy')


def test_readonly_historical_profile_survives_clear_but_new_application_is_off(database):
    from backend.app.services.v3.feedback_service import get_preferences,get_latest_preference_snapshot
    c=contract();candidate().install_sqlite(database)
    with Session(database,autoflush=False) as db:
        before=get_preferences(db,principal()).model_dump(mode='json')
        db.rollback()
        db.connection().exec_driver_sql('BEGIN IMMEDIATE')
        c.clear_evidence(db,principal=principal(),expected_epoch=0,now_utc=datetime(2026,10,19,tzinfo=timezone.utc));db.commit()
    with Session(database,autoflush=False) as db:
        assert get_preferences(db,principal()).model_dump(mode='json')==before
        assert get_latest_preference_snapshot(db,principal()) is None


def test_public_response_contract_never_exposes_internal_proof_pk():
    c=contract()
    output=c.FeedbackSavedV31(feedback_id='synthetic-feedback',status='saved',
        current_feedback_epoch=1,replayed=False,learning_applied=False)
    assert output.model_dump(mode='json')==dict(feedback_id='synthetic-feedback',status='saved',current_feedback_epoch=1,replayed=False,learning_applied=False)
    assert c.FeedbackPageV31(items=[],total=0,next_cursor=None,current_feedback_epoch=0).total==0
    assert c.EvidenceMutationRequest(expected_evidence_epoch=0).expected_evidence_epoch==0
    with pytest.raises(ValidationError):c.FeedbackSavedV31(feedback_id='x',status='saved',current_feedback_epoch=1,replayed=False,learning_applied=True)


def test_clear_requires_cutoff_policy_and_owner_not_just_increasing_epoch():
    c=contract();now=datetime(2026,10,19,tzinfo=timezone.utc)
    policy=c.PolicySnapshot('synthetic-v1','a'*64,'synthetic-only',now-timedelta(days=2),None)
    record=c.EvidenceRecord(owner=7,created_at=now-timedelta(days=1),
        learning_consent=True,consent_policy_version='synthetic-v1',deleted_at=None,evidence_epoch=2)
    assert c.qualifies_for_future_evidence(record,principal=principal(),current_epoch=4,cutoff=None,policy=policy,now_utc=now)
    assert not c.qualifies_for_future_evidence(record,principal=principal(),current_epoch=5,cutoff=now,policy=policy,now_utc=now)
    from dataclasses import replace
    after=replace(record,created_at=now+timedelta(seconds=1),evidence_epoch=5)
    # A subsequent valid feedback advances global epoch; it does not revoke ALL
    # earlier post-clear rows. Derived version CAS, not row equality, is strict.
    assert c.qualifies_for_future_evidence(after,principal=principal(),current_epoch=6,cutoff=now,policy=policy,now_utc=now+timedelta(seconds=2))
    for invalid in (replace(after,owner=1),replace(after,deleted_at=now),replace(after,evidence_epoch=None),replace(after,learning_consent=False)):
        assert not c.qualifies_for_future_evidence(invalid,principal=principal(),current_epoch=6,cutoff=now,policy=policy,now_utc=now+timedelta(seconds=2))
    assert c.m1_preference_application_enabled() is False
