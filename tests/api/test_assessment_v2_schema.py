import pytest
from pydantic import ValidationError

import backend.ai_engine.assessment_v2 as assessment_v2
from backend.app.schemas.assessment_v2 import (
    AssessmentV2Request,
    AssessmentV2Response,
)


def complete_questionnaire():
    return {
        "q01_mood_weather": "cloudy",
        "q02_tension_worry": 4,
        "q03_overthinking": 3,
        "q04_irritability_anger": 2,
        "q05_low_mood": 1,
        "q06_interest_loss": 0,
        "q07_fear_unease": 1,
        "q08_sleep_disturbance": 2,
        "q09_low_energy": 3,
        "q10_appetite_change": 1,
        "q11_daily_impact": 2,
        "q12_physical_safety": ["fatigue"],
    }


def canonical_request(**overrides):
    payload = {
        "session_id": "sess-contract",
        "user_id": "user-contract",
        "document_id": "doc-contract",
        "document_text": "已由用户确认的病例文本。",
        "narrative_text": "最近考试压力较大，睡眠不稳。",
        "questionnaire_answers": complete_questionnaire(),
    }
    payload.update(overrides)
    return payload


def test_request_accepts_only_canonical_assessment_names():
    request = AssessmentV2Request.model_validate(canonical_request())

    assert request.document_id == "doc-contract"
    assert request.document_text == "已由用户确认的病例文本。"
    assert request.questionnaire_answers["q02_tension_worry"] == 4


@pytest.mark.parametrize(
    ("canonical_name", "legacy_name", "legacy_value"),
    [
        (
            "document_text",
            "document",
            {
                "ocr_status": "confirmed",
                "confirmed_text": "旧 V2 病例字段。",
            },
        ),
        ("questionnaire_answers", "questionnaire", complete_questionnaire()),
    ],
)
def test_request_rejects_legacy_v2_names(
    canonical_name,
    legacy_name,
    legacy_value,
):
    payload = canonical_request()
    payload.pop(canonical_name)
    payload[legacy_name] = legacy_value

    with pytest.raises(ValidationError):
        AssessmentV2Request.model_validate(payload)


def test_assessment_runtime_emits_canonical_response(monkeypatch):
    monkeypatch.setattr(
        assessment_v2,
        "qwen_provider_from_env",
        lambda: None,
    )

    result = assessment_v2.run_assessment_v2(canonical_request())
    validated = AssessmentV2Response.model_validate(result)

    assert validated.analysis_mode == "document_narrative_questionnaire"
    assert validated.emotion_profile.dimension_scores == {
        "tension_worry": 100,
        "overthinking": 75,
        "irritability_anger": 50,
        "low_mood": 25,
        "interest_loss": 0,
        "fear_unease": 25,
        "sleep_disturbance": 50,
        "low_energy": 75,
        "appetite_change": 25,
        "daily_impact": 50,
    }
    assert validated.physical_profile.physical_signals == ["fatigue"]
    assert validated.safety_flags == []
    assert "dimensions" not in result
    assert "context" not in result
    assert "evidence" not in result


@pytest.mark.parametrize(
    ("document_id", "document_text", "narrative_text", "expected_mode"),
    [
        (
            "doc-1",
            "已确认病例。",
            "最近压力较大。",
            "document_narrative_questionnaire",
        ),
        (
            "doc-1",
            "已确认病例。",
            None,
            "document_questionnaire",
        ),
        (
            None,
            None,
            "最近压力较大。",
            "narrative_questionnaire",
        ),
        (None, None, None, "questionnaire_only"),
    ],
)
def test_runtime_uses_all_canonical_analysis_modes(
    monkeypatch,
    document_id,
    document_text,
    narrative_text,
    expected_mode,
):
    monkeypatch.setattr(
        assessment_v2,
        "qwen_provider_from_env",
        lambda: None,
    )
    result = assessment_v2.run_assessment_v2(
        canonical_request(
            document_id=document_id,
            document_text=document_text,
            narrative_text=narrative_text,
        )
    )

    assert result["analysis_mode"] == expected_mode
    AssessmentV2Response.model_validate(result)


class TimeoutJsonLLM:
    def complete_json(self, system_prompt, user_prompt):
        del system_prompt, user_prompt
        raise TimeoutError("provider timeout")


def test_timeout_logs_do_not_include_sensitive_source_text(caplog):
    document_secret = "PRIVATE-DOCUMENT-742951"
    narrative_secret = "PRIVATE-NARRATIVE-638204"

    result = assessment_v2.run_assessment_v2(
        canonical_request(
            document_text=document_secret,
            narrative_text=narrative_secret,
        ),
        llm=TimeoutJsonLLM(),
    )

    assert result["degradation"]["reason_code"] == "LLM_TIMEOUT"
    assert result["warnings"] == [
        "LLM_TIMEOUT: AI 分析暂时不可用，已切换到确定性问卷评估。"
    ]
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert document_secret not in log_text
    assert narrative_secret not in log_text
