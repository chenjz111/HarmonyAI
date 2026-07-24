from backend.ai_engine.assessment_demo import run_demo as run_assessment_demo
from backend.ai_engine.diagnosis_demo import run_demo as run_diagnosis_demo
from backend.ai_engine.feedback_demo import run_demo as run_feedback_demo
from backend.ai_engine.prescription_demo import run_demo as run_prescription_demo


def test_assessment_demo_returns_emotion_profile():
    assert "emotion_profile" in run_assessment_demo()["output"]


def test_diagnosis_demo_returns_mvp_syndrome():
    assert run_diagnosis_demo()["output"]["syndrome_diagnosis"]["primary"]["syndrome_id"] == "syd_001"


def test_prescription_demo_returns_evidence_and_prompt():
    result = run_prescription_demo()
    assert result["output"]["prompt_template"]["template_id"] == "CN_V1"
    assert "evidence" in result["output"]


def test_feedback_demo_returns_persisted_decision():
    assert run_feedback_demo()["output"]["decision"]["action"] == "continue"
