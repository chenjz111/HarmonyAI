import pytest
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import JSON

from backend.app.models.assessment_evidence import AssessmentEvidence
from backend.app.schemas.evidence_v21 import EvidenceItemV21


adapter = TypeAdapter(EvidenceItemV21)

COMMON = {
    "evidence_id": "ev_test",
    "label": "test_label",
    "display_name": "测试证据",
    "polarity": "present",
    "severity": "moderate",
    "severity_display": "中等",
    "time_window": "过去两周",
    "source_type": "questionnaire",
    "source_ref": "q03",
    "confirmed": False,
}


@pytest.mark.parametrize(
    "payload",
    [
        {"category": "emotion", "value": 3},
        {"category": "goal", "value": "relaxation"},
        {"category": "physical", "value": ["neck_tension", "palpitation"]},
        {
            "category": "appetite",
            "value": {"direction": "decrease", "severity": 3},
        },
    ],
)
def test_evidence_value_accepts_only_frozen_union_branches(payload):
    result = adapter.validate_python({**COMMON, **payload})
    assert result.category == payload["category"]


@pytest.mark.parametrize(
    "payload",
    [
        {"category": "emotion", "value": 5},
        {"category": "emotion", "value": "high"},
        {"category": "physical", "value": []},
        {"category": "physical", "value": ["neck_tension", "neck_tension"]},
        {"category": "appetite", "value": {"direction": "none", "severity": 2}},
        {"category": "goal", "value": {"free_form": "unbounded"}},
    ],
)
def test_evidence_value_rejects_out_of_contract_shapes(payload):
    with pytest.raises(ValidationError):
        adapter.validate_python({**COMMON, **payload})


def test_assessment_evidence_persists_json_value_and_frozen_fields():
    columns = AssessmentEvidence.__table__.columns
    assert isinstance(columns["value"].type, JSON)
    assert {
        "label",
        "display_name",
        "polarity",
        "severity",
        "severity_display",
        "time_window",
        "source_type",
        "source_ref",
        "quote",
        "extraction_confidence",
        "confirmed",
        "dimension_score",
    }.issubset(columns.keys())
