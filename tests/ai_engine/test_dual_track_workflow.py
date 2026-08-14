from backend.ai_engine.real_workflow import continue_real_workflow_v21


DIMENSIONS = {
    "tension_worry": 75,
    "overthinking": 0,
    "irritability_anger": 0,
    "fear_unease": 0,
    "low_mood": 0,
    "interest_loss": 0,
    "calm_wellbeing": 0,
    "emotional_recovery": 0,
    "sleep_disturbance": 0,
    "unrefreshing_sleep": 0,
    "low_energy": 0,
    "appetite_change": 0,
    "daily_impact": 0,
}


def _assessment(*, safety_status="clear", coverage=0.8, dimensions=None):
    return {
        "assessment_id": "dual-track-a1",
        "revision": 2,
        "status": "confirmed",
        "assessment_status": "completed",
        "confirmation_status": "fully_accurate",
        "confirmation_level": "fully_accurate",
        "safety_status": safety_status,
        "requires_user_confirmation": False,
        "requires_safety_verification": safety_status == "needs_verification",
        "personalized_prescription_allowed": safety_status in {"clear", "resolved"},
        "comfort_audio_allowed": safety_status == "confirmed_mental_health_risk",
        "emotion_profile": {"dimension_scores": dimensions if dimensions is not None else DIMENSIONS},
        "evidence_items": [{"evidence_id": "ev-q1", "source_type": "questionnaire"}],
        "evidence_coverage_score": coverage,
        "missing_information": [],
        "conflicts": [],
        "follow_up_questions": [],
    }


def test_needs_verification_routes_to_verification_without_running_agents():
    assessment = _assessment(safety_status="needs_verification")
    assessment["status"] = "blocked_safety"

    result = continue_real_workflow_v21(assessment=assessment)

    assert result["confirmation"]["status"] == "needs_safety_verification"
    assert result["diagnosis"] is None
    assert result["prescription"] is None
    assert result["music"] is None


def test_confirmed_mental_risk_routes_to_support_without_personalized_agents():
    assessment = _assessment(safety_status="confirmed_mental_health_risk")
    assessment["status"] = "blocked_safety"

    result = continue_real_workflow_v21(assessment=assessment)

    assert result["confirmation"]["status"] == "safety_support"
    assert result["assessment"]["comfort_audio_allowed"] is True
    assert result["prescription"] is None
    assert result["music"] is None


def test_confirmed_acute_risk_routes_to_emergency_without_comfort_audio():
    assessment = _assessment(safety_status="confirmed_acute_physical_risk")
    assessment["status"] = "blocked_safety"

    result = continue_real_workflow_v21(assessment=assessment)

    assert result["confirmation"]["status"] == "safety_support"
    assert result["assessment"]["comfort_audio_allowed"] is False
    assert result["prescription"] is None
    assert result["music"] is None


def test_low_coverage_clear_user_gets_conservative_music_not_dead_end(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "backend.ai_engine.real_workflow.match_music_v2",
        lambda prescription, catalog: calls.append(prescription) or {"status": "success", "stream_url": "/static/music/test.wav"},
    )

    result = continue_real_workflow_v21(assessment=_assessment(coverage=0.2))

    assert result["prescription"]["generation_mode"] == "matched"
    assert result["prescription"]["prescription_mode"] == "emotion_based"
    assert result["prescription"]["recommendation_specificity"] == "conservative"
    assert result["music"] is not None
    assert len(calls) == 1


def test_no_meaningful_dimensions_gets_generic_wellness_fallback(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "backend.ai_engine.real_workflow.match_music_v2",
        lambda prescription, catalog: calls.append(prescription) or {"status": "success", "stream_url": "/static/music/test.wav"},
    )

    result = continue_real_workflow_v21(
        assessment=_assessment(coverage=0.0, dimensions={}),
    )

    assert result["prescription"]["generation_mode"] == "matched"
    assert result["prescription"]["prescription_mode"] == "wellness"
    assert result["prescription"]["recommendation_specificity"] == "wellness"
    assert len(calls) == 1

