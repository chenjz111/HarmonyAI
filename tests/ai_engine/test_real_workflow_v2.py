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


class ExplodingRepository:
    def __getattribute__(self, name):
        raise AssertionError(
            f"repository must not be accessed without feedback: {name}"
        )


def questionnaire_answers(*, safety_flags=None):
    answers = {
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
    return {
        "schema_version": "questionnaire_v2.0",
        "time_window_days": 7,
        "answers": [
            {"question_id": question_id, "value": value}
            for question_id, value in answers.items()
        ],
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
            "music_id": "music-jiao-01",
            "title": "Jiao Calm",
            "stream_url": "local://music/jiao-calm.mp3",
            "duration_seconds": 900,
            "source_type": "matched",
            "tone_id": "jiao",
            "bpm": 68,
            "instruments": ["guzheng", "guqin"],
        }
    ]


def feedback_payload():
    return {
        "schema_version": "feedback_v2.0",
        "session_id": "session-v2-001",
        "prescription_id": "prescription-v2-001",
        "music_id": "music-jiao-01",
        "pre_state": {
            "tension": 8,
            "body_tension": 7,
            "mental_fatigue": 6,
            "goal": "relax",
        },
        "post_state": {
            "tension": 3,
            "body_tension": 4,
            "mental_fatigue": 4,
            "change_label": "much_better",
        },
        "experience": {
            "overall_rating": 5,
            "relaxation_rating": 5,
            "music_match_rating": 4,
            "continue_use": "yes",
            "favorite": True,
            "disliked_features": [],
            "disliked_instruments": [],
            "comment": "Calm and focused.",
        },
    }


@pytest.mark.parametrize(
    ("document_text", "narrative_text", "analysis_mode"),
    [
        (None, None, "questionnaire_only"),
        ("Sleep is light.", None, "document_questionnaire"),
        (None, "Work pressure is high.", "narrative_questionnaire"),
        ("Sleep is light.", "Work pressure is high.", "document_narrative_questionnaire"),
    ],
)
def test_v2_workflow_runs_all_confirmed_source_combinations_offline(
    document_text,
    narrative_text,
    analysis_mode,
):
    from backend.ai_engine.real_workflow import run_real_workflow_v2

    result = run_real_workflow_v2(
        user_id="user-v2-001",
        session_id="session-v2-001",
        questionnaire_answers=questionnaire_answers(),
        document_id="document-v2-001" if document_text else None,
        document_text=document_text,
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
    assert result["music"]["music_id"] == "music-jiao-01"
    assert result["degradations"]["assessment"] == {
        "active": False,
        "reason_codes": [],
    }


def test_v2_workflow_stops_after_safety_gate():
    from backend.ai_engine.real_workflow import run_real_workflow_v2

    result = run_real_workflow_v2(
        user_id="user-v2-001",
        session_id="session-v2-001",
        questionnaire_answers=questionnaire_answers(safety_flags=["self_harm_thoughts"]),
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
        questionnaire_answers=questionnaire_answers(),
        assessment_confirmed=False,
        llm=FixedJsonLLM(assessment_model_response(), diagnosis_model_response()),
        music_catalog=local_catalog(),
    )

    assert result["confirmation"] == {"status": "needs_confirmation"}
    assert result["agent_statuses"]["diagnosis"] == "not_run"
    assert result["agent_statuses"]["prescription"] == "not_run"
    assert result["agent_statuses"]["music"] == "not_run"


def test_v2_workflow_rejects_non_boolean_confirmation():
    from backend.ai_engine.real_workflow import run_real_workflow_v2

    with pytest.raises(TypeError, match="assessment_confirmed"):
        run_real_workflow_v2(
            user_id="user-v2-001",
            session_id="session-v2-001",
            questionnaire_answers=questionnaire_answers(),
            assessment_confirmed="false",
        )


def test_v2_workflow_exposes_qwen_resolution_degradation(monkeypatch):
    from backend.ai_engine.real_workflow import run_real_workflow_v2

    monkeypatch.setattr(
        "backend.ai_engine.assessment_v2.qwen_provider_from_env",
        lambda: None,
    )

    result = run_real_workflow_v2(
        user_id="user-v2-001",
        session_id="session-v2-001",
        questionnaire_answers=questionnaire_answers(),
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

    result = run_real_workflow_v2(
        user_id="user-v2-001",
        session_id="session-v2-001",
        questionnaire_answers=questionnaire_answers(),
        assessment_confirmed=True,
        llm=FixedJsonLLM(assessment_model_response(), diagnosis_model_response()),
        music_catalog=local_catalog(),
        feedback_repository=ExplodingRepository(),
    )

    assert result["feedback"] == {"status": "not_submitted"}


def test_v2_workflow_submits_explicit_feedback_to_atomic_repository():
    from backend.ai_engine.real_workflow import run_real_workflow_v2

    repository = AtomicFeedbackRepository()

    result = run_real_workflow_v2(
        user_id="user-v2-001",
        session_id="session-v2-001",
        questionnaire_answers=questionnaire_answers(),
        assessment_confirmed=True,
        llm=FixedJsonLLM(assessment_model_response(), diagnosis_model_response()),
        music_catalog=local_catalog(),
        feedback_payload=feedback_payload(),
        feedback_repository=repository,
    )

    assert result["feedback"]["status"] == "success"
    feedback_id = result["feedback"]["feedback_id"]
    assert feedback_id.startswith("fb_")
    assert repository.save_once_calls == 1
    assert repository.records[feedback_id]["experience"]["overall_rating"] == 5


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("session_id", "another-session"),
        ("music_id", "another-music"),
    ],
)
def test_v2_workflow_rejects_feedback_for_another_result(field, value):
    from backend.ai_engine.real_workflow import run_real_workflow_v2

    payload = feedback_payload()
    payload[field] = value
    result = run_real_workflow_v2(
        user_id="user-v2-001",
        session_id="session-v2-001",
        questionnaire_answers=questionnaire_answers(),
        assessment_confirmed=True,
        llm=FixedJsonLLM(
            assessment_model_response(),
            diagnosis_model_response(),
        ),
        music_catalog=local_catalog(),
        feedback_payload=payload,
        feedback_repository=AtomicFeedbackRepository(),
    )

    assert result["feedback"] == {
        "status": "failed",
        "error_code": "INVALID_PAYLOAD",
        "field": field,
        "global_rule_update": False,
    }


def test_v2_workflow_rejects_non_mapping_feedback_payload():
    from backend.ai_engine.real_workflow import run_real_workflow_v2

    result = run_real_workflow_v2(
        user_id="user-v2-001",
        session_id="session-v2-001",
        questionnaire_answers=questionnaire_answers(),
        assessment_confirmed=True,
        llm=FixedJsonLLM(
            assessment_model_response(),
            diagnosis_model_response(),
        ),
        music_catalog=local_catalog(),
        feedback_payload="invalid",
        feedback_repository=AtomicFeedbackRepository(),
    )

    assert result["feedback"] == {
        "status": "failed",
        "error_code": "INVALID_PAYLOAD",
        "field": "payload",
        "global_rule_update": False,
    }


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
            "questionnaire_answers": questionnaire_answers(),
            "document_id": None,
            "document_text": None,
            "narrative_text": None,
            "assessment_confirmed": True,
            "feedback_payload": None,
        }
    )

    assert result["result_id"] == "v2-result-direct"
    assert result["agent_statuses"]["music"] == "success"
