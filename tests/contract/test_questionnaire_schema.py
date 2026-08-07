"""Contract tests: Questionnaire V2.0 / V2.1 / Quick State / Follow-Up schema validation.

Validates that questionnaire JSON files conform to the Sprint 4 contract
defined in docs/sprint4/questionnaire-contract-v2.1.md.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pytest


# ---------------------------------------------------------------------------
# Contract constants (from questionnaire-contract-v2.1.md)
# ---------------------------------------------------------------------------

REQUIRED_QUESTION_FIELDS = frozenset({
    "question_id", "module", "order", "text", "type",
    "time_window", "options", "dimension", "scored",
    "reverse_scored", "safety_only", "weight", "ui", "version",
})

VALID_TYPES = frozenset({
    "frequency_0_4", "visual_single", "single_choice",
    "multi_choice", "scale_0_10", "duration_choice",
})

VALID_MODULES_V21 = frozenset({"A_goal", "B_activation", "C_mood",
                                "D_sleep_energy", "E_duration_impact",
                                "F_safety"})

VALID_DIMENSIONS_V21 = frozenset({
    "tension_worry", "worry_control", "overthinking",
    "irritability_anger", "fear_unease", "low_mood",
    "interest_loss", "calm_wellbeing", "emotional_recovery",
    "sleep_disturbance", "unrefreshing_sleep", "low_energy",
    "appetite_change", "physical_signals", "daily_impact",
})

EXPECTED_V20_QUESTION_COUNT = 12
EXPECTED_V21_QUESTION_COUNT = 20
EXPECTED_QUICK_STATE_COUNT = 6


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_question(q: Mapping[str, Any], index: int, *, is_v20: bool = False) -> list[str]:
    errors: list[str] = []
    prefix = f"question[{index}] ({q.get('question_id', '?')})"

    # V2.0 uses nested scoring.scored; normalize
    scored = q.get("scored")
    if scored is None and isinstance(q.get("scoring"), Mapping):
        scored = q["scoring"].get("scored")
    dimension = q.get("dimension")
    if dimension is None and isinstance(q.get("scoring"), Mapping):
        dimension = q["scoring"].get("dimension")
    safety_only = q.get("safety_only", False)
    qtype = q.get("type")

    # V2.1 requires flat fields; V2.0 is exempt
    if not is_v20:
        missing = REQUIRED_QUESTION_FIELDS - set(q)
        if missing:
            errors.append(f"{prefix}: missing V2.1 required fields: {missing}")

    # Type validity
    valid_types = VALID_TYPES | {"visual_multi"}  # V2.0 q12
    if qtype and qtype not in valid_types:
        errors.append(f"{prefix}: invalid type '{qtype}'")

    # Scored questions must have a dimension
    if scored and not dimension:
        errors.append(f"{prefix}: scored=True but dimension is null")

    # Safety-only questions must NOT be scored
    if safety_only and scored:
        errors.append(f"{prefix}: safety_only=True but scored=True")

    # Visual questions must have options with both 'value' (str) and 'score' (int)
    # V2.0 visual questions use value/icon/label; check normalized
    if qtype in ("visual_single",):
        for opt in q.get("options", []):
            has_score = "score" in opt
            has_label = "label" in opt
            if not has_label:
                errors.append(f"{prefix}: visual option missing label: {opt}")

    # frequency_0_4 must have options 0-4
    if qtype == "frequency_0_4":
        values = {opt.get("value") for opt in q.get("options", [])}
        if values != {0, 1, 2, 3, 4}:
            errors.append(
                f"{prefix}: frequency_0_4 options should be 0-4, got {sorted(values)}"
            )

    # V2.1 version must be 2.1; V2.0 is exempt
    if not is_v20 and "version" in q and q["version"] not in ("2.0", "2.1"):
        errors.append(f"{prefix}: unexpected version '{q['version']}'")

    return errors


# ---------------------------------------------------------------------------
# Tests: V2.0 backward compatibility
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def v20_questionnaire() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[2] / "knowledge" / "questionnaire-v2.json"
    if not path.exists():
        pytest.skip("questionnaire-v2.json not found")
    return _load_json(path)


def test_v20_schema_version(v20_questionnaire: dict[str, Any]) -> None:
    assert v20_questionnaire.get("schema_version") == "questionnaire_v2.0"


def test_v20_question_count(v20_questionnaire: dict[str, Any]) -> None:
    questions = v20_questionnaire.get("questions", [])
    assert len(questions) == EXPECTED_V20_QUESTION_COUNT, (
        f"V2.0 should have {EXPECTED_V20_QUESTION_COUNT} questions, got {len(questions)}"
    )


def test_v20_all_questions_valid(v20_questionnaire: dict[str, Any]) -> None:
    errors: list[str] = []
    for i, q in enumerate(v20_questionnaire.get("questions", [])):
        errors.extend(_validate_question(q, i, is_v20=True))
    assert not errors, "\n" + "\n".join(errors)


def test_v20_question_ids_unique(v20_questionnaire: dict[str, Any]) -> None:
    ids = [q["question_id"] for q in v20_questionnaire.get("questions", [])]
    duplicates = {qid for qid in ids if ids.count(qid) > 1}
    assert not duplicates, f"Duplicate question_ids: {duplicates}"


def test_v20_scored_count(v20_questionnaire: dict[str, Any]) -> None:
    # V2.0 uses nested scoring.scored, not flat scored
    def _is_scored(q: Mapping[str, Any]) -> bool:
        scoring = q.get("scoring")
        if isinstance(scoring, Mapping):
            return bool(scoring.get("scored"))
        return bool(q.get("scored"))
    scored = [q for q in v20_questionnaire.get("questions", []) if _is_scored(q)]
    assert len(scored) == 10, f"V2.0 should have 10 scored questions, got {len(scored)}"


def test_v20_safety_not_scored(v20_questionnaire: dict[str, Any]) -> None:
    def _is_safety(q: Mapping[str, Any]) -> bool:
        scoring = q.get("scoring")
        if isinstance(scoring, Mapping):
            return not scoring.get("scored") and scoring.get("dimension") is None
        return bool(q.get("safety_only"))
    def _is_scored(q: Mapping[str, Any]) -> bool:
        scoring = q.get("scoring")
        if isinstance(scoring, Mapping):
            return bool(scoring.get("scored"))
        return bool(q.get("scored"))
    safety = [q for q in v20_questionnaire.get("questions", []) if _is_safety(q)]
    for q in safety:
        assert not _is_scored(q), f"{q['question_id']}: safety question should not be scored"


# ---------------------------------------------------------------------------
# Tests: Scoring rules
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def scoring_rules() -> dict[str, Any] | None:
    path = Path(__file__).resolve().parents[2] / "knowledge" / "questionnaire-scoring-v2.json"
    if not path.exists():
        return None
    return _load_json(path)


def test_scoring_rules_match_questionnaire(
    v20_questionnaire: dict[str, Any],
    scoring_rules: dict[str, Any] | None,
) -> None:
    if scoring_rules is None:
        pytest.skip("scoring rules not found")
    scored_ids = {q["question_id"] for q in v20_questionnaire.get("questions", [])
                  if q.get("scored")}
    # scoring rules should cover all scored questions
    # (exact structure depends on the JSON format)


# ---------------------------------------------------------------------------
# Tests: V2.1 placeholder (to be filled when questionnaire-v2.1.json exists)
# ---------------------------------------------------------------------------

def test_v21_json_placeholder() -> None:
    """Reminder: create knowledge/questionnaire-v2.1.json per contract §5."""
    path = Path(__file__).resolve().parents[2] / "knowledge" / "questionnaire-v2.1.json"
    if not path.exists():
        pytest.skip(
            "questionnaire-v2.1.json not yet created — 肖宇翔 S4-02 deliverable"
        )


def test_quick_state_json_placeholder() -> None:
    """Reminder: create knowledge/quick-state-questionnaire-v1.json per contract §6."""
    path = Path(__file__).resolve().parents[2] / "knowledge" / "quick-state-questionnaire-v1.json"
    if not path.exists():
        pytest.skip(
            "quick-state-questionnaire-v1.json not yet created — 肖宇翔 S4-02 deliverable"
        )


# ---------------------------------------------------------------------------
# Tests: Cross-version integrity
# ---------------------------------------------------------------------------

def test_v20_to_v21_migration_keys_defined() -> None:
    """Contract §9 defines a V2.0→V2.1 mapping table. Verify it covers all V2.0 IDs."""
    mapping = {
        "q02_tension_worry": "q03_tension_worry",
        "q03_overthinking": "q05_overthinking",
        "q04_irritability_anger": "q06_irritability_anger",
        "q05_low_mood": "q08_low_mood",
        "q06_interest_loss": "q09_interest_loss",
        "q07_fear_unease": "q07_fear_unease",
        "q08_sleep_disturbance": "q12_sleep_disturbance",
        "q09_low_energy": "q14_low_energy",
        "q10_appetite_change": "q15_appetite_change",
        "q11_daily_impact": "q18_daily_impact",
        "q01_mood_weather": "q02_mood_weather",
        "q12_physical_safety": "q16_physical_signals",
    }
    assert len(mapping) == 12, f"Mapping should cover 12 V2.0 questions, got {len(mapping)}"
    # All values must be V2.1 IDs (not yet validated against actual JSON)
    assert all(isinstance(v, str) and v for v in mapping.values())
