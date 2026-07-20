from backend.ai_engine.agent_stubs import assessment_stub


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
