"""PF-1A: production gateways are disabled; persisted history stays readable."""
import json
from datetime import datetime, timezone

import pytest

from backend.app.models.v3.feedback import UserMusicPreference, UserMusicPreferenceVersion, UserPreferenceItem, PreferenceEvent
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.services.v3 import feedback_service, diagnosis_service, prescription_service
from tests.api.v3.test_feedback import (
    _setup_guest, _seed_user_asset, _feedback_body, _post_feedback,
    _seed_db, _public_user_id, _row_ids, _v3_data, client,
)


def _principal(headers, session_id):
    public = _public_user_id(headers['Authorization'].split()[1])
    with _seed_db() as db:
        pk, _ = _row_ids(db, public, session_id)
    return AuthPrincipal(internal_user_pk=pk, public_user_id=public, auth_type='guest', guest_expires_at=datetime(2030,1,1,tzinfo=timezone.utc))


def _seed_history(principal):
    with _seed_db() as db:
        db.add(UserMusicPreference(profile_id='legacy', internal_user_pk=principal.internal_user_pk,
                                   current_version_id='legacy-v2'))
        db.flush()
        db.add(UserMusicPreferenceVersion(preference_version_id='legacy-v2', profile_id='legacy',
            version=2, feedback_count=4, minimum_samples_for_application=3,
            preferred_bpm_min=60, preferred_bpm_max=60, bpm_weight=1.0))
        db.flush()
        db.add_all([UserPreferenceItem(preference_version_id='legacy-v2', category='feature',
            code=code, polarity='preferred', weight=1.0, sample_count=4) for code in ['relaxing','focus']])
        db.add(UserPreferenceItem(preference_version_id='legacy-v2', category='instrument',
            code='guqin', polarity='preferred', weight=1.0, sample_count=4))
        db.commit()


def test_m1_feedback_never_calls_automatic_learner(monkeypatch):
    headers, session_id = _setup_guest()
    music_id = _seed_user_asset(headers, session_id)
    def forbidden(*args, **kwargs):
        pytest.fail('M1 submit invoked the legacy learner')
    monkeypatch.setattr(feedback_service, '_learn_preferences', forbidden)
    for index in range(5):
        result = _post_feedback(headers, _feedback_body(session_id, music_id), f'm1-{index}')
        assert result.status_code == 201
        assert _v3_data(result)['preference_update']['applied'] is False
    with _seed_db() as db:
        assert db.query(UserMusicPreferenceVersion).count() == 0
        assert db.query(PreferenceEvent).count() == 0


def test_m1_blocks_both_new_consumers_but_preserves_legacy_profile():
    headers, session_id = _setup_guest()
    principal = _principal(headers, session_id)
    _seed_history(principal)
    before = _v3_data(client.get('/api/v3/me/preferences', headers=headers))
    with _seed_db() as db:
        assert feedback_service.get_latest_preference_snapshot(db, principal) is None
        assert diagnosis_service.get_latest_preference_snapshot(db, principal) is None
        assert prescription_service._resolve_preference(db, principal, None) is None
    after = _v3_data(client.get('/api/v3/me/preferences', headers=headers))
    assert before == after
    assert after['version'] == 2
    assert after['public_user_id'] == principal.public_user_id
    assert {i['code'] for i in after['preferred_instruments']} == {'guqin'}
    assert after['learning']['feedback_count'] == 4
    assert {i['code'] for i in after['preferred_features']} == {'relaxing','focus'}
    assert after['preferred_bpm_range'] == {'min':60,'max':60,'weight':1.0}


def test_m1_direct_learner_is_fail_closed():
    class NoDatabaseAccess:
        def __getattr__(self, name):
            pytest.fail('disabled learner accessed persistence')
    principal = AuthPrincipal(internal_user_pk=1, public_user_id='test-owner', auth_type='guest', guest_expires_at=datetime(2030,1,1,tzinfo=timezone.utc))
    result = feedback_service._learn_preferences(NoDatabaseAccess(), principal, 'fb', 100)
    assert result.applied is False
    assert result.new_version is None


def test_m1_replay_does_not_revive_legacy_applied_claim():
    from backend.app.models.v3.feedback import FeedbackV3
    headers, session_id = _setup_guest()
    music_id = _seed_user_asset(headers, session_id)
    body = _feedback_body(session_id, music_id)
    first = _post_feedback(headers, body, 'legacy-replay')
    principal = _principal(headers, session_id)
    _seed_history(principal)
    with _seed_db() as db:
        fb = db.query(FeedbackV3).one()
        fb.preference_update_status = 'applied'
        db.commit()
    replay = _post_feedback(headers, body, 'legacy-replay')
    assert replay.status_code == 200
    assert _v3_data(replay)['feedback_id'] == _v3_data(first)['feedback_id']
    assert _v3_data(replay)['preference_update']['applied'] is False
    with _seed_db() as db:
        assert db.query(FeedbackV3).one().preference_update_status == 'applied'
        assert db.query(UserMusicPreferenceVersion).count() == 1
