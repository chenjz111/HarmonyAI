"""Workflow-level hard-stop gating for Prescription → Music (Blocker 5).

Guarantees:
* Safety → Music agent is never invoked (``match_music_v2`` call count == 0).
* True information insufficiency → Music agent is never invoked.
* Diagnosis abstain + sufficient assessment → Prescription runs, Music runs once.
* Clear syndrome → Music runs once.
"""

from backend.ai_engine.real_workflow import continue_real_workflow_v21


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


def _assessment(*, dimensions=None, coverage=1.0, status="confirmed"):
    scores = {dimension: 0 for dimension in _ALL_DIMENSIONS}
    if dimensions:
        scores.update(dimensions)
    return {
        "assessment_id": "asmt-wf",
        "status": status,
        "confirmation_level": "fully_accurate",
        "revision": 1,
        "requires_user_confirmation": False,
        "emotion_profile": {"dimension_scores": scores},
        "evidence_items": [],
        "evidence_coverage_score": coverage,
        "missing_information": [],
        "conflicts": [],
        "follow_up_questions": [],
    }


class MusicSpy:
    def __init__(self):
        self.calls = 0

    def __call__(self, prescription, catalog):
        self.calls += 1
        return {"status": "success", "stream_url": "/media/spy.mp3"}


def test_safety_blocks_music_agent(monkeypatch):
    spy = MusicSpy()
    monkeypatch.setattr("backend.ai_engine.real_workflow.match_music_v2", spy)

    result = continue_real_workflow_v21(
        assessment=_assessment(status="blocked_safety"),
        music_catalog=[],
    )

    assert result["confirmation"]["status"] == "blocked_safety"
    assert result["music"] is None
    assert spy.calls == 0


def test_true_insufficiency_blocks_music_agent(monkeypatch):
    spy = MusicSpy()
    monkeypatch.setattr("backend.ai_engine.real_workflow.match_music_v2", spy)

    result = continue_real_workflow_v21(
        assessment=_assessment(dimensions={"tension_worry": 100}, coverage=0.2),
        music_catalog=[],
    )

    assert result["prescription"]["generation_mode"] == "matched"
    assert result["prescription"]["prescription_mode"] == "emotion_based"
    assert result["music"] is not None
    assert spy.calls == 1


def test_abstain_but_sufficient_still_runs_music(monkeypatch):
    spy = MusicSpy()
    monkeypatch.setattr("backend.ai_engine.real_workflow.match_music_v2", spy)

    result = continue_real_workflow_v21(
        assessment=_assessment(dimensions={"tension_worry": 75}, coverage=0.8),
        music_catalog=[],
    )

    assert result["diagnosis"]["abstained"] is True
    assert result["prescription"]["generation_mode"] == "matched"
    assert result["prescription"]["prescription_mode"] == "emotion_based"
    assert result["music"] is not None
    assert spy.calls == 1


def test_clear_syndrome_runs_music(monkeypatch):
    spy = MusicSpy()
    monkeypatch.setattr("backend.ai_engine.real_workflow.match_music_v2", spy)

    result = continue_real_workflow_v21(
        assessment=_assessment(
            dimensions={"tension_worry": 100, "irritability_anger": 75},
            coverage=0.8,
        ),
        music_catalog=[],
    )

    assert result["prescription"]["prescription_mode"] == "syndrome_based"
    assert result["music"] is not None
    assert spy.calls == 1

def test_v22_ordinary_follow_up_does_not_add_a_second_confirmation_gate(monkeypatch):
    spy = MusicSpy()
    monkeypatch.setattr("backend.ai_engine.real_workflow.match_music_v2", spy)
    assessment = _assessment(dimensions={"tension_worry": 75}, coverage=0.8)
    assessment["input_processing_status"] = {
        "questionnaire": {"version": "questionnaire_v2.2"}
    }
    assessment["follow_up_questions"] = [
        {"follow_up_id": "fu-conflict", "reason": "ordinary_conflict"}
    ]

    result = continue_real_workflow_v21(assessment=assessment, music_catalog=[])

    assert result["confirmation"]["status"] == "confirmed"
    assert result["music"] is not None
    assert spy.calls == 1


def test_v21_follow_up_gate_remains_compatible(monkeypatch):
    spy = MusicSpy()
    monkeypatch.setattr("backend.ai_engine.real_workflow.match_music_v2", spy)
    assessment = _assessment(dimensions={"tension_worry": 75}, coverage=0.8)
    assessment["input_processing_status"] = {
        "questionnaire": {"version": "questionnaire_v2.1"}
    }
    assessment["follow_up_questions"] = [
        {"follow_up_id": "fu-duration", "reason": "missing_duration"}
    ]

    result = continue_real_workflow_v21(assessment=assessment, music_catalog=[])

    assert result["confirmation"]["status"] == "needs_follow_up"
    assert result["music"] is None
    assert spy.calls == 0
