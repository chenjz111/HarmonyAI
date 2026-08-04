"""Evidence-sufficiency confidence tests for Assessment V2."""

import pytest

from backend.ai_engine.assessment_v2 import run_assessment_v2
from backend.app.schemas.assessment_v2 import AssessmentV2Response
from tests.api.test_assessment_v2_schema import (
    canonical_request,
    questionnaire_envelope,
)


class TimeoutJsonLLM:
    def complete_json(self, _system_prompt, _user_prompt):
        raise TimeoutError("simulated timeout")


class FixedJsonLLM:
    def complete_json(self, _system_prompt, _user_prompt):
        return {
            "state_summary": {"summary": "多源信息已完成结构化整理。"},
            "context": {
                "triggers": ["考试压力"],
                "physical_signals": ["睡眠不稳"],
            },
            "evidence": [
                {
                    "claim": "紧张担忧较明显",
                    "sources": ["questionnaire:q02"],
                    "summary": "问卷频率评分较高。",
                }
            ],
            "conflicts": [],
        }


def test_all_confirmed_sources_and_valid_model_have_full_confidence():
    result = run_assessment_v2(canonical_request(), llm=FixedJsonLLM())

    assert result["status"] == "success"
    assert result["confidence"] == pytest.approx(1.0)
    assert AssessmentV2Response.model_validate(result).confidence == 1.0


def test_one_optional_source_and_valid_model_have_explainable_confidence():
    result = run_assessment_v2(
        {
            "session_id": "sess-confidence-one-source",
            "user_id": "user-confidence",
            "narrative_text": "最近考试压力较大。",
            "questionnaire_answers": questionnaire_envelope(),
        },
        llm=FixedJsonLLM(),
    )

    # questionnaire 0.50 + one confirmed optional source 0.10
    # + source consistency 0.15 + validated model contract 0.15
    assert result["confidence"] == pytest.approx(0.90)


def test_qwen_degradation_does_not_claim_model_or_optional_source_credit():
    result = run_assessment_v2(canonical_request(), llm=TimeoutJsonLLM())

    assert result["status"] == "degraded"
    assert result["analysis_mode"] == "questionnaire_only"
    assert result["confidence"] == pytest.approx(0.50)
