"""Executable checks for the frozen Sprint 4 contract artifacts."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
SPRINT4_DOCS = ROOT / "docs" / "sprint4"


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def questionnaire_contract() -> dict[str, Any]:
    return load_fixture("questionnaire-v2.1.contract.json")


@pytest.fixture(scope="module")
def assessment_contract() -> dict[str, Any]:
    return load_fixture("assessment-v2.1.contract.json")


@pytest.fixture(scope="module")
def provider_contract() -> dict[str, Any]:
    return load_fixture("provider.contract.json")


def question_by_id(contract: dict[str, Any], question_id: str) -> dict[str, Any]:
    return next(q for q in contract["questions"] if q["question_id"] == question_id)


FROZEN_OPTION_VALUES = {
    "q01_user_goal": {
        "relaxation", "sleep", "calm_irritability", "improve_low_mood",
        "focus", "restore_energy", "release_emotion", "other",
    },
    "q02_mood_weather": {"clear", "variable", "rainy", "storm", "fog"},
    "q05_overthinking": {"calm", "ripple", "waves", "swell", "storm"},
    "q16_physical_signals": {
        "neck_tension", "head_heaviness", "palpitation", "chest_tightness",
        "stomach_discomfort", "limb_fatigue", "cold_extremities", "sweating",
        "dry_mouth", "none", "other",
    },
    "q17_duration": {
        "less_than_3_days", "3_to_6_days", "1_to_2_weeks",
        "2_weeks_to_1_month", "1_to_3_months", "over_3_months",
        "recurrent_unclear",
    },
}


def test_canonical_questionnaire_option_sets_are_complete(
    questionnaire_contract: dict[str, Any],
) -> None:
    for question_id, expected_values in FROZEN_OPTION_VALUES.items():
        question = question_by_id(questionnaire_contract, question_id)
        assert {option["value"] for option in question["options"]} == expected_values
    assert question_by_id(questionnaire_contract, "q16_physical_signals")[
        "mutually_exclusive_value"
    ] == "none"

def test_questionnaire_required_fields_and_unique_ids(questionnaire_contract: dict[str, Any]) -> None:
    required = set(questionnaire_contract["required_question_fields"])
    questions = questionnaire_contract["questions"]
    assert len(questions) == 20
    assert len({q["question_id"] for q in questions}) == len(questions)
    assert all(required <= set(q) for q in questions)


def test_visual_questions_preserve_semantic_value_and_numeric_score(
    questionnaire_contract: dict[str, Any],
) -> None:
    visual = [q for q in questionnaire_contract["questions"] if q["type"] == "visual_single"]
    assert visual
    for question in visual:
        assert all(isinstance(option["value"], str) for option in question["options"])
        assert all(isinstance(option["score"], int) for option in question["options"])


def test_reverse_scored_questions_are_scored_numeric_questions(
    questionnaire_contract: dict[str, Any],
) -> None:
    reversed_questions = [q for q in questionnaire_contract["questions"] if q["reverse_scored"]]
    assert [q["question_id"] for q in reversed_questions] == ["q10_calm_wellbeing"]
    assert all(q["scored"] and q["type"] == "frequency_0_4" for q in reversed_questions)


def test_safety_questions_are_never_scored(questionnaire_contract: dict[str, Any]) -> None:
    safety_questions = [q for q in questionnaire_contract["questions"] if q["safety_only"]]
    assert {q["question_id"] for q in safety_questions} == {"q19_self_harm", "q20_emergency"}
    assert all(not q["scored"] and q["dimension"] is None for q in safety_questions)


def test_q19_every_non_never_answer_enters_safety_flow(
    questionnaire_contract: dict[str, Any],
) -> None:
    q19 = question_by_id(questionnaire_contract, "q19_self_harm")
    routes = {option["value"]: option["route"] for option in q19["options"]}
    assert routes.pop("never") == "continue_assessment"
    assert routes
    assert set(routes.values()) == {"safety_flow"}


def test_q20_none_is_mutually_exclusive_with_emergency_options(
    questionnaire_contract: dict[str, Any],
) -> None:
    q20 = question_by_id(questionnaire_contract, "q20_emergency")
    exclusive = q20["mutually_exclusive_value"]
    emergency_values = {o["value"] for o in q20["options"] if o["value"] != exclusive}

    def selection_is_valid(selection: set[str]) -> bool:
        allowed = {option["value"] for option in q20["options"]}
        return bool(selection) and selection <= allowed and not (
            exclusive in selection and len(selection) > 1
        )

    assert exclusive == "none"
    assert emergency_values
    assert selection_is_valid({"none"})
    assert selection_is_valid({next(iter(emergency_values))})
    assert not selection_is_valid({"none", next(iter(emergency_values))})
    routes = {option["value"]: option["route"] for option in q20["options"]}
    assert routes.pop("none") == "continue_assessment"
    assert routes and set(routes.values()) == {"safety_flow"}


def test_v20_q12_migration_routes_every_option_without_losing_safety(
    questionnaire_contract: dict[str, Any],
) -> None:
    old = json.loads((ROOT / "knowledge" / "questionnaire-v2.json").read_text(encoding="utf-8"))
    q12 = next(q for q in old["questions"] if q["question_id"] == "q12_physical_safety")
    migration = questionnaire_contract["v20_migration"]["q12_physical_safety"]
    routes = migration["value_routes"]
    assert set(routes) == {option["value"] for option in q12["options"]}
    assert routes["self_harm_thoughts"] == "q19_self_harm"
    assert routes["severe_chest_pain"] == "q20_emergency"
    assert routes["severe_breathing_difficulty"] == "q20_emergency"
    for option in q12["options"]:
        if option["category"] == "physical_signal":
            assert routes[option["value"]] == "q16_physical_signals"


def test_q04_is_frozen_as_unscored_qualitative_evidence(
    questionnaire_contract: dict[str, Any],
) -> None:
    q04 = question_by_id(questionnaire_contract, "q04_worry_control")
    assert q04["dimension"] == "worry_control"
    assert q04["scored"] is False
    assert q04["weight"] == 0
    assert q04["evidence_role"] == "qualitative"


def test_follow_up_limit_is_four(questionnaire_contract: dict[str, Any]) -> None:
    assert questionnaire_contract["follow_up"]["max_questions_total"] == 4
    assert questionnaire_contract["follow_up"]["allowed_count_range"] == [0, 4]


def test_scored_dimensions_are_derived_from_canonical_questions(
    questionnaire_contract: dict[str, Any], assessment_contract: dict[str, Any]
) -> None:
    derived = sorted({q["dimension"] for q in questionnaire_contract["questions"] if q["scored"]})
    assert assessment_contract["questionnaire_processing"]["scored_dimensions"] == derived
    assert assessment_contract["questionnaire_processing"]["scored_dimension_count"] == len(derived)


@pytest.mark.parametrize(
    "example_name",
    ["numeric", "categorical", "string_list", "appetite"],
)
def test_evidence_value_union_accepts_four_legal_shapes(
    assessment_contract: dict[str, Any], example_name: str
) -> None:
    schema = assessment_contract["evidence_item_schema"]
    Draft202012Validator(schema).validate(assessment_contract["valid_examples"][example_name])


def test_evidence_value_union_rejects_invalid_payloads(assessment_contract: dict[str, Any]) -> None:
    validator = Draft202012Validator(assessment_contract["evidence_item_schema"])
    for payload in assessment_contract["invalid_examples"]:
        with pytest.raises(ValidationError):
            validator.validate(payload)


def test_evidence_value_shape_is_discriminated_by_category(
    assessment_contract: dict[str, Any],
) -> None:
    validator = Draft202012Validator(assessment_contract["evidence_item_schema"])
    mismatched = [
        {"category": "emotion", "value": "relaxation"},
        {"category": "appetite", "value": 3},
        {"category": "goal", "value": ["neck_tension"]},
        {"category": "physical", "value": "neck_tension"},
    ]
    for payload in mismatched:
        with pytest.raises(ValidationError):
            validator.validate(payload)

def test_questionnaire_only_can_have_full_evidence_without_forced_follow_up(
    assessment_contract: dict[str, Any],
) -> None:
    example = assessment_contract["coverage_examples"]["questionnaire_only_complete"]
    assert example["evidence_coverage_score"] == 1.0
    assert example["source_diversity"]["count"] == 1
    assert example["follow_up_required"] is False


def test_source_diversity_is_descriptive_not_a_coverage_multiplier(
    assessment_contract: dict[str, Any],
) -> None:
    coverage = assessment_contract["evidence_coverage"]
    assert "source_diversity" not in coverage["formula"]
    assert coverage["source_diversity_affects_follow_up"] is False


def test_provider_sync_and_async_methods_share_semantics(provider_contract: dict[str, Any]) -> None:
    methods = {method["name"]: method for method in provider_contract["methods"]}
    assert set(methods) == {"complete_json", "acomplete_json"}
    comparable = ("result_schema", "error_codes", "retry_semantics", "schema_validation")
    assert all(methods["complete_json"][key] == methods["acomplete_json"][key] for key in comparable)


def test_provider_logging_contract_excludes_all_user_text(provider_contract: dict[str, Any]) -> None:
    logging = provider_contract["ordinary_logging"]
    assert set(logging["allowed_fields"]).isdisjoint(logging["forbidden_fields"])
    required_forbidden = {
        "narrative_text", "document_text", "ocr_text", "questionnaire_answer_text",
        "system_prompt", "user_prompt",
    }
    assert required_forbidden <= set(logging["forbidden_fields"])
    assert set(logging["allowed_fields"]) == {
        "request_id",
        "session_id",
        "agent_id",
        "source_type",
        "text_length",
        "provider",
        "model",
        "prompt_version",
        "latency_ms",
        "input_tokens",
        "output_tokens",
        "status",
        "error_code",
        "retry_count",
    }
    assert logging["allow_truncated_user_text"] is False


def test_all_json_contract_fixtures_are_parseable() -> None:
    fixture_paths = sorted(FIXTURES.glob("*.json"))
    assert fixture_paths
    for path in fixture_paths:
        json.loads(path.read_text(encoding="utf-8"))


def test_all_json_examples_in_sprint4_docs_are_parseable() -> None:
    pattern = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL)
    examples = []
    for path in sorted(SPRINT4_DOCS.glob("*.md")):
        for index, block in enumerate(pattern.findall(path.read_text(encoding="utf-8")), start=1):
            examples.append((path.name, index, block))
    assert examples
    for filename, index, block in examples:
        try:
            json.loads(block)
        except json.JSONDecodeError as exc:
            pytest.fail(f"{filename} JSON example #{index} is invalid: {exc}")
