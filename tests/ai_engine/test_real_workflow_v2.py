import pytest


class FixedJsonLLM:
    def __init__(self, *responses):
        self._responses = list(responses)

    def complete_json(self, system_prompt, user_prompt):
        del system_prompt, user_prompt
        return self._responses.pop(0)


class AtomicFeedbackRepository:
    def __init__(self):
        self.records = {}
        self.save_once_calls = 0

    def save_once(self, record, preference_patch):
        del preference_patch
        self.save_once_calls += 1
        if record["feedback_id"] in self.records:
            return False
        self.records[record["feedback_id"]] = record
        return True


def questionnaire_answers(*, safety_flags=None):
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
        "q12_physical_safety": ["none"] if safety_flags is None else safety_flags,
    }


def assessment_model_response():
    return {
        "state_summary": {"summary": "Stress is elevated."},
        "context": {"triggers": ["workload"], "physical_signals": []},
        "evidence": [],
        "conflicts": [],
    }


def diagnosis_model_response():
    return {"tendency_id": "syd_001", "confidence": 0.9}


def local_catalog():
    return [
        {
            "track_id": "track-jiao-01",
            "title": "Jiao Calm",
            "audio_url": "local://music/jiao-calm.mp3",
            "duration": 900,
            "source": "local_catalog",
            "tone_id": "jiao",
            "bpm": 68,
            "instruments": ["guzheng", "guqin"],
        }
    ]


def feedback_payload():
    return {
        "feedback_id": "feedback-v2-001",
        "session_id": "session-v2-001",
        "user_id": "user-v2-001",
        "before": {"tension": 8, "body_tension": 7, "fatigue": 6},
        "after": {"tension": 3, "body_tension": 4, "fatigue": 4},
        "rating": 5,
        "relaxation": 9,
        "match": 8,
        "comment": "Calm and focused.",
        "is_favorite": True,
        "continue_listening": True,
        "disliked_features": ["fast tempo"],
        "track_id": "track-jiao-01",
    }


@pytest.mark.parametrize(
    ("document", "narrative_text", "analysis_mode"),
    [
        (None, None, "questionnaire_only"),
        ({"ocr_status": "confirmed", "confirmed_text": "Sleep is light."}, None, "document_questionnaire"),
        (None, "Work pressure is high.", "narrative_questionnaire"),
        ({"ocr_status": "confirmed", "confirmed_text": "Sleep is light."}, "Work pressure is high.", "document_text_questionnaire"),
    ],
)
def test_v2_workflow_runs_all_confirmed_source_combinations_offline(
    document,
    narrative_text,
    analysis_mode,
):
    from backend.ai_engine.real_workflow import run_real_workflow_v2

    result = run_real_workflow_v2(
        user_id="user-v2-001",
        session_id="session-v2-001",
        questionnaire=questionnaire_answers(),
        document=document,
        narrative_text=narrative_text,
        assessment_confirmed=True,
        llm=FixedJsonLLM(assessment_model_response(), diagnosis_model_response()),
        music_catalog=local_catalog(),
    )

    assert result["session_id"] == "session-v2-001"
    assert result["result_id"].startswith("v2-result-")
    assert result["assessment"]["analysis_mode"] == analysis_mode
    assert result["agent_statuses"] == {
        "assessment": "success",
        "confirmation": "confirmed",
        "diagnosis": "success",
        "prescription": "success",
        "music": "success",
        "feedback": "not_submitted",
    }
    assert result["music"]["track_id"] == "track-jiao-01"
    assert result["degradations"]["assessment"] == {
        "active": False,
        "reason_codes": [],
    }


def test_v2_workflow_stops_after_safety_gate():
    from backend.ai_engine.real_workflow import run_real_workflow_v2

    result = run_real_workflow_v2(
        user_id="user-v2-001",
        session_id="session-v2-001",
        questionnaire=questionnaire_answers(safety_flags=["self_harm_thoughts"]),
        assessment_confirmed=True,
        llm=FixedJsonLLM(assessment_model_response(), diagnosis_model_response()),
        music_catalog=local_catalog(),
    )

    assert result["assessment"]["status"] == "blocked_safety"
    assert result["confirmation"]["status"] == "blocked_safety"
    assert result["agent_statuses"]["diagnosis"] == "not_run"
    assert result["agent_statuses"]["prescription"] == "not_run"
    assert result["agent_statuses"]["music"] == "not_run"


def test_v2_workflow_requires_explicit_assessment_confirmation():
    from backend.ai_engine.real_workflow import run_real_workflow_v2

    result = run_real_workflow_v2(
        user_id="user-v2-001",
        session_id="session-v2-001",
        questionnaire=questionnaire_answers(),
        assessment_confirmed=False,
        llm=FixedJsonLLM(assessment_model_response(), diagnosis_model_response()),
        music_catalog=local_catalog(),
    )

    assert result["confirmation"] == {"status": "needs_confirmation"}
    assert result["agent_statuses"]["diagnosis"] == "not_run"
    assert result["agent_statuses"]["prescription"] == "not_run"
    assert result["agent_statuses"]["music"] == "not_run"


def test_v2_workflow_exposes_qwen_resolution_degradation(monkeypatch):
    from backend.ai_engine.real_workflow import run_real_workflow_v2

    monkeypatch.setattr(
        "backend.ai_engine.assessment_v2.qwen_provider_from_env",
        lambda: None,
    )

    result = run_real_workflow_v2(
        user_id="user-v2-001",
        session_id="session-v2-001",
        questionnaire=questionnaire_answers(),
        assessment_confirmed=True,
        music_catalog=local_catalog(),
    )

    assert result["agent_statuses"]["assessment"] == "degraded"
    assert result["degradations"]["assessment"]["reason_codes"] == [
        "LLM_NOT_CONFIGURED"
    ]
    assert result["agent_statuses"]["diagnosis"] == "degraded"
    assert result["agent_statuses"]["music"] == "degraded"


def test_v2_workflow_does_not_touch_repository_without_feedback_payload():
    from backend.ai_engine.real_workflow import run_real_workflow_v2

    repository = AtomicFeedbackRepository()

    result = run_real_workflow_v2(
        user_id="user-v2-001",
        session_id="session-v2-001",
        questionnaire=questionnaire_answers(),
        assessment_confirmed=True,
        llm=FixedJsonLLM(assessment_model_response(), diagnosis_model_response()),
        music_catalog=local_catalog(),
        feedback_repository=repository,
    )

    assert result["feedback"] == {"status": "not_submitted"}
    assert repository.save_once_calls == 0


def test_v2_workflow_submits_explicit_feedback_to_atomic_repository():
    from backend.ai_engine.real_workflow import run_real_workflow_v2

    repository = AtomicFeedbackRepository()

    result = run_real_workflow_v2(
        user_id="user-v2-001",
        session_id="session-v2-001",
        questionnaire=questionnaire_answers(),
        assessment_confirmed=True,
        llm=FixedJsonLLM(assessment_model_response(), diagnosis_model_response()),
        music_catalog=local_catalog(),
        feedback_payload=feedback_payload(),
        feedback_repository=repository,
    )

    assert result["feedback"]["status"] == "success"
    assert result["feedback"]["feedback_id"] == "feedback-v2-001"
    assert repository.save_once_calls == 1
    assert repository.records["feedback-v2-001"]["rating"] == 5


def test_v2_graph_entry_returns_the_same_finalized_contract():
    from backend.ai_engine.real_workflow import build_real_graph_v2

    graph = build_real_graph_v2(
        llm=FixedJsonLLM(assessment_model_response(), diagnosis_model_response()),
        knowledge_store=None,
        music_catalog=local_catalog(),
        feedback_repository=None,
    )

    result = graph.invoke(
        {
            "result_id": "v2-result-direct",
            "session_id": "session-v2-001",
            "user_id": "user-v2-001",
            "questionnaire": questionnaire_answers(),
            "document": None,
            "narrative_text": None,
            "assessment_confirmed": True,
            "feedback_payload": None,
        }
    )

    assert result["result_id"] == "v2-result-direct"
    assert result["agent_statuses"]["music"] == "success"
