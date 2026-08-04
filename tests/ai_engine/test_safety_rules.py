from typing import get_type_hints

import pytest

import backend.ai_engine.safety_rules as safety_rules
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
            {"narrative_text": "我现在有强烈的自杀念头。"},
            "self_harm_thoughts",
            "SAFETY_SELF_HARM_OR_SUICIDE",
        ),
        (
            {"narrative_text": "我真的想死。"},
            "self_harm_thoughts",
            "SAFETY_SELF_HARM_OR_SUICIDE",
        ),
        (
            {"narrative_text": "I feel suicidal and have a plan."},
            "self_harm_thoughts",
            "SAFETY_SELF_HARM_OR_SUICIDE",
        ),
        (
            {"narrative_text": "I am thinking of killing myself."},
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
            {"narrative_text": "胸痛已经持续两个小时。"},
            "severe_chest_pain",
            "SAFETY_SEVERE_OR_PERSISTENT_CHEST_PAIN",
        ),
        (
            {"narrative_text": "My chest pain has lasted for two hours."},
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
        (
            {"narrative_text": "我呼吸困难，说不出完整的话。"},
            "severe_breathing_difficulty",
            "SAFETY_SEVERE_BREATHING_DIFFICULTY",
        ),
        (
            {"narrative_text": "I have extreme shortness of breath."},
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


@pytest.mark.parametrize(
    ("narrative_text", "expected_flag", "expected_reason_code"),
    [
        (
            "我现在想去死。",
            "self_harm_thoughts",
            "SAFETY_SELF_HARM_OR_SUICIDE",
        ),
        (
            "我有明确的自杀计划。",
            "self_harm_thoughts",
            "SAFETY_SELF_HARM_OR_SUICIDE",
        ),
        (
            "I plan to commit suicide.",
            "self_harm_thoughts",
            "SAFETY_SELF_HARM_OR_SUICIDE",
        ),
        (
            "胸痛两个小时了。",
            "severe_chest_pain",
            "SAFETY_SEVERE_OR_PERSISTENT_CHEST_PAIN",
        ),
        (
            "I have had chest pain for two hours.",
            "severe_chest_pain",
            "SAFETY_SEVERE_OR_PERSISTENT_CHEST_PAIN",
        ),
        (
            "呼吸困难到一句完整话都说不出来。",
            "severe_breathing_difficulty",
            "SAFETY_SEVERE_BREATHING_DIFFICULTY",
        ),
        (
            "I am too breathless to speak.",
            "severe_breathing_difficulty",
            "SAFETY_SEVERE_BREATHING_DIFFICULTY",
        ),
    ],
)
def test_composable_risk_concepts_block_without_full_sentence_enumeration(
    narrative_text,
    expected_flag,
    expected_reason_code,
):
    result = evaluate_safety(narrative_text=narrative_text)

    assert result == {
        "status": "blocked_safety",
        "level": "high",
        "flags": [expected_flag],
        "reason_codes": [expected_reason_code],
        "block_standard_prescription": True,
    }


@pytest.mark.parametrize(
    ("narrative_text", "expected_flag", "expected_reason_code"),
    [
        (
            "我正在自残。",
            "self_harm_thoughts",
            "SAFETY_SELF_HARM_OR_SUICIDE",
        ),
        (
            "我正在考虑自杀。",
            "self_harm_thoughts",
            "SAFETY_SELF_HARM_OR_SUICIDE",
        ),
        (
            "I am self-harming.",
            "self_harm_thoughts",
            "SAFETY_SELF_HARM_OR_SUICIDE",
        ),
        (
            "I have a suicide plan.",
            "self_harm_thoughts",
            "SAFETY_SELF_HARM_OR_SUICIDE",
        ),
        (
            "胸口一直疼。",
            "severe_chest_pain",
            "SAFETY_SEVERE_OR_PERSISTENT_CHEST_PAIN",
        ),
        (
            "胸痛超过半小时。",
            "severe_chest_pain",
            "SAFETY_SEVERE_OR_PERSISTENT_CHEST_PAIN",
        ),
        (
            "chest pain for half an hour.",
            "severe_chest_pain",
            "SAFETY_SEVERE_OR_PERSISTENT_CHEST_PAIN",
        ),
        (
            "我不能呼吸。",
            "severe_breathing_difficulty",
            "SAFETY_SEVERE_BREATHING_DIFFICULTY",
        ),
        (
            "我呼吸很困难。",
            "severe_breathing_difficulty",
            "SAFETY_SEVERE_BREATHING_DIFFICULTY",
        ),
        (
            "I can barely breathe.",
            "severe_breathing_difficulty",
            "SAFETY_SEVERE_BREATHING_DIFFICULTY",
        ),
        (
            "I am unable to breathe.",
            "severe_breathing_difficulty",
            "SAFETY_SEVERE_BREATHING_DIFFICULTY",
        ),
    ],
)
def test_additional_composable_direct_risk_variants_block(
    narrative_text,
    expected_flag,
    expected_reason_code,
):
    result = evaluate_safety(narrative_text=narrative_text)

    assert result == {
        "status": "blocked_safety",
        "level": "high",
        "flags": [expected_flag],
        "reason_codes": [expected_reason_code],
        "block_standard_prescription": True,
    }


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
    result = evaluate_safety(narrative_text=narrative_text)

    assert result == {
        "status": "success",
        "level": "none",
        "flags": [],
        "reason_codes": [],
        "block_standard_prescription": False,
    }


def test_questionnaire_safety_flags_accept_a_tuple_of_exact_flags():
    result = evaluate_safety(
        questionnaire_safety_flags=("severe_breathing_difficulty",)
    )

    assert result == {
        "status": "blocked_safety",
        "level": "high",
        "flags": ["severe_breathing_difficulty"],
        "reason_codes": ["SAFETY_SEVERE_BREATHING_DIFFICULTY"],
        "block_standard_prescription": True,
    }


@pytest.mark.parametrize(
    "invalid_flags",
    [
        "self_harm_thoughts",
        ["unknown_signal"],
        ["self_harm_thoughts", 7],
        ["self_harm_thoughts", ["nested_value"]],
    ],
)
def test_questionnaire_safety_flags_reject_invalid_input_without_echoing_it(
    invalid_flags,
):
    with pytest.raises(ValueError) as error:
        evaluate_safety(questionnaire_safety_flags=invalid_flags)

    assert str(error.value) == "invalid questionnaire safety flags"


@pytest.mark.parametrize(
    "narrative_text",
    [
        "我不想自杀。",
        "我以前想自杀，但现在已经没有这种想法。",
        "病历记录：无持续胸痛，仅偶发轻微不适。",
        "The patient denies severe chest pain.",
        "未见明显呼吸困难。",
        "Seek urgent care if severe chest pain develops.",
    ],
)
def test_negated_resolved_and_conditional_contexts_do_not_block(narrative_text):
    result = evaluate_safety(narrative_text=narrative_text)

    assert result == {
        "status": "success",
        "level": "none",
        "flags": [],
        "reason_codes": [],
        "block_standard_prescription": False,
    }


@pytest.mark.parametrize(
    "narrative_text",
    [
        "没有想自杀。",
        "我不想伤害自己。",
        "I do not want to die.",
        "I am not thinking about suicide.",
        "我曾经想自杀但现在已无这种想法。",
        "I had thoughts of suicide in the past but no longer do.",
        "患者没有严重胸痛。",
        "No severe difficulty breathing.",
        "如出现严重胸痛请立即就医。",
        "如果喘不上气请立即就医。",
    ],
)
def test_candidate_context_excludes_negated_resolved_and_conditional_risk(
    narrative_text,
):
    result = evaluate_safety(narrative_text=narrative_text)

    assert result == {
        "status": "success",
        "level": "none",
        "flags": [],
        "reason_codes": [],
        "block_standard_prescription": False,
    }


@pytest.mark.parametrize(
    "narrative_text",
    [
        "I don't want to die.",
        "denies having severe chest pain.",
        "If severe chest pain develops, call 911.",
        "胸痛不严重。",
        "否认有持续胸痛。",
        "如胸痛持续十分钟请拨打120。",
    ],
)
def test_additional_candidate_negation_and_conditional_guidance_do_not_block(
    narrative_text,
):
    result = evaluate_safety(narrative_text=narrative_text)

    assert result == {
        "status": "success",
        "level": "none",
        "flags": [],
        "reason_codes": [],
        "block_standard_prescription": False,
    }


@pytest.mark.parametrize(
    "narrative_text",
    [
        "Previously I had thoughts of suicide, but I no longer smoke.",
        "我以前有自杀念头但现在没有工作。",
    ],
)
def test_unrelated_current_state_does_not_resolve_past_self_harm_risk(
    narrative_text,
):
    result = evaluate_safety(narrative_text=narrative_text)

    assert result == {
        "status": "blocked_safety",
        "level": "high",
        "flags": ["self_harm_thoughts"],
        "reason_codes": ["SAFETY_SELF_HARM_OR_SUICIDE"],
        "block_standard_prescription": True,
    }


def test_questionnaire_flags_annotation_matches_runtime_contract():
    annotation = get_type_hints(evaluate_safety)["questionnaire_safety_flags"]

    assert annotation == list[str] | tuple[str, ...] | None


def test_candidate_exclusion_does_not_quadratically_rescan_clause_prefix(
    monkeypatch,
):
    original_split = safety_rules.re.split
    scanned_characters = 0

    def counting_split(pattern, string, *args, **kwargs):
        nonlocal scanned_characters
        if pattern == r"[,，]":
            scanned_characters += len(string)
        return original_split(pattern, string, *args, **kwargs)

    monkeypatch.setattr(safety_rules.re, "split", counting_split)

    def evaluate_repeated_negated_candidates(repetitions):
        nonlocal scanned_characters
        scanned_characters = 0
        result = evaluate_safety(
            narrative_text="denies having severe chest pain, " * repetitions
        )
        assert result["block_standard_prescription"] is False
        return scanned_characters

    smaller_scan = evaluate_repeated_negated_candidates(120)
    doubled_scan = evaluate_repeated_negated_candidates(240)

    assert doubled_scan <= max(64, smaller_scan * 3)


def test_local_context_rfind_is_bounded_to_candidate_window():
    rfind_calls = []

    class TrackingClause(str):
        def rfind(self, substring, start=0, end=None):
            rfind_calls.append((substring, start, end))
            return super().rfind(
                substring,
                start,
                len(self) if end is None else end,
            )

    clause = TrackingClause("x" * 200)

    assert safety_rules._local_context(clause, 200) == (152, "x" * 48)
    assert rfind_calls == [
        (",", 152, 200),
        ("，", 152, 200),
    ]


@pytest.mark.parametrize(
    "narrative_text",
    [
        "I do not want to die, but I am now planning suicide.",
        "I am not thinking about suicide, but I now plan to kill myself.",
    ],
)
def test_negated_intent_does_not_consume_later_direct_self_harm_risk(
    narrative_text,
):
    result = evaluate_safety(narrative_text=narrative_text)

    assert result == {
        "status": "blocked_safety",
        "level": "high",
        "flags": ["self_harm_thoughts"],
        "reason_codes": ["SAFETY_SELF_HARM_OR_SUICIDE"],
        "block_standard_prescription": True,
    }


@pytest.mark.parametrize(
    ("narrative_text", "expected_flag", "expected_reason_code"),
    [
        (
            "我不想自杀；但我现在想去死。",
            "self_harm_thoughts",
            "SAFETY_SELF_HARM_OR_SUICIDE",
        ),
        (
            "The patient denies severe chest pain; "
            "I have had chest pain for two hours.",
            "severe_chest_pain",
            "SAFETY_SEVERE_OR_PERSISTENT_CHEST_PAIN",
        ),
        (
            "未见明显呼吸困难。\n呼吸困难到一句完整话都说不出来。",
            "severe_breathing_difficulty",
            "SAFETY_SEVERE_BREATHING_DIFFICULTY",
        ),
    ],
)
def test_excluded_clause_does_not_hide_later_direct_risk(
    narrative_text,
    expected_flag,
    expected_reason_code,
):
    result = evaluate_safety(narrative_text=narrative_text)

    assert result == {
        "status": "blocked_safety",
        "level": "high",
        "flags": [expected_flag],
        "reason_codes": [expected_reason_code],
        "block_standard_prescription": True,
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
