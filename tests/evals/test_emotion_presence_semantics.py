"""Regression tests for the canonical emotion presence semantics.

These lock down the Sprint 4 Contract Owner decision for emotion presence:

  * Negative frequency_0_4 emotions (tension_worry, overthinking,
    irritability_anger, fear_unease, low_mood, interest_loss):
    value=0 → ABSENT, value∈{1,2,3,4} → PRESENT.
  * emotional_recovery (single_choice, "分值越高恢复越困难"): value=0 → ABSENT,
    value≥1 → PRESENT.
  * calm_wellbeing (reverse_scored=true): evidence value is already reversed to
    `4 - raw`, so evidence value=0 → ABSENT ("fully calm"), value≥1 → PRESENT.
  * worry_control is scored=false/weight=0 and excluded from emotion labels.

The single canonical helper ``_emotion_present`` is shared by the expected side
(``_expected_fields``) and the actual side (``_actual_fields``), so the two can
never drift apart.
"""

import pytest

from evals.run_sprint4_eval import (
    _EMOTION_LABELS,
    _actual_emotion_present,
    _emotion_present,
    _expected_fields,
    _is_active_evidence,
)


_NEGATIVE_EMOTIONS = (
    "tension_worry",
    "overthinking",
    "irritability_anger",
    "fear_unease",
    "low_mood",
    "interest_loss",
)


def _item(label, value, polarity="present", **extra):
    return {"label": label, "value": value, "polarity": polarity, **extra}


@pytest.mark.parametrize("label", _NEGATIVE_EMOTIONS)
def test_negative_emotion_value_zero_is_absent(label):
    assert _emotion_present(_item(label, 0)) is False


@pytest.mark.parametrize("label", _NEGATIVE_EMOTIONS)
@pytest.mark.parametrize("value", [1, 2, 3, 4])
def test_negative_emotion_value_one_to_four_is_present(label, value):
    assert _emotion_present(_item(label, value)) is True


@pytest.mark.parametrize("label", _NEGATIVE_EMOTIONS)
def test_negative_emotion_polarity_absent_is_absent_even_with_value(label):
    assert _emotion_present(_item(label, 3, polarity="absent")) is False


@pytest.mark.parametrize("label", _NEGATIVE_EMOTIONS)
def test_negative_emotion_negated_is_absent_even_with_value(label):
    assert _emotion_present(_item(label, 3, negated=True)) is False


def test_emotional_recovery_value_zero_is_absent():
    # value=0 = "很快恢复" (recovers fast) → not a concern.
    assert _emotion_present(_item("emotional_recovery", 0)) is False


@pytest.mark.parametrize("value", [1, 2, 3, 4])
def test_emotional_recovery_value_one_to_four_is_present(value):
    assert _emotion_present(_item("emotional_recovery", value)) is True


def test_calm_wellbeing_evidence_value_zero_is_absent():
    # Evidence value for calm_wellbeing is already reversed (4 - raw):
    # raw=4 (fully calm) → evidence value=0 → absent.
    assert _emotion_present(_item("calm_wellbeing", 0)) is False


@pytest.mark.parametrize("value", [1, 2, 3, 4])
def test_calm_wellbeing_evidence_value_one_to_four_is_present(value):
    assert _emotion_present(_item("calm_wellbeing", value)) is True


def test_worry_control_is_excluded_from_emotion_labels():
    assert "worry_control" not in _EMOTION_LABELS
    assert _emotion_present(_item("worry_control", 3)) is False


def test_non_emotion_label_is_absent():
    assert _emotion_present(_item("sleep_disturbance", 3)) is False
    assert _emotion_present(_item("daily_impact", 2)) is False


@pytest.mark.parametrize("blank", ["", "none"])
def test_blank_value_is_absent(blank):
    assert _emotion_present(_item("low_mood", blank)) is False


def test_missing_value_defaults_to_present():
    # A bare {"label": ...} (no value/polarity) means "listed as present".
    assert _emotion_present({"label": "low_mood"}) is True
    assert _emotion_present({"label": "low_mood", "polarity": "present"}) is True


def test_empty_list_value_is_absent():
    assert _emotion_present(_item("low_mood", [])) is False
    assert _emotion_present(_item("low_mood", ["none"])) is False


def test_expected_fields_drops_value_zero_emotion():
    fields = _expected_fields(
        {
            "emotion_states": [
                _item("low_mood", 0),  # value=0 → absent
                _item("tension_worry", 1),  # present
            ],
            "life_events": [],
            "physical_signals": [],
            "expected_conflicts": [],
            "expected_follow_up_count": {"min": 0, "max": 0},
            "expected_abstain": False,
            "safety_expected": "pass",
        }
    )
    assert fields["emotion_labels"] == {"tension_worry"}


def test_expected_fields_drops_absent_polarity_emotion():
    fields = _expected_fields(
        {
            "emotion_states": [
                _item("low_mood", 2, polarity="absent"),
                _item("tension_worry", 2, polarity="present"),
            ],
            "life_events": [],
            "physical_signals": [],
            "expected_conflicts": [],
            "expected_follow_up_count": {"min": 0, "max": 0},
            "expected_abstain": False,
            "safety_expected": "pass",
        }
    )
    assert fields["emotion_labels"] == {"tension_worry"}


def test_questionnaire_emotion_value_one_is_background_not_salient():
    # value=1 "偶尔" (1-3 days) is a mild/background self-report, not a
    # clearly-appearing emotion — excluded from the emotion_f1 label set.
    item = {
        "source_type": "questionnaire",
        "category": "emotion",
        "label": "low_mood",
        "value": 1,
        "polarity": "present",
    }
    assert _actual_emotion_present(item) is False


def test_questionnaire_emotion_value_two_is_background_not_salient():
    item = {
        "source_type": "questionnaire",
        "category": "emotion",
        "label": "low_mood",
        "value": 2,
        "polarity": "present",
    }
    assert _actual_emotion_present(item) is False


@pytest.mark.parametrize("value", [3, 4])
def test_questionnaire_emotion_value_three_plus_is_salient(value):
    item = {
        "source_type": "questionnaire",
        "category": "emotion",
        "label": "low_mood",
        "value": value,
        "polarity": "present",
    }
    assert _actual_emotion_present(item) is True


@pytest.mark.parametrize("value", [1, 2, 3, 4])
def test_narrative_emotion_is_present_regardless_of_value(value):
    # Qwen narrative extraction is salient by construction; any non-zero value
    # is present (never subject to the questionnaire salience threshold).
    item = {
        "source_type": "narrative",
        "category": "emotion",
        "label": "low_mood",
        "value": value,
        "polarity": "present",
    }
    assert _actual_emotion_present(item) is True


def test_questionnaire_emotion_value_zero_is_not_present_on_actual_side():
    item = {
        "source_type": "questionnaire",
        "category": "emotion",
        "label": "low_mood",
        "value": 0,
        "polarity": "absent",
    }
    assert _actual_emotion_present(item) is False


def test_expected_and_actual_share_presence_rule():
    """The same (label, value, polarity) tuple must yield the same presence
    on both the expected and actual sides."""
    for label in _EMOTION_LABELS:
        for value in (0, 1, 2, 3, 4):
            for polarity in ("present", "absent"):
                item = _item(label, value, polarity=polarity)
                assert _emotion_present(item) is _emotion_present(dict(item))
