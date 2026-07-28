import json

import pytest

import backend.ai_engine.assessment_v2 as assessment_v2
from backend.ai_engine.assessment_v2 import run_assessment_v2
from backend.ai_engine.questionnaire_v2 import QuestionnaireValidationError


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


def assessment_submission(**overrides):
    submission = {
        "session_id": "session-task4",
        "user_id": "user-task4",
        "questionnaire": questionnaire_answers(),
    }
    submission.update(overrides)
    return submission


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


def test_typed_dict_input_contract_has_required_and_optional_fields():
    assert assessment_v2.AssessmentV2Submission.__required_keys__ == frozenset(
        {"session_id", "user_id", "questionnaire"}
    )
    assert assessment_v2.AssessmentV2Submission.__optional_keys__ == frozenset(
        {"document", "narrative_text"}
    )
    assert assessment_v2.AssessmentDocumentInput.__required_keys__ == frozenset(
        {"ocr_status", "confirmed_text"}
    )


@pytest.mark.parametrize("invalid_submission", [None, [], "submission"])
def test_submission_must_be_a_mapping(invalid_submission):
    with pytest.raises(assessment_v2.AssessmentValidationError) as error:
        run_assessment_v2(invalid_submission)

    assert str(error.value) == "submission must be a mapping"


@pytest.mark.parametrize(
    ("field", "invalid_value", "expected_message"),
    [
        (
            "session_id",
            "",
            "session_id must be a non-empty string",
        ),
        (
            "session_id",
            " \n ",
            "session_id must be a non-empty string",
        ),
        (
            "session_id",
            7,
            "session_id must be a non-empty string",
        ),
        (
            "user_id",
            "",
            "user_id must be a non-empty string",
        ),
        (
            "user_id",
            None,
            "user_id must be a non-empty string",
        ),
    ],
)
def test_session_and_user_ids_must_be_non_empty_strings(
    field,
    invalid_value,
    expected_message,
):
    submission = assessment_submission()
    submission[field] = invalid_value

    with pytest.raises(assessment_v2.AssessmentValidationError) as error:
        run_assessment_v2(submission)

    assert str(error.value) == expected_message


@pytest.mark.parametrize("missing_field", ["session_id", "user_id"])
def test_session_and_user_ids_are_required(missing_field):
    submission = assessment_submission()
    del submission[missing_field]

    with pytest.raises(assessment_v2.AssessmentValidationError) as error:
        run_assessment_v2(submission)

    assert str(error.value) == (
        f"{missing_field} must be a non-empty string"
    )


@pytest.mark.parametrize(
    ("document", "expected_message"),
    [
        ("document text", "document must be a mapping or None"),
        ([], "document must be a mapping or None"),
        (
            {"confirmed_text": "文本"},
            "document.ocr_status is invalid",
        ),
        (
            {
                "ocr_status": "queued",
                "confirmed_text": "文本",
            },
            "document.ocr_status is invalid",
        ),
        (
            {"ocr_status": "pending"},
            "document.confirmed_text must be a string or None",
        ),
        (
            {
                "ocr_status": "confirmed",
                "confirmed_text": 123456,
            },
            "document.confirmed_text must be a string or None",
        ),
    ],
)
def test_document_runtime_contract_is_validated(document, expected_message):
    with pytest.raises(assessment_v2.AssessmentValidationError) as error:
        run_assessment_v2(assessment_submission(document=document))

    assert str(error.value) == expected_message


@pytest.mark.parametrize("narrative_text", [42, [], {"text": "描述"}])
def test_narrative_must_be_text_or_none(narrative_text):
    with pytest.raises(assessment_v2.AssessmentValidationError) as error:
        run_assessment_v2(
            assessment_submission(narrative_text=narrative_text)
        )

    assert str(error.value) == "narrative_text must be a string or None"


@pytest.mark.parametrize(
    ("questionnaire", "extra_input", "expected_flag"),
    [
        (
            {
                **questionnaire_answers(["self_harm_thoughts"]),
                "q11_daily_impact": None,
            },
            {},
            "self_harm_thoughts",
        ),
        (
            {},
            {"narrative_text": "我现在有明确的自杀计划。"},
            "self_harm_thoughts",
        ),
        (
            {},
            {
                "document": {
                    "ocr_status": "confirmed",
                    "confirmed_text": "记录显示患者持续胸痛两个小时。",
                }
            },
            "severe_chest_pain",
        ),
    ],
)
def test_explicit_safety_risk_blocks_before_invalid_questionnaire_scoring(
    questionnaire,
    extra_input,
    expected_flag,
):
    questionnaire.pop("q11_daily_impact", None)
    llm = RecordingJsonLLM(valid_model_response())

    result = run_assessment_v2(
        assessment_submission(
            questionnaire=questionnaire,
            **extra_input,
        ),
        llm=llm,
    )

    assert result["status"] == "blocked_safety"
    assert result["dimensions"] == {}
    assert result["sources_used"][0] == {
        "source": "questionnaire",
        "status": "invalid",
    }
    assert result["safety"]["flags"] == [expected_flag]
    assert result["degradation"] == {
        "active": True,
        "reason_codes": ["QUESTIONNAIRE_INVALID"],
    }
    assert result["evidence"] == []
    assert llm.calls == []


def test_non_risk_invalid_questionnaire_raises_fixed_assessment_error():
    questionnaire = questionnaire_answers()
    del questionnaire["q11_daily_impact"]

    with pytest.raises(assessment_v2.AssessmentValidationError) as error:
        run_assessment_v2(
            assessment_submission(questionnaire=questionnaire),
            llm=RecordingJsonLLM(valid_model_response()),
        )

    assert str(error.value) == "invalid assessment questionnaire"
    assert isinstance(error.value.__cause__, QuestionnaireValidationError)


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
    assert result["session_id"] == "session-task4"
    assert result["user_id"] == "user-task4"
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
        assessment_submission(),
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
        assessment_submission(
            document={
                "ocr_status": ocr_status,
                "confirmed_text": secret_text,
            },
        ),
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
        assessment_submission(
            document={
                "ocr_status": "pending",
                "confirmed_text": secret_text,
            },
        ),
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


def test_complete_normalized_english_unconfirmed_ocr_echo_is_discarded():
    response = valid_model_response()
    response["state_summary"] = {"summary": "patient john doe"}

    result = run_assessment_v2(
        assessment_submission(
            document={
                "ocr_status": "pending",
                "confirmed_text": "  Patient   John Doe  ",
            },
        ),
        llm=RecordingJsonLLM(response),
    )

    assert result["degradation"] == {
        "active": True,
        "reason_codes": [
            "DOCUMENT_UNCONFIRMED",
            "LLM_UNCONFIRMED_OCR_ECHO",
        ],
    }
    assert "patient john doe" not in json.dumps(
        result,
        ensure_ascii=False,
    ).casefold()


def test_explicit_short_id_unconfirmed_ocr_echo_is_discarded():
    response = valid_model_response()
    response["state_summary"] = {"summary": "ID-42"}

    result = run_assessment_v2(
        assessment_submission(
            document={
                "ocr_status": "pending",
                "confirmed_text": "Confidential record ID-42",
            },
        ),
        llm=RecordingJsonLLM(response),
    )

    assert result["degradation"] == {
        "active": True,
        "reason_codes": [
            "DOCUMENT_UNCONFIRMED",
            "LLM_UNCONFIRMED_OCR_ECHO",
        ],
    }
    assert "ID-42" not in json.dumps(result, ensure_ascii=False)


@pytest.mark.parametrize(
    ("unconfirmed_text", "model_summary"),
    [
        (
            "PRIVATE full record ID-123456",
            "记录编号 ID-123456 需要核对。",
        ),
    ],
)
def test_model_echo_of_sensitive_unconfirmed_ocr_fragment_is_discarded(
    unconfirmed_text,
    model_summary,
):
    response = valid_model_response()
    response["state_summary"] = {"summary": model_summary}

    result = run_assessment_v2(
        assessment_submission(
            document={
                "ocr_status": "pending",
                "confirmed_text": unconfirmed_text,
            },
        ),
        llm=RecordingJsonLLM(response),
    )

    assert result["degradation"] == {
        "active": True,
        "reason_codes": [
            "DOCUMENT_UNCONFIRMED",
            "LLM_UNCONFIRMED_OCR_ECHO",
        ],
    }
    assert model_summary not in json.dumps(result, ensure_ascii=False)


def test_common_chinese_summary_is_not_treated_as_unconfirmed_ocr_echo():
    common_summary = "睡眠质量明显下降"
    response = valid_model_response()
    response["state_summary"] = {"summary": common_summary}
    llm = RecordingJsonLLM(response)

    result = run_assessment_v2(
        assessment_submission(
            document={
                "ocr_status": "pending",
                "confirmed_text": common_summary,
            },
        ),
        llm=llm,
    )

    assert common_summary not in llm.calls[0][1]
    assert result["state_summary"] == {"summary": common_summary}
    assert result["degradation"] == {
        "active": True,
        "reason_codes": ["DOCUMENT_UNCONFIRMED"],
    }


def test_short_common_phrase_does_not_trigger_unconfirmed_ocr_echo_filter():
    response = valid_model_response()
    response["state_summary"] = {"summary": "睡眠不好"}

    result = run_assessment_v2(
        assessment_submission(
            document={
                "ocr_status": "pending",
                "confirmed_text": "睡眠不好",
            },
        ),
        llm=RecordingJsonLLM(response),
    )

    assert result["state_summary"] == {"summary": "睡眠不好"}
    assert result["degradation"] == {
        "active": True,
        "reason_codes": ["DOCUMENT_UNCONFIRMED"],
    }


def test_blank_document_and_narrative_are_missing_sources():
    llm = RecordingJsonLLM(valid_model_response())

    result = run_assessment_v2(
        assessment_submission(
            document={
                "ocr_status": "confirmed",
                "confirmed_text": " \n\t ",
            },
            narrative_text=" \t\n ",
        ),
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
    submission = {
        "session_id": "session-task4",
        "user_id": "user-task4",
        **submission,
    }

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
        assessment_submission(
            document={
                "ocr_status": "confirmed",
                "confirmed_text": "记录：睡眠平稳。",
            },
            narrative_text="最近睡眠不稳。",
        ),
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
    submission = assessment_submission()

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
