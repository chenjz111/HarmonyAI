from backend.ai_engine.langgraph_workflow import run_stub_workflow


def test_normal_input_runs_all_five_agents_in_order():
    result = run_stub_workflow(
        user_id="user-1",
        session_id="session-1",
        emotion_scores={"anxiety": 82},
    )

    keys = ("assessment", "diagnosis", "prescription", "generation", "feedback")
    assert [key for key in keys if key in result] == list(keys)
    assert result["feedback"]["status"] == "success"


def test_empty_input_routes_to_low_confidence_handler():
    result = run_stub_workflow(user_id="user-1", session_id="session-1", emotion_scores={})

    assert result["assessment"]["status"] == "degraded"
    assert result["low_confidence"]["status"] == "success"
    assert "prescription" not in result
    assert "generation" not in result
