import pytest
from pydantic import ValidationError

from backend.app.schemas.assessment_v2 import QuestionnaireAnswer


@pytest.mark.parametrize("value", [
    {"direction": "decrease", "severity": 0},
    {"direction": "decrease", "severity": 2},
    {"direction": "increase", "severity": 4},
    {"direction": "none", "severity": 0},
])
def test_http_schema_accepts_frozen_q15_appetite_values(value):
    answer = QuestionnaireAnswer.model_validate({
        "question_id": "q15_appetite_change",
        "value": value,
        "type": "single_choice",
    })
    assert answer.value.direction == value["direction"]
    assert answer.value.severity == value["severity"]


@pytest.mark.parametrize("value", [
    {"severity": 2},
    {"direction": "decrease"},
    {"direction": "other", "severity": 2},
    {"direction": "none", "severity": 2},
    {"direction": "increase", "severity": 5},
])
def test_http_schema_rejects_invalid_q15_appetite_values(value):
    with pytest.raises(ValidationError):
        QuestionnaireAnswer.model_validate({
            "question_id": "q15_appetite_change",
            "value": value,
            "type": "single_choice",
        })
