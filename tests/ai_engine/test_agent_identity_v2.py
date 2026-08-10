"""Canonical Agent IDs must be present on every V2 outcome."""

from backend.ai_engine.diagnosis_v2 import run_diagnosis_v2
from backend.ai_engine.feedback_v2 import submit_feedback_v2
from backend.ai_engine.prescription_v2 import run_prescription_v2
from tests.ai_engine.test_diagnosis_v2 import assessment
from tests.ai_engine.test_feedback_v2 import (
    AtomicFeedbackRepository,
    FailingFeedbackRepository,
    feedback_payload,
)


def test_diagnosis_success_and_safety_block_use_canonical_agent_id():
    success = run_diagnosis_v2(assessment())
    blocked = run_diagnosis_v2(
        assessment(status="blocked_safety")
    )

    assert success["agent_id"] == "diagnosis_agent"
    assert blocked["agent_id"] == "diagnosis_agent"


def test_prescription_success_and_withheld_use_canonical_agent_id():
    diagnosis = run_diagnosis_v2(assessment())
    success = run_prescription_v2(diagnosis)
    withheld = run_prescription_v2({"status": "blocked_safety"})

    assert success["agent_id"] == "prescription_agent"
    assert withheld["agent_id"] == "prescription_agent"


def test_feedback_success_validation_and_storage_failure_use_canonical_agent_id():
    success = submit_feedback_v2(
        feedback_payload(),
        AtomicFeedbackRepository(),
    )
    invalid = submit_feedback_v2({}, AtomicFeedbackRepository())
    failed = submit_feedback_v2(
        feedback_payload(),
        FailingFeedbackRepository(),
    )

    assert success["agent_id"] == "feedback_agent"
    assert invalid["agent_id"] == "feedback_agent"
    assert failed["agent_id"] == "feedback_agent"
