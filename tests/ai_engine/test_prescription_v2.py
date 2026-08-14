"""Prescription Agent V2.1 fallback modes.

Guarantees from the Owner decision:
* Diagnosis confidence determines prescription *specificity*, not whether music exists.
* A diagnosis abstention that is only "no local multidimensional candidate" must still
  yield music via ``emotion_based`` / ``wellness`` modes.
* Only SAFETY and genuine information insufficiency withhold music.
* The legacy V2.0 path (``assessment=None``) keeps its exact ``_withheld_reason`` contract.
"""

from backend.ai_engine.diagnosis_v2 import run_diagnosis_v21
from backend.ai_engine.music_agent import match_music_v2
from backend.ai_engine.prescription_v2 import (
    run_prescription_v2,
    select_prescription_mode,
    _candidate_tone_weights,
    _valid_candidates,
)


_ALL_DIMENSIONS = [
    "tension_worry",
    "overthinking",
    "irritability_anger",
    "fear_unease",
    "low_mood",
    "interest_loss",
    "calm_wellbeing",
    "emotional_recovery",
    "sleep_disturbance",
    "unrefreshing_sleep",
    "low_energy",
    "appetite_change",
    "daily_impact",
]


def v21_assessment(
    *,
    status="success",
    dimensions=None,
    coverage=1.0,
    missing=None,
    requires_confirmation=False,
    conflicts=None,
):
    scores = {dimension: 0 for dimension in _ALL_DIMENSIONS}
    if dimensions:
        scores.update(dimensions)
    return {
        "assessment_id": "asmt-rx-test",
        "status": status,
        "requires_user_confirmation": requires_confirmation,
        "revision": 2,
        "emotion_profile": {"dimension_scores": scores},
        "evidence_items": [],
        "evidence_coverage_score": coverage,
        "missing_information": missing or [],
        "conflicts": conflicts or [],
    }


def _prescribe(assessment):
    diagnosis = run_diagnosis_v21(assessment)
    prescription = run_prescription_v2(diagnosis, assessment=assessment)
    return diagnosis, prescription


def _catalog():
    return [
        {
            "music_id": "m-jiao",
            "title": "角调疗愈曲",
            "tone_id": "jiao",
            "bpm": 68,
            "duration_seconds": 900,
            "stream_url": "/media/jiao.mp3",
            "source_type": "matched",
            "instruments": ["古筝"],
        },
        {
            "music_id": "m-gong",
            "title": "宫调疗愈曲",
            "tone_id": "gong",
            "bpm": 62,
            "duration_seconds": 900,
            "stream_url": "/media/gong.mp3",
            "source_type": "matched",
            "instruments": ["编钟"],
        },
    ]


def test_case_a_clear_syndrome_maps_to_syndrome_based():
    _, prescription = _prescribe(
        v21_assessment(dimensions={"tension_worry": 100, "irritability_anger": 75})
    )

    assert prescription["generation_mode"] == "matched"
    assert prescription["prescription_mode"] == "syndrome_based"
    assert prescription["music_feature"]["tone_id"] == "jiao"
    assert prescription["source_basis"]
    assert prescription["recommendation_specificity"] == "high"
    assert prescription["recommendation_confidence"]["level"] == "high"
    assert prescription["recommendation_confidence"]["score"] == 1.0


def test_case_b_explicit_primary_wins_over_secondary_candidates():
    # When Diagnosis has produced an explicit primary_tendency, a secondary
    # candidate list must NOT downgrade it to candidate_blend.
    diagnosis, prescription = _prescribe(
        v21_assessment(
            dimensions={
                "tension_worry": 100,
                "irritability_anger": 70,
                "sleep_disturbance": 75,
            }
        )
    )

    assert diagnosis["abstained"] is False
    assert len(diagnosis["candidate_tendencies"]) == 2
    assert diagnosis["primary_tendency"]["id"] in ("syd_001", "syd_002")
    assert prescription["prescription_mode"] == "syndrome_based"
    assert prescription["music_feature"]["tone_id"] == "jiao"
    assert "tone_weights" not in prescription
    assert prescription["generation_mode"] == "matched"


def test_case_c_abstained_no_candidate_still_yields_emotion_based_music():
    diagnosis, prescription = _prescribe(
        v21_assessment(dimensions={"tension_worry": 75})
    )

    assert diagnosis["abstained"] is True
    assert diagnosis["abstain_reason"] == "INSUFFICIENT_EVIDENCE"
    assert prescription["generation_mode"] == "matched"
    assert prescription["prescription_mode"] == "emotion_based"
    assert prescription["dominant_dimension"] == "tension_worry"
    assert prescription["music_feature"]["tone_id"] == "jiao"
    assert prescription["recommendation_specificity"] == "conservative"
    assert prescription["recommendation_confidence"]["score"] == 1.0


def test_case_weak_syndrome_is_more_specific_than_wellness():
    diagnosis, prescription = _prescribe(
        v21_assessment(dimensions={"tension_worry": 25, "overthinking": 25})
    )

    assert diagnosis["abstained"] is False
    assert prescription["prescription_mode"] == "syndrome_based"
    assert prescription["music_feature"]["tone_id"] == "jiao"


def test_case_d_stable_state_yields_wellness_gong():
    diagnosis, prescription = _prescribe(
        v21_assessment(dimensions={"tension_worry": 25})
    )

    assert diagnosis["abstained"] is True
    assert prescription["generation_mode"] == "matched"
    assert prescription["prescription_mode"] == "wellness"
    assert prescription["music_feature"]["tone_id"] == "gong"
    assert prescription["recommendation_specificity"] == "wellness"


def test_case_e_safety_still_withholds():
    _, prescription = _prescribe(v21_assessment(status="blocked_safety"))

    assert prescription["generation_mode"] == "withheld"
    assert prescription["withheld_reason"] == "SAFETY_BLOCKED"
    assert prescription["status"] == "blocked_safety"


def test_case_f_low_evidence_coverage_withholds():
    _, prescription = _prescribe(
        v21_assessment(dimensions={"tension_worry": 100}, coverage=0.2)
    )

    assert prescription["generation_mode"] == "withheld"
    assert prescription["withheld_reason"] == "INSUFFICIENT_EVIDENCE"


def test_case_g_important_missing_information_withholds():
    _, prescription = _prescribe(
        v21_assessment(
            dimensions={"tension_worry": 100},
            missing=[{"field": "duration", "severity": "important"}],
        )
    )

    assert prescription["generation_mode"] == "withheld"
    assert prescription["withheld_reason"] == "INSUFFICIENT_EVIDENCE"


def test_case_h_unconfirmed_assessment_withholds():
    _, prescription = _prescribe(
        v21_assessment(dimensions={"tension_worry": 100}, requires_confirmation=True)
    )

    assert prescription["generation_mode"] == "withheld"
    assert prescription["withheld_reason"] == "ASSESSMENT_NOT_CONFIRMED"


def test_case_i_legacy_low_confidence_still_withholds_without_assessment():
    diagnosis = {
        "status": "success",
        "confidence": {"level": "low", "score": 0.2},
        "primary_tendency": {"id": "syd_001", "score": 87.5},
        "conflicts": [],
        "assessment_status": "success",
        "assessment_degradation": {"active": False, "reason_codes": []},
    }
    prescription = run_prescription_v2(diagnosis)

    assert prescription["generation_mode"] == "withheld"
    assert prescription["withheld_reason"] == "LOW_CONFIDENCE"


def test_case_j_legacy_normal_diagnosis_keeps_matched_contract():
    diagnosis = {
        "status": "success",
        "confidence": {"level": "high", "score": 0.85},
        "primary_tendency": {
            "id": "syd_001",
            "label": "肝郁化火",
            "score": 87.5,
            "element": "木",
            "organs": ["肝"],
            "supporting_dimensions": ["tension_worry", "irritability_anger"],
        },
        "conflicts": [],
        "warnings": [],
        "assessment_status": "success",
        "assessment_degradation": {"active": False, "reason_codes": []},
    }
    prescription = run_prescription_v2(diagnosis)

    assert prescription["status"] == "success"
    assert prescription["generation_mode"] == "matched"
    assert prescription["prescription_mode"] == "syndrome_based"
    assert prescription["music_feature"]["tone_id"] == "jiao"
    assert prescription["recommendation_specificity"] == "high"
    assert prescription["recommendation_confidence"]["score"] is None
    assert prescription["recommendation_confidence"]["basis"] == "unavailable"


def test_emotion_based_prescription_reaches_music_matching():
    diagnosis, prescription = _prescribe(
        v21_assessment(dimensions={"tension_worry": 75})
    )

    music = match_music_v2(prescription, _catalog())

    assert music["status"] == "success"
    assert music["stream_url"] == "/media/jiao.mp3"
    assert music["mode"] == "角调"


def test_select_prescription_mode_is_deterministic():
    diagnosis = run_diagnosis_v21(
        v21_assessment(dimensions={"tension_worry": 75})
    )
    assessment = v21_assessment(dimensions={"tension_worry": 75})

    assert select_prescription_mode(diagnosis, assessment) == "emotion_based"
    assert select_prescription_mode(diagnosis, assessment) == "emotion_based"


def _empty_dims_assessment(*, coverage):
    return {
        "assessment_id": "asmt-empty",
        "status": "success",
        "requires_user_confirmation": False,
        "revision": 2,
        "emotion_profile": {"dimension_scores": {}},
        "evidence_items": [],
        "evidence_coverage_score": coverage,
        "missing_information": [],
        "conflicts": [],
    }


def _blend_diagnosis():
    """Synthetic Diagnosis: not abstained, no explicit primary, multiple valid
    candidates. This state does not occur in the real V2.1 contract but exercises
    the candidate_blend compatibility path."""
    return {
        "status": "success",
        "abstained": False,
        "abstain_reason": None,
        "primary_tendency": None,
        "candidate_tendencies": [
            {"id": "syd_001", "score": 85.0},
            {"id": "syd_003", "score": 80.0},
        ],
    }


# --- Blocker 2: wellness 判定 ---

def test_multiple_near_moderate_dimensions_are_not_wellness():
    # 多个接近中等的负向维度不能因「每个都 < 50」就被判为「平稳」。
    _, prescription = _prescribe(
        v21_assessment(
            dimensions={
                "tension_worry": 45,
                "sleep_disturbance": 45,
                "low_energy": 45,
            }
        )
    )
    assert prescription["prescription_mode"] == "emotion_based"


def test_empty_dimensions_with_insufficient_evidence_withholds():
    _, prescription = _prescribe(_empty_dims_assessment(coverage=0.2))
    assert prescription["generation_mode"] == "withheld"
    assert prescription["withheld_reason"] == "INSUFFICIENT_EVIDENCE"


def test_empty_dimensions_are_not_wellness():
    # dimensions 为空（即便 coverage 充足）也不能自动 wellness → 真实信息不足。
    _, prescription = _prescribe(_empty_dims_assessment(coverage=1.0))
    assert prescription["generation_mode"] == "withheld"
    assert prescription["withheld_reason"] == "INSUFFICIENT_EVIDENCE"


# --- Blocker 3: recommendation confidence 数据驱动、不伪精确 ---

def test_recommendation_confidence_tracks_evidence_coverage():
    _, prescription = _prescribe(
        v21_assessment(
            dimensions={"tension_worry": 100, "irritability_anger": 75},
            coverage=0.6,
        )
    )
    assert prescription["recommendation_specificity"] == "high"
    assert prescription["recommendation_confidence"]["score"] == 0.6
    assert prescription["recommendation_confidence"]["level"] == "medium"
    assert prescription["recommendation_confidence"]["basis"] == "evidence_coverage"


def test_wellness_specificity_is_categorical_not_numeric():
    _, prescription = _prescribe(
        v21_assessment(dimensions={"tension_worry": 25})
    )
    assert prescription["recommendation_specificity"] == "wellness"


# --- Blocker 4: candidate_blend 无有效候选不得回退宫调 ---

def test_candidate_tone_weights_does_not_fabricate_gong_fallback():
    assert _candidate_tone_weights([]) == {}
    assert _candidate_tone_weights([{"id": "not-a-syndrome", "score": 50}]) == {}


def test_select_prescription_mode_ignores_invalid_candidates():
    diagnosis = {
        "abstained": False,
        "primary_tendency": {"id": "syd_001", "score": 85.0},
        "candidate_tendencies": [
            {"id": "syd_001", "score": 85.0},
            {"id": "not-a-syndrome", "score": 80.0},
        ],
    }
    assessment = v21_assessment(
        dimensions={"tension_worry": 100, "irritability_anger": 75}
    )
    assert select_prescription_mode(diagnosis, assessment) == "syndrome_based"


# --- 额外一致性：四个模式都真实到达 Music Agent ---

def test_all_four_modes_reach_music_matching():
    catalog = _catalog()

    # The three modes reachable from a real Diagnosis output.
    cases = [
        ({"tension_worry": 100, "irritability_anger": 75}, "syndrome_based"),
        ({"tension_worry": 75}, "emotion_based"),
        ({"tension_worry": 25}, "wellness"),
    ]
    for dimensions, expected_mode in cases:
        _, prescription = _prescribe(v21_assessment(dimensions=dimensions))
        assert prescription["prescription_mode"] == expected_mode
        assert prescription["music_feature"]["tone_id"]
        assert prescription["music_feature"]["bpm"]
        assert prescription["music_feature"]["instruments"]
        music = match_music_v2(prescription, catalog)
        assert music["status"] == "success", expected_mode
        assert music["stream_url"], expected_mode

    # candidate_blend is a compatibility path only (no explicit primary + multiple
    # valid candidates); it must still reach Music with a unified music_feature.
    blend = run_prescription_v2(
        _blend_diagnosis(),
        assessment=v21_assessment(dimensions={"tension_worry": 100}),
    )
    assert blend["prescription_mode"] == "candidate_blend"
    assert blend["music_feature"]["tone_id"]
    assert blend["music_feature"]["bpm"]
    assert blend["music_feature"]["instruments"]
    music = match_music_v2(blend, catalog)
    assert music["status"] == "success"
    assert music["stream_url"]


# --- PR #70 review (1): primary_tendency precedence ---

def test_explicit_primary_wins_over_multiple_candidates():
    diagnosis = {
        "status": "success",
        "abstained": False,
        "abstain_reason": None,
        "primary_tendency": {"id": "syd_001", "score": 85.0},
        "candidate_tendencies": [
            {"id": "syd_001", "score": 85.0},
            {"id": "syd_003", "score": 80.0},
        ],
    }
    assessment = v21_assessment(
        dimensions={"tension_worry": 100, "irritability_anger": 75}
    )

    assert select_prescription_mode(diagnosis, assessment) == "syndrome_based"
    prescription = run_prescription_v2(diagnosis, assessment=assessment)
    assert prescription["prescription_mode"] == "syndrome_based"


def test_candidate_blend_compat_path_without_primary():
    # candidate_blend is preserved for the (non-real) "no explicit primary but
    # multiple valid candidates" state, but never overrides an explicit primary.
    diagnosis = _blend_diagnosis()
    assessment = v21_assessment(dimensions={"tension_worry": 100})

    assert select_prescription_mode(diagnosis, assessment) == "candidate_blend"
    prescription = run_prescription_v2(diagnosis, assessment=assessment)
    assert prescription["prescription_mode"] == "candidate_blend"


# --- PR #70 review (2): candidate_blend safety ---

def test_two_valid_syndromes_zero_score_do_not_blend():
    diagnosis = {
        "status": "success",
        "abstained": False,
        "abstain_reason": None,
        "primary_tendency": None,
        "candidate_tendencies": [
            {"id": "syd_001", "score": 0},
            {"id": "syd_003", "score": 0},
        ],
    }
    assessment = v21_assessment(dimensions={"tension_worry": 75})

    assert select_prescription_mode(diagnosis, assessment) != "candidate_blend"
    prescription = run_prescription_v2(diagnosis, assessment=assessment)
    assert prescription["prescription_mode"] != "candidate_blend"
    assert prescription["generation_mode"] == "matched"


def test_candidate_missing_score_does_not_blend():
    diagnosis = {
        "status": "success",
        "abstained": False,
        "abstain_reason": None,
        "primary_tendency": None,
        "candidate_tendencies": [
            {"id": "syd_001"},
            {"id": "syd_003"},
        ],
    }
    assessment = v21_assessment(dimensions={"tension_worry": 75})

    assert select_prescription_mode(diagnosis, assessment) != "candidate_blend"
    assert (
        run_prescription_v2(diagnosis, assessment=assessment)["prescription_mode"]
        != "candidate_blend"
    )


def test_candidate_invalid_score_does_not_blend():
    diagnosis = {
        "status": "success",
        "abstained": False,
        "abstain_reason": None,
        "primary_tendency": None,
        "candidate_tendencies": [
            {"id": "syd_001", "score": "high"},
            {"id": "syd_003", "score": None},
        ],
    }
    assessment = v21_assessment(dimensions={"tension_worry": 75})

    assert select_prescription_mode(diagnosis, assessment) != "candidate_blend"
    assert (
        run_prescription_v2(diagnosis, assessment=assessment)["prescription_mode"]
        != "candidate_blend"
    )


def test_empty_weights_do_not_raise_stop_iteration():
    # Zero-score candidates produce empty tone weights; the prescription path
    # must degrade gracefully instead of crashing on next(iter({})).
    diagnosis = {
        "status": "success",
        "abstained": False,
        "abstain_reason": None,
        "primary_tendency": None,
        "candidate_tendencies": [
            {"id": "syd_001", "score": 0},
            {"id": "syd_003", "score": 0},
        ],
    }

    assert _candidate_tone_weights(_valid_candidates(diagnosis["candidate_tendencies"])) == {}
    prescription = run_prescription_v2(
        diagnosis, assessment=v21_assessment(dimensions={"tension_worry": 75})
    )
    assert prescription["generation_mode"] == "matched"
    assert prescription["prescription_mode"] == "emotion_based"


def test_multiple_positive_score_candidates_blend_pass():
    # Normal case: multiple positive-score candidates still reach candidate_blend.
    prescription = run_prescription_v2(
        _blend_diagnosis(),
        assessment=v21_assessment(dimensions={"tension_worry": 100}),
    )
    assert prescription["prescription_mode"] == "candidate_blend"
    assert set(prescription["tone_weights"]) == {"jiao", "zhi"}
    assert prescription["music_feature"]["tone_id"] == "jiao"
    assert prescription["generation_mode"] == "matched"
