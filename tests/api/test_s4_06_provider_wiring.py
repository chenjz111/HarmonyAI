from fastapi.testclient import TestClient

from backend.ai_engine.providers import MockProvider
from backend.app.main import app
from backend.app.routers import workflow_v2_router
from tests.ai_engine.test_questionnaire_v21 import valid_v21_envelope


def test_assessment_endpoint_injects_async_qwen_provider(monkeypatch):
    provider = MockProvider({
        "items": [{
            "category": "duration",
            "label": "duration",
            "value": "1_to_2_weeks",
            "polarity": "present",
            "time_window": "past_14_days",
            "quote": "two weeks",
            "source_ref": "narrative:sentence_1",
            "extraction_confidence": 0.9,
            "negated": False,
        }]
    })
    monkeypatch.setattr(
        workflow_v2_router,
        "async_qwen_provider_from_env",
        lambda: provider,
    )

    response = TestClient(app).post(
        "/api/v2/assessments",
        json={
            "session_id": "session-s4-06-provider",
            "user_id": "user-s4-06-provider",
            "narrative_text": "two weeks",
            "questionnaire_answers": valid_v21_envelope(),
        },
    )

    assert response.status_code == 200
    assessment = response.json()["data"]
    assert assessment["input_processing_status"]["narrative"]["status"] == "processed"
    assert any(
        item["source_type"] == "narrative"
        for item in assessment["evidence_items"]
    )
    assert provider.calls == 1
