import json

import pytest

from backend.ai_engine.assessment_v2 import run_assessment_v2


class RecordingJsonLLM:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def complete_json(self, system_prompt, user_prompt):
        self.calls.append((system_prompt, user_prompt))
        return self.response


def questionnaire_answers(q12=None):
    return {
        "q01_mood_weather": "cloudy",
        "q02_tension_worry": 3,
        "q03_overthinking": 2,
        "q04_irritability_anger": 1,
        "q05_low_mood": 4,
        "q06_interest_loss": 0,
        "q07_fear_unease": 2,
        "q08_sleep_disturbance": 3,
        "q09_low_energy": 1,
        "q10_appetite_change": 2,
        "q11_daily_impact": 4,
        "q12_physical_safety": ["none"] if q12 is None else q12,
    }


def valid_model_response():
    return {
        "state_summary": {"summary": "近期压力感较明显。"},
        "context": {
            "triggers": ["工作节奏"],
            "physical_signals": [],
        },
        "evidence": [
            {
                "claim": "紧张担忧较频繁",
                "sources": ["questionnaire:q02"],
                "summary": "问卷显示过去七天紧张担忧频率较高。",
            }
        ],
        "conflicts": [],
    }


@pytest.mark.parametrize(
    (
        "document",
        "narrative_text",
        "expected_mode",
        "expected_sources",
        "expected_missing",
        "expected_prompt_text",
    ),
    [
        (
            None,
            None,
            "questionnaire_only",
            [
                {"source": "questionnaire", "status": "used"},
                {"source": "document", "status": "missing"},
                {"source": "narrative", "status": "missing"},
            ],
            ["document", "narrative"],
            [],
        ),
        (
            None,
            "最近工作节奏较快。",
            "narrative_questionnaire",
            [
                {"source": "questionnaire", "status": "used"},
                {"source": "document", "status": "missing"},
                {"source": "narrative", "status": "used"},
            ],
            ["document"],
            ["最近工作节奏较快。"],
        ),
        (
            {
                "ocr_status": "confirmed",
                "confirmed_text": "已确认记录：近期睡眠不稳。",
            },
            None,
            "document_questionnaire",
            [
                {"source": "questionnaire", "status": "used"},
                {"source": "document", "status": "used"},
                {"source": "narrative", "status": "missing"},
            ],
            ["narrative"],
            ["已确认记录：近期睡眠不稳。"],
        ),
        (
            {
                "ocr_status": "confirmed",
                "confirmed_text": "已确认记录：近期睡眠不稳。",
            },
            "最近工作节奏较快。",
            "document_text_questionnaire",
            [
                {"source": "questionnaire", "status": "used"},
                {"source": "document", "status": "used"},
                {"source": "narrative", "status": "used"},
            ],
            [],
            ["已确认记录：近期睡眠不稳。", "最近工作节奏较快。"],
        ),
    ],
)
def test_four_source_combinations_have_exact_modes_and_machine_readable_sources(
    document,
    narrative_text,
    expected_mode,
    expected_sources,
    expected_missing,
    expected_prompt_text,
):
    llm = RecordingJsonLLM(valid_model_response())
    submission = {
        "session_id": "session-task4",
        "user_id": "user-task4",
        "questionnaire": questionnaire_answers(),
        "document": document,
        "narrative_text": narrative_text,
    }

    result = run_assessment_v2(submission, llm=llm)

    assert result["agent_id"] == "assessment_agent"
    assert result["status"] == "success"
    assert result["analysis_mode"] == expected_mode
    assert result["sources_used"] == expected_sources
    assert result["missing_information"] == expected_missing
    assert result["dimensions"] == {
        "tension_worry": 75,
        "overthinking": 50,
        "irritability_anger": 25,
        "low_mood": 100,
        "interest_loss": 0,
        "fear_unease": 50,
        "sleep_disturbance": 75,
        "low_energy": 25,
        "appetite_change": 50,
        "daily_impact": 100,
    }
    assert result["degradation"] == {
        "active": False,
        "reason_codes": [],
    }
    assert result["disclaimer"] == (
        "本结果仅用于状态评估与音乐调养参考，不构成医学诊断或治疗建议。"
    )
    assert len(llm.calls) == 1
    prompt = llm.calls[0][1]
    for text in expected_prompt_text:
        assert text in prompt


def test_model_dimensions_cannot_override_deterministic_questionnaire_scores():
    response = valid_model_response()
    response["dimensions"] = {
        "tension_worry": 999,
        "low_mood": -1,
    }
    llm = RecordingJsonLLM(response)

    result = run_assessment_v2(
        {"questionnaire": questionnaire_answers()},
        llm=llm,
    )

    assert result["status"] == "success"
    assert result["dimensions"] == {
        "tension_worry": 75,
        "overthinking": 50,
        "irritability_anger": 25,
        "low_mood": 100,
        "interest_loss": 0,
        "fear_unease": 50,
        "sleep_disturbance": 75,
        "low_energy": 25,
        "appetite_change": 50,
        "daily_impact": 100,
    }


@pytest.mark.parametrize("ocr_status", ["pending", "failed", "unconfirmed"])
def test_unconfirmed_document_text_never_reaches_llm_or_output(ocr_status):
    secret_text = "未确认OCR原文-PRIVATE-4821"
    llm = RecordingJsonLLM(valid_model_response())

    result = run_assessment_v2(
        {
            "questionnaire": questionnaire_answers(),
            "document": {
                "ocr_status": ocr_status,
                "confirmed_text": secret_text,
            },
        },
        llm=llm,
    )

    assert result["analysis_mode"] == "questionnaire_only"
    assert result["sources_used"] == [
        {"source": "questionnaire", "status": "used"},
        {"source": "document", "status": "unconfirmed"},
        {"source": "narrative", "status": "missing"},
    ]
    assert result["status"] == "degraded"
    assert result["degradation"] == {
        "active": True,
        "reason_codes": ["DOCUMENT_UNCONFIRMED"],
    }
    assert secret_text not in llm.calls[0][0]
    assert secret_text not in llm.calls[0][1]
    assert secret_text not in json.dumps(result, ensure_ascii=False)


def test_model_echo_of_unconfirmed_ocr_is_discarded_from_output():
    secret_text = "未确认OCR原文-PRIVATE-9917"
    response = valid_model_response()
    response["state_summary"] = {"summary": secret_text}
    llm = RecordingJsonLLM(response)

    result = run_assessment_v2(
        {
            "questionnaire": questionnaire_answers(),
            "document": {
                "ocr_status": "pending",
                "confirmed_text": secret_text,
            },
        },
        llm=llm,
    )

    assert result["status"] == "degraded"
    assert result["degradation"] == {
        "active": True,
        "reason_codes": [
            "DOCUMENT_UNCONFIRMED",
            "LLM_UNCONFIRMED_OCR_ECHO",
        ],
    }
    assert secret_text not in json.dumps(result, ensure_ascii=False)


def test_blank_document_and_narrative_are_missing_sources():
    llm = RecordingJsonLLM(valid_model_response())

    result = run_assessment_v2(
        {
            "questionnaire": questionnaire_answers(),
            "document": {
                "ocr_status": "confirmed",
                "confirmed_text": " \n\t ",
            },
            "narrative_text": " \t\n ",
        },
        llm=llm,
    )

    assert result["analysis_mode"] == "questionnaire_only"
    assert result["sources_used"] == [
        {"source": "questionnaire", "status": "used"},
        {"source": "document", "status": "missing"},
        {"source": "narrative", "status": "missing"},
    ]
    assert result["missing_information"] == ["document", "narrative"]
    assert result["status"] == "success"


@pytest.mark.parametrize(
    "submission",
    [
        {
            "questionnaire": questionnaire_answers(),
            "narrative_text": "我现在有明确的自杀计划。",
        },
        {
            "questionnaire": questionnaire_answers(
                ["severe_breathing_difficulty"]
            ),
        },
        {
            "questionnaire": questionnaire_answers(),
            "document": {
                "ocr_status": "confirmed",
                "confirmed_text": "记录显示患者持续胸痛两个小时。",
            },
        },
    ],
)
def test_safety_block_happens_before_llm_for_all_reliable_sources(submission):
    llm = RecordingJsonLLM(valid_model_response())

    result = run_assessment_v2(submission, llm=llm)

    assert result["status"] == "blocked_safety"
    assert result["safety"]["level"] == "high"
    assert result["safety"]["block_standard_prescription"] is True
    assert result["state_summary"] == {
        "summary": "检测到需要优先处理的安全风险，普通状态分析已终止。"
    }
    assert result["evidence"] == []
    assert llm.calls == []


def test_structured_conflicts_are_validated_and_passed_without_a_winner():
    response = valid_model_response()
    response["evidence"] = [
        {
            "claim": "睡眠描述存在差异",
            "sources": ["document", "narrative"],
            "summary": "两个可靠来源对睡眠状态的描述不一致。",
        }
    ]
    response["conflicts"] = [
        {
            "topic": "sleep",
            "sources": ["document", "narrative"],
            "summary": "病例记录与自由描述存在差异，需要用户确认。",
        }
    ]
    llm = RecordingJsonLLM(response)

    result = run_assessment_v2(
        {
            "questionnaire": questionnaire_answers(),
            "document": {
                "ocr_status": "confirmed",
                "confirmed_text": "记录：睡眠平稳。",
            },
            "narrative_text": "最近睡眠不稳。",
        },
        llm=llm,
    )

    assert result["status"] == "degraded"
    assert result["conflicts"] == [
        {
            "topic": "sleep",
            "sources": ["document", "narrative"],
            "summary": "病例记录与自由描述存在差异，需要用户确认。",
        }
    ]
    assert result["degradation"] == {
        "active": True,
        "reason_codes": ["SOURCE_CONFLICT"],
    }
    assert "winner" not in result["conflicts"][0]
    assert "diagnosis" not in result["conflicts"][0]


def test_repeated_questionnaire_fallback_is_byte_for_byte_deterministic(
    monkeypatch,
):
    monkeypatch.setattr(
        "backend.ai_engine.assessment_v2.qwen_provider_from_env",
        lambda: None,
    )
    submission = {"questionnaire": questionnaire_answers()}

    first = json.dumps(
        run_assessment_v2(submission),
        ensure_ascii=False,
        sort_keys=True,
    )
    second = json.dumps(
        run_assessment_v2(submission),
        ensure_ascii=False,
        sort_keys=True,
    )

    assert first == second
