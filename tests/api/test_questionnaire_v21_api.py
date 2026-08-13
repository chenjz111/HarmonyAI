from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def _payload(answer_count):
    return {
        "session_id": "sess_questionnaire_v21",
        "user_id": "user_questionnaire_v21",
        "questionnaire_answers": {
            "schema_version": "questionnaire_v2.1",
            "time_window_days": 14,
            "answers": [
                {
                    "question_id": f"q{index:02d}",
                    "value": 0,
                    "type": "frequency_0_4",
                }
                for index in range(1, answer_count + 1)
            ],
        },
    }


def _answer(question_id, value, type_=None, score=None):
    record = {"question_id": question_id, "value": value}
    if type_ is not None:
        record["type"] = type_
    if score is not None:
        record["score"] = score
    return record


def _frozen_payload():
    """A complete, business-valid 20-question v2.1 submission matching the frozen contract.

    q15_appetite_change carries the frozen ``{direction, severity}`` dict (not a flat
    string), which is the value shape the endpoint must accept at the HTTP boundary.
    """
    return {
        "session_id": "sess_frozen_v21",
        "user_id": "user_frozen_v21",
        "questionnaire_answers": {
            "schema_version": "questionnaire_v2.1",
            "time_window_days": 14,
            "answers": [
                _answer("q01_user_goal", "relaxation", "single_choice"),
                _answer("q02_mood_weather", "clear", "visual_single", score=0),
                _answer("q03_tension_worry", 1, "frequency_0_4"),
                _answer("q04_worry_control", 4, "frequency_0_4"),
                _answer("q05_overthinking", "calm", "visual_single", score=0),
                _answer("q06_irritability_anger", 0, "frequency_0_4"),
                _answer("q07_fear_unease", 0, "frequency_0_4"),
                _answer("q08_low_mood", 0, "frequency_0_4"),
                _answer("q09_interest_loss", 0, "frequency_0_4"),
                _answer("q10_calm_wellbeing", 4, "frequency_0_4"),
                _answer("q11_emotional_recovery", 1, "single_choice"),
                _answer("q12_sleep_disturbance", 2, "frequency_0_4"),
                _answer("q13_unrefreshing_sleep", 1, "frequency_0_4"),
                _answer("q14_low_energy", "half", "visual_single", score=2),
                _answer("q15_appetite_change", {"direction": "none", "severity": 0}, "single_choice"),
                _answer("q16_physical_signals", ["neck_tension"], "multi_choice"),
                _answer("q17_duration", "1_to_2_weeks", "duration_choice"),
                _answer("q18_daily_impact", 1, "frequency_0_4"),
                _answer("q19_self_harm", "never", "single_choice"),
                _answer("q20_emergency", ["none"], "multi_choice"),
            ],
        },
    }


def test_questionnaire_v21_payload_reaches_business_validation_not_http_422():
    response = client.post("/api/v2/assessments", json=_payload(20))
    assert response.status_code == 200
    assert "success" in response.json()


def test_questionnaire_v21_requires_twenty_answers_at_api_boundary():
    response = client.post("/api/v2/assessments", json=_payload(19))
    assert response.status_code == 422


def test_questionnaire_v21_accepts_appetite_direction_dict_at_api_boundary():
    response = client.post("/api/v2/assessments", json=_frozen_payload())
    assert response.status_code == 200
    body = response.json()
    # The q15 {direction, severity} dict must clear the HTTP boundary (no 422) AND
    # business validation (no ASSESSMENT_INVALID), yielding a full success.
    assert body["success"] is True
    assert body["error"] is None
