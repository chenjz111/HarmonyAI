import json

from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.ai_engine.providers import MockProvider
from backend.app.core.logging_config import sanitize_log
from backend.app.main import app
from backend.app.models.ai_call_log import AICallLog
from backend.app.routers import workflow_v2_router
from tests.ai_engine.test_questionnaire_v21 import valid_v21_envelope
from tests.api.conftest import _TestingSession, _engine


MARKER = "S4_PRIVACY_PROBE_20260811"


def test_privacy_probe_never_reaches_ordinary_or_database_logs(
    monkeypatch,
    caplog,
):
    provider = MockProvider({"items": []})
    monkeypatch.setattr(
        workflow_v2_router,
        "async_qwen_provider_from_env",
        lambda: provider,
    )

    response = TestClient(app).post(
        "/api/v2/assessments",
        json={
            "session_id": "session-s4-06-privacy",
            "user_id": "user-s4-06-privacy",
            "narrative_text": MARKER,
            "document_text": MARKER,
            "questionnaire_answers": valid_v21_envelope(),
        },
    )

    assert response.status_code == 200
    assert provider.calls == 2
    assert MARKER not in caplog.text
    assert MARKER not in sanitize_log({
        "narrative_text": MARKER,
        "document_text": MARKER,
        "provider_input": MARKER,
    })

    AICallLog.__table__.create(bind=_engine, checkfirst=True)
    with _TestingSession() as session:
        session.add(AICallLog(
            request_id="request-s4-06-privacy",
            session_id="session-s4-06-privacy",
            agent_id="assessment",
            provider="mock",
            status="failed",
            input_summary=MARKER,
            output_summary=MARKER,
            error=MARKER,
            error_code=MARKER,
        ))
        session.commit()

    with _TestingSession() as session:
        rows = session.scalars(select(AICallLog)).all()
        serialized = json.dumps([
            {
                "input_summary": row.input_summary,
                "output_summary": row.output_summary,
                "error": row.error,
            }
            for row in rows
        ])
    assert MARKER not in serialized
