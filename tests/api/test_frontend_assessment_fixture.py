import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import app
from tests.ai_engine.test_questionnaire_v21 import valid_v21_envelope


FIXTURE_PATH = (
    Path(__file__).parents[2]
    / "frontend"
    / "tests"
    / "fixtures"
    / "assessment-v2.1-response.json"
)


def _assert_same_schema(actual, fixture, path="assessment"):
    assert type(fixture) is type(actual), path
    if isinstance(actual, dict):
        assert set(fixture) == set(actual), path
        for key, value in actual.items():
            _assert_same_schema(value, fixture[key], f"{path}.{key}")
    elif isinstance(actual, list):
        if not actual:
            assert fixture == [], path
        else:
            assert fixture, path
            for index, value in enumerate(fixture):
                _assert_same_schema(actual[0], value, f"{path}[{index}]")


def test_frontend_assessment_fixture_matches_real_api_response_schema():
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    response = TestClient(app).post(
        "/api/v2/assessments",
        json={
            "session_id": "session-frontend-fixture",
            "user_id": "user-frontend-fixture",
            "questionnaire_answers": valid_v21_envelope(),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    actual = body["data"]
    _assert_same_schema(actual, fixture)
    assert fixture["status"] == actual["status"]
    assert fixture["input_processing_status"] == actual["input_processing_status"]
