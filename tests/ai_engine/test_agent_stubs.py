from backend.ai_engine.agent_stubs import (
    assessment_stub,
    diagnosis_stub,
    feedback_stub,
    generation_stub,
    prescription_stub,
)


def test_assessment_stub_returns_universal_agent_envelope():
    result = assessment_stub(
        {
            "run_id": "run-1",
            "session_id": "session-1",
            "user_id": "user-1",
            "emotion_scores": {"anxiety": 82},
        }
    )["assessment"]

    required = {
        "agent_id",
        "agent_version",
        "agent_name",
        "agent_layer",
        "run_id",
        "session_id",
        "user_id",
        "status",
        "confidence",
        "reason",
        "warnings",
        "input",
        "output",
        "processing_time_ms",
        "timestamp",
        "retry_count",
    }
    assert required.issubset(result)
    assert result["agent_id"] == "evaluation_agent"
    assert result["status"] == "success"


def test_stub_nodes_produce_schema_shaped_handoff_data():
    state = {
        "run_id": "run-1",
        "session_id": "session-1",
        "user_id": "user-1",
        "emotion_scores": {"anxiety": 82},
    }
    state.update(assessment_stub(state))
    state.update(diagnosis_stub(state))
    state.update(prescription_stub(state))
    state.update(generation_stub(state))
    state.update(feedback_stub(state))

    assert state["diagnosis"]["output"]["syndrome_diagnosis"]["primary"]["name"] == "肝郁化火"
    assert state["prescription"]["output"]["music_feature"]["tone_id"] == "jiao"
    assert state["generation"]["output"]["audio"]["url"].endswith(".wav")
    assert state["feedback"]["output"]["decision"]["action"] == "continue"
