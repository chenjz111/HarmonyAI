"""Sprint 6 Phase 0 — acceptance-case fixture contract.

This test validates the **fixture itself**, not production behaviour.

Scope rules (Phase 0):
  * pure local: no provider, no embedding, no music provider, no network
  * it does NOT import production schemas, so the fixture can never force a production
    schema change; it only validates the frozen acceptance vocabulary
  * it does NOT assert that current production code satisfies the future expectations —
    Phase 0 must not create a red baseline
  * it proves the fixture is asset-owned and synthetic: every claim code, question id and
    option code must exist in the approved knowledge assets, and no real-data marker may
    appear anywhere in the file
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "sprint6_acceptance_cases.json"
QUESTIONNAIRE_PATH = REPO_ROOT / "knowledge" / "v3" / "questionnaire-v3.0.1.json"
CLAIM_DICTIONARY_PATH = REPO_ROOT / "knowledge" / "v3" / "claim-dictionary-v3.0.json"

EXPECTED_CASE_IDS = ("A", "B", "C", "D", "E", "F", "G", "H")
EXPECTED_MODES = ("personalized_five_tone", "integrated_regulation", "basic_wellness")
EXPECTED_TONES = ("jiao", "zhi", "gong", "shang", "yu")
EXPECTED_ORGANS = ("liver", "heart", "spleen", "lung", "kidney")
EXPECTED_INPUT_TYPES = (
    "questionnaire",
    "organ_profile_snapshot",
    "insufficient_input",
    "diagnosis_snapshot_rag_empty",
    "repeatability",
)

# Markers that would indicate real runtime/patient material leaked into the fixture.
FORBIDDEN_REAL_DATA_MARKERS = (
    "uploads/",
    "uploads\\",
    "doc_2026",
    "final-e2e.db",
    "harmonyai.db",
    "acceptance-runtime",
    "C:\\",
    "/Users/",
    "/home/",
)

# Allowed "no evidence" option for the multi-choice blocks.
NONE_OPTION = "none"


@pytest.fixture(scope="module")
def fixture_text() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def fixture(fixture_text: str) -> dict:
    return json.loads(fixture_text)


@pytest.fixture(scope="module")
def questionnaire() -> dict:
    return json.loads(QUESTIONNAIRE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def claim_codes() -> set[str]:
    payload = json.loads(CLAIM_DICTIONARY_PATH.read_text(encoding="utf-8"))
    return {entry["claim_code"] for entry in payload["entries"]}


@pytest.fixture(scope="module")
def cases_by_id(fixture: dict) -> dict:
    return {case["case_id"]: case for case in fixture["cases"]}


def _question_options(questionnaire: dict) -> dict:
    """Map question_id -> (answer_type, set(option_code))."""

    options: dict[str, tuple[str, set[str]]] = {}
    for question in questionnaire["questions"]:
        codes = {option["option_code"] for option in question.get("options") or []}
        options[question["question_id"]] = (question["answer_type"], codes)
    return options


# ---------------------------------------------------------------------------
# file-level contract
# ---------------------------------------------------------------------------


def test_fixture_file_exists_and_is_valid_json():
    assert FIXTURE_PATH.is_file(), f"missing acceptance fixture: {FIXTURE_PATH}"
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)


def test_fixture_declares_sprint6_phase0_identity(fixture):
    assert fixture["schema_version"] == "sprint6_acceptance_cases_v1"
    assert fixture["sprint"] == "Sprint 6"
    assert fixture["phase"] == "Phase 0"
    assert fixture["purpose"]


def test_fixture_declares_synthetic_provenance(fixture):
    provenance = fixture["provenance"]
    assert provenance["data_class"] == "synthetic"
    assert provenance["contains_real_user_data"] is False
    assert provenance["authoring_basis"]


def test_fixture_contains_no_real_runtime_or_patient_markers(fixture_text):
    lowered = fixture_text.lower()
    leaked = [marker for marker in FORBIDDEN_REAL_DATA_MARKERS if marker.lower() in lowered]
    assert leaked == [], f"fixture references real runtime/patient material: {leaked}"


def test_vocabularies_are_closed_and_match_the_frozen_lists(fixture):
    assert tuple(fixture["mode_vocabulary"]) == EXPECTED_MODES
    assert tuple(fixture["tone_vocabulary"]) == EXPECTED_TONES
    assert tuple(fixture["organ_vocabulary"]) == EXPECTED_ORGANS
    assert tuple(fixture["input_type_vocabulary"]) == EXPECTED_INPUT_TYPES


def test_source_assets_point_at_tracked_knowledge_files(fixture):
    for label, relative in fixture["source_assets"].items():
        path = REPO_ROOT / relative
        assert path.is_file(), f"{label} asset missing: {relative}"


# ---------------------------------------------------------------------------
# case inventory contract
# ---------------------------------------------------------------------------


def test_all_cases_a_to_h_are_present(fixture):
    ids = [case["case_id"] for case in fixture["cases"]]
    assert tuple(ids) == EXPECTED_CASE_IDS


def test_case_ids_are_unique(fixture):
    ids = [case["case_id"] for case in fixture["cases"]]
    assert len(ids) == len(set(ids)), "duplicate case_id in acceptance fixture"


def test_every_case_has_the_required_fields_and_types(fixture):
    required = {
        "case_id",
        "title",
        "description",
        "input_type",
        "synthetic_input",
        "expected_future_mode",
        "expected_future_primary_tone",
        "expected_future_tone_weights_present",
        "notes",
    }
    for case in fixture["cases"]:
        missing = required - set(case)
        assert missing == set(), f"case {case.get('case_id')} missing fields: {sorted(missing)}"
        assert isinstance(case["case_id"], str) and case["case_id"]
        assert isinstance(case["title"], str) and case["title"].strip()
        assert isinstance(case["description"], str) and case["description"].strip()
        assert isinstance(case["notes"], str) and case["notes"].strip()
        assert isinstance(case["synthetic_input"], dict) and case["synthetic_input"]


# ---------------------------------------------------------------------------
# future expectation contract
# ---------------------------------------------------------------------------


def test_expected_modes_use_only_the_frozen_vocabulary(fixture):
    vocabulary = set(fixture["mode_vocabulary"])
    for case in fixture["cases"]:
        assert case["expected_future_mode"] in vocabulary, case["case_id"]


def test_personalized_cases_require_a_tone_and_non_personalized_cases_must_not_have_one(fixture):
    tones = set(fixture["tone_vocabulary"])
    for case in fixture["cases"]:
        mode = case["expected_future_mode"]
        tone = case["expected_future_primary_tone"]
        if mode == "personalized_five_tone":
            assert tone in tones, f"case {case['case_id']} must name a primary tone"
        else:
            assert tone is None, (
                f"case {case['case_id']} is {mode} and must not carry a primary tone"
            )


def test_integrated_regulation_keeps_tone_weights_and_basic_wellness_expects_none(fixture):
    for case in fixture["cases"]:
        mode = case["expected_future_mode"]
        weights_present = case["expected_future_tone_weights_present"]
        assert isinstance(weights_present, bool), case["case_id"]
        if mode == "integrated_regulation":
            assert weights_present is True, (
                f"case {case['case_id']}: integrated_regulation must retain tone weights"
            )
        if mode == "basic_wellness":
            # basic_wellness may be weightless or neutral, but must never claim a tone
            assert case["expected_future_primary_tone"] is None


def test_no_case_expects_a_fabricated_gong_for_non_personalized_modes(fixture):
    for case in fixture["cases"]:
        if case["expected_future_mode"] in {"integrated_regulation", "basic_wellness"}:
            assert case["expected_future_primary_tone"] != "gong", case["case_id"]


def test_input_types_use_only_the_frozen_vocabulary(fixture):
    vocabulary = set(fixture["input_type_vocabulary"])
    for case in fixture["cases"]:
        assert case["input_type"] in vocabulary, case["case_id"]


# ---------------------------------------------------------------------------
# synthetic input contract — asset-owned vocabulary only
# ---------------------------------------------------------------------------


def _iter_answers(case: dict):
    answers = case["synthetic_input"].get("answers")
    if answers is None:
        return []
    assert isinstance(answers, list) and answers, case["case_id"]
    return answers


def test_questionnaire_answers_reference_real_questions_and_option_codes(cases_by_id, questionnaire):
    options = _question_options(questionnaire)
    pattern = re.compile(r"^q(?:0[1-9]|10)$")

    for case_id, case in cases_by_id.items():
        answers = _iter_answers(case)
        if not answers:
            continue

        seen: set[str] = set()
        for answer in answers:
            question_id = answer["question_id"]
            assert pattern.match(question_id), f"{case_id}: bad question id {question_id}"
            assert question_id not in seen, f"{case_id}: duplicate answer for {question_id}"
            seen.add(question_id)

            assert question_id in options, f"{case_id}: {question_id} not in the approved manifest"
            manifest_answer_type, manifest_options = options[question_id]
            assert answer["answer_type"] == manifest_answer_type, (
                f"{case_id}: {question_id} answer_type mismatch"
            )

            value = answer["value"]
            if manifest_answer_type == "frequency_0_4":
                assert isinstance(value, int) and not isinstance(value, bool)
                assert 0 <= value <= 4, f"{case_id}: {question_id} frequency out of range"
            else:
                assert isinstance(value, list) and value, f"{case_id}: {question_id} needs options"
                for code in value:
                    assert code in manifest_options, (
                        f"{case_id}: {question_id} unknown option code {code!r}"
                    )
                if NONE_OPTION in value:
                    assert value == [NONE_OPTION], (
                        f"{case_id}: {question_id} 'none' must be exclusive"
                    )

        expected_ids = {f"q{index:02d}" for index in range(1, 11)}
        if case["input_type"] in {"questionnaire", "insufficient_input"}:
            assert seen == expected_ids, f"{case_id}: incomplete questionnaire answer set"


def test_multi_choice_answers_carry_only_claim_backed_option_codes(cases_by_id, questionnaire):
    """Every non-'none' multi-choice option must map to an approved claim code."""

    claims: dict[str, str | None] = {}
    for question in questionnaire["questions"]:
        for option in question.get("options") or []:
            claims[option["option_code"]] = option.get("claim_code")

    for case_id, case in cases_by_id.items():
        for answer in _iter_answers(case):
            if answer["answer_type"] != "multi_choice_evidence":
                continue
            for code in answer["value"]:
                if code == NONE_OPTION:
                    continue
                assert claims.get(code), f"{case_id}: option {code!r} has no approved claim"


def test_organ_profiles_are_well_formed_when_present(cases_by_id):
    for case_id, case in cases_by_id.items():
        profile = case.get("synthetic_organ_profile")
        if profile is None:
            continue
        assert isinstance(profile, dict), case_id
        assert set(profile) == set(EXPECTED_ORGANS), case_id
        for organ, weight in profile.items():
            assert isinstance(weight, (int, float)) and not isinstance(weight, bool), case_id
            assert 0.0 <= float(weight) <= 1.0, f"{case_id}: {organ} weight out of range"
        total = sum(float(weight) for weight in profile.values())
        assert abs(total - 1.0) <= 0.01, f"{case_id}: organ weights must sum to 1 (got {total})"


def test_rag_empty_case_declares_zero_hits(cases_by_id):
    case = cases_by_id["G"]
    rag = case["synthetic_input"]["rag_result"]
    assert rag["status"] == "empty"
    assert rag["hits"] == []
    assert rag["reason_code"] == "RAG_EMPTY"
    assert case["expected_future_primary_tone"] is None


def test_repeatability_case_references_an_existing_case(cases_by_id):
    case = cases_by_id["H"]
    payload = case["synthetic_input"]
    assert payload["repeats_reference_case"] in cases_by_id
    assert isinstance(payload["repeat_count"], int) and payload["repeat_count"] >= 2
    assert payload["checks"], "repeatability case must declare its stability checks"
    for check in payload["checks"]:
        assert isinstance(check, str) and check.strip()


def test_insufficient_case_declares_no_organ_evidence(cases_by_id):
    case = cases_by_id["E"]
    answers = _iter_answers(case)
    assert answers
    for answer in answers:
        if answer["answer_type"] == "frequency_0_4":
            assert answer["value"] == 0, "case E must not assert any emotional frequency"
        else:
            assert answer["value"] == [NONE_OPTION], "case E must not assert any body claim"
    assert case["synthetic_organ_profile"] is None
    assert case["expected_future_mode"] == "basic_wellness"


def test_fixture_claim_vocabulary_matches_the_approved_claim_dictionary(
    cases_by_id, questionnaire, claim_codes
):
    """Every claim the fixture can reach must exist in the approved claim dictionary.

    This is what makes the fixture asset-owned rather than free-form text: it can only
    express claims the medical dictionary already defines.
    """

    option_to_claim: dict[str, str] = {}
    frequency_claims: dict[str, str] = {}
    for question in questionnaire["questions"]:
        options = question.get("options") or []
        for option in options:
            claim = option.get("claim_code")
            if claim:
                option_to_claim[option["option_code"]] = claim
        if question["answer_type"] == "frequency_0_4":
            claims = {option.get("claim_code") for option in options}
            assert len(claims) == 1 and None not in claims, question["question_id"]
            frequency_claims[question["question_id"]] = claims.pop()

    used_claims: set[str] = set()
    for case_id, case in cases_by_id.items():
        for answer in _iter_answers(case):
            if answer["answer_type"] == "multi_choice_evidence":
                for code in answer["value"]:
                    if code == NONE_OPTION:
                        continue
                    claim = option_to_claim.get(code)
                    assert claim, f"{case_id}: option {code!r} maps to no approved claim"
                    used_claims.add(claim)
            else:
                claim = frequency_claims.get(answer["question_id"])
                assert claim, f"{case_id}: {answer['question_id']} has no approved claim"
                assert isinstance(answer["value"], int) and 0 <= answer["value"] <= 4
                if answer["value"] > 0:
                    used_claims.add(claim)

    assert used_claims, "fixture must exercise at least one approved claim"
    assert used_claims <= claim_codes, (
        f"fixture uses claims outside the approved dictionary: {sorted(used_claims - claim_codes)}"
    )
    assert "flank_discomfort" in used_claims
    assert "anger_tendency" in used_claims
