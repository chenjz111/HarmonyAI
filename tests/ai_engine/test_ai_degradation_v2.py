import json

import pytest

import backend.ai_engine.assessment_v2 as assessment_v2
from backend.ai_engine.assessment_v2 import (
    run_assessment_v2 as _run_assessment_v2,
)
from backend.ai_engine.providers import LLMProviderError


class ResultJsonLLM:
    def __init__(self, result):
        self.result = result

    def complete_json(self, system_prompt, user_prompt):
        del system_prompt, user_prompt
        return self.result


class ErrorJsonLLM:
    def __init__(self, error):
        self.error = error

    def complete_json(self, system_prompt, user_prompt):
        del system_prompt, user_prompt
        raise self.error


def _legacy_assertion_view(result):
    reason_codes = []
    primary_reason = result["degradation"]["reason_code"]
    if primary_reason is not None:
        reason_codes.append(primary_reason)
    for warning in result["warnings"]:
        warning_code = warning.split(":", 1)[0]
        if warning_code not in reason_codes:
            reason_codes.append(warning_code)
    view = dict(result)
    view.update(
        {
            "state_summary": {
                "summary": result["assessment_summary"],
            },
            "dimensions": result["emotion_profile"]["dimension_scores"],
            "context": {
                "triggers": result["life_events"]["triggers"],
                "physical_signals": result["physical_profile"][
                    "physical_signals"
                ],
            },
            "evidence": result["extracted_evidence"],
            "degradation": {
                "active": result["degradation"]["triggered"],
                "reason_codes": reason_codes,
            },
        }
    )
    return view


def run_assessment_v2(*args, **kwargs):
    return _legacy_assertion_view(
        _run_assessment_v2(*args, **kwargs)
    )


def questionnaire_answers():
    return {
        "q01_mood_weather": "rainy",
        "q02_tension_worry": 4,
        "q03_overthinking": 3,
        "q04_irritability_anger": 2,
        "q05_low_mood": 1,
        "q06_interest_loss": 0,
        "q07_fear_unease": 1,
        "q08_sleep_disturbance": 2,
        "q09_low_energy": 3,
        "q10_appetite_change": 4,
        "q11_daily_impact": 0,
        "q12_physical_safety": ["fatigue"],
    }


def assessment_submission(**overrides):
    submission = {
        "session_id": "session-task4",
        "user_id": "user-task4",
        "questionnaire": questionnaire_answers(),
    }
    submission.update(overrides)
    return submission


def assert_deterministic_questionnaire_fallback(result, reason_codes):
    assert result["status"] == "degraded"
    assert result["dimensions"] == {
        "tension_worry": 100,
        "overthinking": 75,
        "irritability_anger": 50,
        "low_mood": 25,
        "interest_loss": 0,
        "fear_unease": 25,
        "sleep_disturbance": 50,
        "low_energy": 75,
        "appetite_change": 100,
        "daily_impact": 0,
    }
    assert result["state_summary"] == {
        "summary": "已根据问卷完成确定性状态评估。"
    }
    assert result["context"] == {
        "triggers": [],
        "physical_signals": ["fatigue"],
    }
    assert result["evidence"] == [
        {
            "claim": "tension_worry维度问卷结果",
            "sources": ["questionnaire:q02"],
            "summary": "归一化得分为100。",
        },
        {
            "claim": "overthinking维度问卷结果",
            "sources": ["questionnaire:q03"],
            "summary": "归一化得分为75。",
        },
        {
            "claim": "irritability_anger维度问卷结果",
            "sources": ["questionnaire:q04"],
            "summary": "归一化得分为50。",
        },
        {
            "claim": "low_mood维度问卷结果",
            "sources": ["questionnaire:q05"],
            "summary": "归一化得分为25。",
        },
        {
            "claim": "interest_loss维度问卷结果",
            "sources": ["questionnaire:q06"],
            "summary": "归一化得分为0。",
        },
        {
            "claim": "fear_unease维度问卷结果",
            "sources": ["questionnaire:q07"],
            "summary": "归一化得分为25。",
        },
        {
            "claim": "sleep_disturbance维度问卷结果",
            "sources": ["questionnaire:q08"],
            "summary": "归一化得分为50。",
        },
        {
            "claim": "low_energy维度问卷结果",
            "sources": ["questionnaire:q09"],
            "summary": "归一化得分为75。",
        },
        {
            "claim": "appetite_change维度问卷结果",
            "sources": ["questionnaire:q10"],
            "summary": "归一化得分为100。",
        },
        {
            "claim": "daily_impact维度问卷结果",
            "sources": ["questionnaire:q11"],
            "summary": "归一化得分为0。",
        },
    ]
    assert result["conflicts"] == []
    assert result["degradation"] == {
        "active": True,
        "reason_codes": reason_codes,
    }
    assert result["missing_information"] == ["document", "narrative"]
    assert result["disclaimer"] == (
        "本结果仅用于状态评估与音乐调养参考，不构成医学诊断或治疗建议。"
    )


def test_qwen_not_configured_degrades_without_raising(monkeypatch):
    monkeypatch.setattr(
        "backend.ai_engine.assessment_v2.qwen_provider_from_env",
        lambda: None,
    )

    result = run_assessment_v2(
        assessment_submission(),
    )

    assert_deterministic_questionnaire_fallback(
        result,
        ["LLM_NOT_CONFIGURED"],
    )


@pytest.mark.parametrize(
    ("error", "expected_reason"),
    [
        (TimeoutError("provider timeout"), "LLM_TIMEOUT"),
        (LLMProviderError("provider failed"), "LLM_PROVIDER_ERROR"),
    ],
)
def test_provider_timeout_and_error_degrade_without_raising(
    error,
    expected_reason,
):
    result = run_assessment_v2(
        assessment_submission(),
        llm=ErrorJsonLLM(error),
    )

    assert_deterministic_questionnaire_fallback(
        result,
        [expected_reason],
    )


def test_unexpected_complete_json_error_degrades_without_raising():
    result = run_assessment_v2(
        assessment_submission(),
        llm=ErrorJsonLLM(RuntimeError("unexpected provider failure")),
    )

    assert_deterministic_questionnaire_fallback(
        result,
        ["LLM_UNEXPECTED_ERROR"],
    )


def test_unexpected_provider_resolution_error_degrades_without_raising(
    monkeypatch,
):
    def raise_unexpected_error():
        raise RuntimeError("unexpected provider resolution failure")

    monkeypatch.setattr(
        "backend.ai_engine.assessment_v2.qwen_provider_from_env",
        raise_unexpected_error,
    )

    result = run_assessment_v2(
        assessment_submission(),
    )

    assert_deterministic_questionnaire_fallback(
        result,
        ["LLM_UNEXPECTED_ERROR"],
    )


@pytest.mark.parametrize(
    ("error", "expected_reason"),
    [
        (TimeoutError("resolution timeout"), "LLM_TIMEOUT"),
        (LLMProviderError("resolution failed"), "LLM_PROVIDER_ERROR"),
        (
            json.JSONDecodeError("resolution json", "not-json", 0),
            "LLM_INVALID_JSON",
        ),
    ],
)
def test_known_provider_resolution_errors_keep_specific_reasons(
    monkeypatch,
    error,
    expected_reason,
):
    def raise_known_error():
        raise error

    monkeypatch.setattr(
        "backend.ai_engine.assessment_v2.qwen_provider_from_env",
        raise_known_error,
    )

    result = run_assessment_v2(
        assessment_submission(),
    )

    assert_deterministic_questionnaire_fallback(
        result,
        [expected_reason],
    )


def test_base_exceptions_are_not_converted_to_degradation():
    with pytest.raises(SystemExit):
        run_assessment_v2(
            assessment_submission(),
            llm=ErrorJsonLLM(SystemExit(7)),
        )


def test_non_object_model_result_is_treated_as_invalid_json():
    result = run_assessment_v2(
        assessment_submission(),
        llm=ResultJsonLLM("not-json-object"),
    )

    assert_deterministic_questionnaire_fallback(
        result,
        ["LLM_INVALID_JSON"],
    )


def test_json_decode_error_degrades_without_raising():
    result = run_assessment_v2(
        assessment_submission(),
        llm=ErrorJsonLLM(
            json.JSONDecodeError("invalid model json", "not-json", 0)
        ),
    )

    assert_deterministic_questionnaire_fallback(
        result,
        ["LLM_INVALID_JSON"],
    )


def test_missing_required_model_field_discards_the_whole_result():
    result = run_assessment_v2(
        assessment_submission(),
        llm=ResultJsonLLM(
            {
                "state_summary": {"summary": "不得局部保留"},
                "evidence": [],
            }
        ),
    )

    assert_deterministic_questionnaire_fallback(
        result,
        ["LLM_MISSING_FIELDS"],
    )


@pytest.mark.parametrize(
    "invalid_result",
    [
        {
            "state_summary": {},
            "context": {
                "triggers": [],
                "physical_signals": [],
            },
            "evidence": [],
        },
        {
            "state_summary": {"summary": " \n "},
            "context": {
                "triggers": [],
                "physical_signals": [],
            },
            "evidence": [],
        },
        {
            "state_summary": {
                "summary": "状态摘要",
                "confidence": 0.8,
            },
            "context": {
                "triggers": [],
                "physical_signals": [],
            },
            "evidence": [],
        },
        {
            "state_summary": "not-an-object",
            "context": {
                "triggers": [],
                "physical_signals": [],
            },
            "evidence": [],
        },
        {
            "state_summary": {"summary": "状态摘要"},
            "context": [],
            "evidence": [],
        },
        {
            "state_summary": {"summary": "状态摘要"},
            "context": {},
            "evidence": [],
        },
        {
            "state_summary": {"summary": "状态摘要"},
            "context": {
                "triggers": None,
                "physical_signals": [],
            },
            "evidence": [],
        },
        {
            "state_summary": {"summary": "状态摘要"},
            "context": {
                "triggers": "工作压力",
                "physical_signals": [],
            },
            "evidence": [],
        },
        {
            "state_summary": {"summary": "状态摘要"},
            "context": {
                "triggers": [],
                "physical_signals": "fatigue",
            },
            "evidence": [],
        },
        {
            "state_summary": {"summary": "状态摘要"},
            "context": {
                "triggers": ["工作压力", "工作压力"],
                "physical_signals": [],
            },
            "evidence": [],
        },
        {
            "state_summary": {"summary": "状态摘要"},
            "context": {
                "triggers": [" "],
                "physical_signals": [],
            },
            "evidence": [],
        },
        {
            "state_summary": {"summary": "状态摘要"},
            "context": {
                "triggers": [],
                "physical_signals": [],
                "sources_used": ["questionnaire"],
            },
            "evidence": [],
        },
        {
            "state_summary": {"summary": "状态摘要"},
            "context": {
                "triggers": [],
                "physical_signals": [],
            },
            "evidence": [
                {
                    "claim": "wrong type",
                    "sources": "questionnaire:q02",
                    "summary": "不得接受",
                }
            ],
        },
        {
            "state_summary": {"summary": "状态摘要"},
            "context": {
                "triggers": [],
                "physical_signals": [],
            },
            "evidence": [
                {
                    "claim": "extra evidence field",
                    "sources": ["questionnaire:q02"],
                    "summary": "不得接受",
                    "confidence": 0.9,
                }
            ],
        },
    ],
)
def test_illegal_model_field_types_discard_the_whole_result(invalid_result):
    result = run_assessment_v2(
        assessment_submission(),
        llm=ResultJsonLLM(invalid_result),
    )

    assert_deterministic_questionnaire_fallback(
        result,
        ["LLM_SCHEMA_INVALID"],
    )


@pytest.mark.parametrize(
    "unknown_source",
    [
        "questionnaire:q01",
        "questionnaire:q12",
        "questionnaire:q13",
        "web",
        "document",
        "narrative",
    ],
)
def test_unknown_or_unavailable_evidence_source_discards_whole_model_result(
    unknown_source,
):
    result = run_assessment_v2(
        assessment_submission(),
        llm=ResultJsonLLM(
            {
                "state_summary": {"summary": "不得局部保留"},
                "context": {
                    "triggers": [],
                    "physical_signals": [],
                },
                "evidence": [
                    {
                        "claim": "非法来源",
                        "sources": [unknown_source],
                        "summary": "不得接受未知或未使用来源。",
                    }
                ],
            }
        ),
    )

    assert_deterministic_questionnaire_fallback(
        result,
        ["LLM_UNKNOWN_SOURCE"],
    )


@pytest.mark.parametrize("medical_field", ["syndrome", "diagnosis"])
def test_medical_conclusion_fields_discard_whole_model_result(medical_field):
    result = run_assessment_v2(
        assessment_submission(),
        llm=ResultJsonLLM(
            {
                "state_summary": {"summary": "不得局部保留"},
                "context": {
                    "triggers": [],
                    "physical_signals": [],
                    medical_field: "医学结论",
                },
                "evidence": [],
            }
        ),
    )

    assert_deterministic_questionnaire_fallback(
        result,
        ["LLM_PROHIBITED_MEDICAL_FIELD"],
    )


def test_unknown_conflict_source_discards_whole_model_result():
    result = run_assessment_v2(
        assessment_submission(),
        llm=ResultJsonLLM(
            {
                "state_summary": {"summary": "不得局部保留"},
                "context": {
                    "triggers": [],
                    "physical_signals": [],
                },
                "evidence": [],
                "conflicts": [
                    {
                        "topic": "sleep",
                        "sources": ["questionnaire:q08", "document"],
                        "summary": "未使用的 document 不得成为冲突来源。",
                    }
                ],
            }
        ),
    )

    assert_deterministic_questionnaire_fallback(
        result,
        ["LLM_UNKNOWN_SOURCE"],
    )
