import pytest

from backend.ai_engine.safety_rules import (
    build_safety_log_fields,
    evaluate_safety,
)


@pytest.mark.parametrize(
    ("inputs", "expected_flag", "expected_reason_code"),
    [
        (
            {"narrative_text": "我最近反复想自杀。"},
            "self_harm_thoughts",
            "SAFETY_SELF_HARM_OR_SUICIDE",
        ),
        (
            {"narrative_text": "I am thinking about taking my own life."},
            "self_harm_thoughts",
            "SAFETY_SELF_HARM_OR_SUICIDE",
        ),
        (
            {"narrative_text": "我有伤害自己的念头。"},
            "self_harm_thoughts",
            "SAFETY_SELF_HARM_OR_SUICIDE",
        ),
        (
            {"narrative_text": "I have thoughts of self-harm."},
            "self_harm_thoughts",
            "SAFETY_SELF_HARM_OR_SUICIDE",
        ),
        (
            {"narrative_text": "我现在持续胸痛，一直不缓解。"},
            "severe_chest_pain",
            "SAFETY_SEVERE_OR_PERSISTENT_CHEST_PAIN",
        ),
        (
            {"confirmed_ocr_text": "The patient has severe chest pain."},
            "severe_chest_pain",
            "SAFETY_SEVERE_OR_PERSISTENT_CHEST_PAIN",
        ),
        (
            {"confirmed_ocr_text": "患者明显呼吸困难，喘不上气。"},
            "severe_breathing_difficulty",
            "SAFETY_SEVERE_BREATHING_DIFFICULTY",
        ),
        (
            {"narrative_text": "I am struggling to breathe."},
            "severe_breathing_difficulty",
            "SAFETY_SEVERE_BREATHING_DIFFICULTY",
        ),
    ],
)
def test_high_risk_chinese_and_english_text_blocks_standard_prescription(
    inputs,
    expected_flag,
    expected_reason_code,
):
    result = evaluate_safety(**inputs)

    assert result["status"] == "blocked_safety"
    assert result["level"] == "high"
    assert result["flags"] == [expected_flag]
    assert result["reason_codes"] == [expected_reason_code]
    assert result["block_standard_prescription"] is True


def test_exact_q12_safety_flags_map_to_fixed_reason_codes():
    result = evaluate_safety(
        questionnaire_safety_flags=[
            "severe_breathing_difficulty",
            "self_harm_thoughts",
            "severe_chest_pain",
        ]
    )

    assert result == {
        "status": "blocked_safety",
        "level": "high",
        "flags": [
            "self_harm_thoughts",
            "severe_chest_pain",
            "severe_breathing_difficulty",
        ],
        "reason_codes": [
            "SAFETY_SELF_HARM_OR_SUICIDE",
            "SAFETY_SEVERE_OR_PERSISTENT_CHEST_PAIN",
            "SAFETY_SEVERE_BREATHING_DIFFICULTY",
        ],
        "block_standard_prescription": True,
    }


@pytest.mark.parametrize(
    "narrative_text",
    [
        "最近颈部紧张、疲劳，身体有点不舒服。",
        "I have neck tension, fatigue, and general discomfort.",
        "I read a suicide prevention article and practiced breathing exercises.",
        "A brief mild chest discomfort after exercise has gone away.",
    ],
)
def test_ordinary_discomfort_and_broad_context_words_do_not_block(narrative_text):
    result = evaluate_safety(
        narrative_text=narrative_text,
        questionnaire_safety_flags=["neck_tension", "fatigue", "other"],
    )

    assert result == {
        "status": "success",
        "level": "none",
        "flags": [],
        "reason_codes": [],
        "block_standard_prescription": False,
    }


def test_multiple_sources_are_merged_once_in_deterministic_rule_order():
    inputs = {
        "narrative_text": "I am thinking about taking my own life.",
        "confirmed_ocr_text": "记录显示持续胸痛。",
        "questionnaire_safety_flags": [
            "severe_breathing_difficulty",
            "self_harm_thoughts",
        ],
    }

    first = evaluate_safety(**inputs)
    second = evaluate_safety(**inputs)

    assert first == second == {
        "status": "blocked_safety",
        "level": "high",
        "flags": [
            "self_harm_thoughts",
            "severe_chest_pain",
            "severe_breathing_difficulty",
        ],
        "reason_codes": [
            "SAFETY_SELF_HARM_OR_SUICIDE",
            "SAFETY_SEVERE_OR_PERSISTENT_CHEST_PAIN",
            "SAFETY_SEVERE_BREATHING_DIFFICULTY",
        ],
        "block_standard_prescription": True,
    }


def test_log_fields_are_built_only_from_fixed_reason_codes():
    fields = build_safety_log_fields(
        [
            "SAFETY_SEVERE_BREATHING_DIFFICULTY",
            "SAFETY_SELF_HARM_OR_SUICIDE",
            "SAFETY_SELF_HARM_OR_SUICIDE",
        ]
    )

    assert fields == {
        "status": "blocked_safety",
        "level": "high",
        "reason_codes": [
            "SAFETY_SELF_HARM_OR_SUICIDE",
            "SAFETY_SEVERE_BREATHING_DIFFICULTY",
        ],
        "block_standard_prescription": True,
    }
    assert "narrative_text" not in fields
    assert "confirmed_ocr_text" not in fields


def test_log_fields_reject_non_reason_code_text():
    with pytest.raises(ValueError) as error:
        build_safety_log_fields(["患者原文：我持续胸痛"])

    assert str(error.value) == "unsupported safety reason code"
