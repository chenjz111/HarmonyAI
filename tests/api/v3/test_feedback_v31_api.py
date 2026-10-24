"""Real registered App, synthetic authentication and isolated formal schema."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.api.v3.test_feedback_v31_transactions import ready, body, principal


@pytest.fixture
def client(ready, monkeypatch):
    from backend.app.main import app
    from backend.app.core.database import get_db
    from backend.app.services.v3.auth_service import get_current_v3_principal
    monkeypatch.setenv('HARMONY_LIBRARY_CURSOR_SECRET', 'synthetic-feedback-cursor-secret-0123456789')
    previous = dict(app.dependency_overrides)
    def get_test_db():
        with Session(ready, autoflush=False) as db:
            yield db
    app.dependency_overrides[get_db] = get_test_db
    app.dependency_overrides[get_current_v3_principal] = lambda: principal()
    try:
        with TestClient(app) as instance:
            yield instance
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def post(client, key='api-key', **changes):
    return client.post('/api/v3/feedback-records', json={**body(), **changes}, headers={'Idempotency-Key':key})


def test_registered_save_exact_replay_read_delete_tombstone(client):
    first = post(client)
    assert first.status_code == 201, first.text
    data = first.json()['data']
    assert set(first.json()) == {'ok','data','request_id','schema_version'}
    assert post(client).status_code == 200
    fid = data['feedback_id']
    detail = client.get('/api/v3/feedback-records/'+fid)
    assert detail.status_code == 200 and detail.json()['data']['playback_event_id'] == 'event-a'
    assert not {'internal_user_pk','session_row_id','playback_event_row_id','comment_ciphertext'}.intersection(detail.json()['data'])
    page = client.get('/api/v3/feedback-records').json()['data']
    assert page['total'] == 1 and page['items'][0]['feedback_id'] == fid
    deleted = client.request('DELETE','/api/v3/feedback-records/'+fid, json={'expected_evidence_epoch':1})
    assert deleted.status_code == 200 and deleted.json()['data']['current_feedback_epoch'] == 2
    assert client.get('/api/v3/feedback-records/'+fid).status_code == 404
    assert client.get('/api/v3/feedback-records').json()['data']['total'] == 0
    assert post(client).status_code == 410
    assert post(client).json()['error']['code'] == 'FEEDBACK_DELETED'


def test_clear_keeps_history_and_replays_original_receipt(client):
    assert post(client).status_code == 201
    path = '/api/v3/me/feedback-evidence/clear'
    request = {'expected_evidence_epoch':1}
    first = client.post(path, json=request, headers={'Idempotency-Key':'clear-api'})
    assert first.status_code == 200, first.text
    assert first.json()['data']['resulting_feedback_epoch'] == 2
    assert client.get('/api/v3/feedback-records').json()['data']['total'] == 1
    assert post(client,key='after-clear',expected_evidence_epoch=2).status_code == 201
    replay = client.post(path, json=request, headers={'Idempotency-Key':'clear-api'})
    assert replay.json()['data'] == first.json()['data']
    changed = client.post(path,json={'expected_evidence_epoch':3},headers={'Idempotency-Key':'clear-api'})
    assert changed.status_code == 409 and changed.json()['error']['code'] == 'IDEMPOTENCY_CONFLICT'


def test_owner_isolation_key_epoch_and_policy_errors(client):
    assert post(client).status_code == 201
    assert post(client,post_state={'change_label':'worse'}).json()['error']['code'] == 'IDEMPOTENCY_CONFLICT'
    assert post(client,key='stale').json()['error']['code'] == 'FEEDBACK_EPOCH_CONFLICT'
    policy = post(client,key='policy',expected_evidence_epoch=1,learning_consent=True,consent_policy_version='unapproved')
    assert policy.status_code == 503 and policy.json()['error']['code'] == 'CONSENT_POLICY_UNAVAILABLE'
    from backend.app.main import app
    from backend.app.services.v3.auth_service import get_current_v3_principal
    fid = post(client).json()['data']['feedback_id']
    app.dependency_overrides[get_current_v3_principal] = lambda: principal(1)
    assert client.get('/api/v3/feedback-records/'+fid).status_code == 404
    assert client.request('DELETE','/api/v3/feedback-records/'+fid,json={'expected_evidence_epoch':0}).status_code == 404


def test_feedback_cursor_binds_epoch_filter_and_owner(client):
    assert post(client).status_code == 201
    assert post(client,key='second',expected_evidence_epoch=1).status_code == 201
    first = client.get('/api/v3/feedback-records?limit=1').json()['data']
    assert first['next_cursor']
    next_page = client.get('/api/v3/feedback-records', params={'limit':1,'cursor':first['next_cursor']})
    assert next_page.status_code == 200 and next_page.json()['data']['items'][0]['feedback_id'] != first['items'][0]['feedback_id']
    assert post(client,key='third',expected_evidence_epoch=2).status_code == 201
    stale = client.get('/api/v3/feedback-records', params={'cursor':first['next_cursor']})
    assert stale.status_code == 409 and stale.json()['error']['code'] == 'FEEDBACK_CURSOR_STALE'


def test_invalid_dto_and_missing_key_do_not_write(client):
    assert post(client,learning_consent=1).status_code == 422
    assert post(client,comment='not supported').status_code == 422
    response = client.post('/api/v3/feedback-records', json=body())
    assert response.status_code == 400 and response.json()['error']['code'] == 'IDEMPOTENCY_KEY_REQUIRED'
    assert client.get('/api/v3/feedback-records').json()['data']['total'] == 0


def test_library_context_carries_owned_session_for_explicit_historical_feedback(client):
    response = client.get('/api/v3/music/assets/music_shared?context_id=ctx_a')
    assert response.status_code == 200
    contexts = response.json()['data']['source_contexts']
    assert {c['context_id'] for c in contexts} == {'ctx_a','ctx_b'}
    assert all(c['session_id'] == 'sess_legacy' for c in contexts)
