from pathlib import Path

from backend.ai_engine.models import WorkflowInput
from backend.ai_engine.prompt_engine import PromptEngine
from backend.ai_engine.workflow import run_workflow


def test_workflow_maps_highest_emotion_to_structured_prescription():
    result = run_workflow(
        WorkflowInput("u1", "s1", {"anxiety": 82, "anger": 60}),
        PromptEngine(Path("prompt/v1")),
    )

    assert result.evaluation.agent_id == "evaluation_agent"
    assert result.prescription.agent_id == "prescription_agent"
    assert result.prescription.tone_id == "jiao"
    assert result.prescription.bpm == 68
    assert "角调式" in result.prescription.prompt.text


def test_empty_emotions_use_fallback_and_review_warning():
    result = run_workflow(
        WorkflowInput("u1", "s1", {}),
        PromptEngine(Path("prompt/v1")),
    )

    assert result.evaluation.confidence < 0.4
    assert result.evaluation.warnings["recommend_professional"] is True
    assert any("fallback" in reason for reason in result.evaluation.reason)
