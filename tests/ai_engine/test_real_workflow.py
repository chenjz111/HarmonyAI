from backend.ai_engine.feedback_store import SQLiteFeedbackStore
from backend.ai_engine.real_workflow import run_real_workflow


def test_real_workflow_runs_offline_and_persists_feedback(tmp_path):
    store = SQLiteFeedbackStore(tmp_path / "feedback.sqlite3")

    result = run_real_workflow(
        user_id="u-1",
        session_id="s-1",
        questionnaire={"sleep": "最近睡不好"},
        feedback_store=store,
    )

    assert result["assessment"]["status"] in {"success", "degraded"}
    assert result["diagnosis"]["output"]["syndrome_diagnosis"]["primary"]["syndrome_id"] == "syd_001"
    assert result["prescription"]["output"]["prompt_template"]["template_id"] == "CN_V1"
    assert result["generation"]["output"]["audio"]["url"].startswith("local://")
    assert result["feedback"]["status"] == "success"
    assert store.count() == 1


def test_real_workflow_stops_before_generation_on_low_confidence(tmp_path):
    store = SQLiteFeedbackStore(tmp_path / "feedback.sqlite3")

    result = run_real_workflow(
        user_id="u-1",
        session_id="s-1",
        questionnaire={},
        feedback_store=store,
    )

    assert result["assessment"]["confidence"] <= 0.3
    assert "prescription" not in result
    assert "generation" not in result
    assert "low_confidence" in result
