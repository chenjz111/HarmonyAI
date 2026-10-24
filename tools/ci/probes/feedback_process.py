"""Explicitly selected pytest worker; launched only by run_feedback_processes.py."""
import json
import os
from pathlib import Path
import time


def test_feedback_process_role(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.app.core import database
    from backend.app.services.v3.feedback_v31_transactions import save_feedback
    from backend.app.services.v3.feedback_v31_contract import EvidenceEpochConflict
    from backend.app.schemas.v3.feedback_v31 import FeedbackV31
    from tests.api.v3.test_feedback_v31_transactions import body, principal, NOW
    from tests.api.v3.test_int2_0012_contract import seed
    from backend.app import models  # noqa: F401
    root = Path(os.environ['CI_DB_SANDBOX'])
    role = os.environ['HARMONY_FEEDBACK_ROLE']
    scenario = os.environ['HARMONY_FEEDBACK_SCENARIO']
    assert role in {'setup', 'a', 'b'} and scenario in {'same', 'different','clear-same','clear-different','clear-save'}
    engine = create_engine('sqlite:///' + str(root/'shared.sqlite'), connect_args={'timeout':20})
    try:
        if role == 'setup':
            monkeypatch.setattr(database, 'engine', engine)
            database.init_database()
            with engine.begin() as db:
                db.exec_driver_sql("INSERT INTO users(id,openid) VALUES(7,'synthetic-owner')")
                db.exec_driver_sql("INSERT INTO sessions(id,user_id,session_id,status) VALUES(1,7,'sess_legacy','active')")
                seed(db)
                db.exec_driver_sql("INSERT INTO music_playback_events(internal_user_pk,event_id,music_asset_id,event_type,source_context_id,occurred_at) VALUES(7,'event-a','music_shared','play_started','ctx_a','2026-10-24 00:00:00')")
            return
        (root/f'{role}.ready').write_text('ready', encoding='utf-8')
        deadline = time.monotonic()+15
        while not all((root/f'{name}.ready').exists() for name in ('a','b')):
            assert time.monotonic() < deadline, 'second guarded process never reached barrier'
            time.sleep(0.01)
        factory = sessionmaker(bind=engine, autoflush=False)
        try:
            if scenario.startswith('clear-') and not (scenario == 'clear-save' and role == 'b'):
                from backend.app.services.v3.feedback_clear_service import clear_with_commit
                from backend.app.schemas.v3.feedback_v31 import EvidenceMutationRequest
                result = clear_with_commit(factory,verification_factory=factory,principal=principal(),
                    request=EvidenceMutationRequest(expected_evidence_epoch=0),
                    idempotency_key='clear-shared' if scenario == 'clear-same' else f'clear-{role}',now_utc=NOW)
                row = dict(status='cleared',operation_id=result.operation_id,cutoff=result.cutoff.isoformat(),epoch=result.resulting_feedback_epoch)
            else:
                result = save_feedback(factory, verification_factory=factory, principal=principal(),
                    request=FeedbackV31.model_validate(body()),
                    idempotency_key='shared-key' if scenario == 'same' else f'key-{role}', now_utc=NOW)
                row = dict(status='saved', feedback_id=result.feedback_id, replayed=result.replayed,
                           epoch=result.current_feedback_epoch)
        except EvidenceEpochConflict:
            assert scenario in {'different','clear-different','clear-save'}
            row = dict(status='conflict')
        (root/f'{role}.result.json').write_text(json.dumps(row), encoding='utf-8')
    finally:
        engine.dispose()
