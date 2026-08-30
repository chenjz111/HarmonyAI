"""Owner Flow Amendment 001 §5/§6 — v3.1 discriminator schema tests.

These tests pin the contract-visible boundaries: music goals are rejected on
new discriminators (never defaulted), understanding/questionnaire refs follow
the with/without-document rules, and deferred_v3 Safety fields are null.
"""

import pytest
from pydantic import ValidationError

from backend.app.schemas.v3.assessment import (
    AssessmentRefV31,
    AssessmentV31Request,
    AssessmentV31Response,
)
from backend.app.schemas.v3.common import OrganProfile, SafetyStatus
from backend.app.schemas.v3.diagnosis import DiagnosisV31Input
from backend.app.schemas.v3.prescription import PrescriptionV31Request
from backend.app.schemas.v3.understanding import (
    UnderstandingV31ConfirmationRequest,
    UnderstandingV31Response,
)


def _questionnaire_ref():
    return {
        "questionnaire_submission_id": "qsub_1",
        "schema_id": "questionnaire_v3",
        "schema_version": "3.0.0",
        "manifest_version": "medical_v3.0",
        "content_checksum": "sha256:approved-manifest-checksum",
    }


def test_assessment_v31_rejects_user_goal_via_extra_forbid():
    with pytest.raises(ValidationError) as exc:
        AssessmentV31Request.model_validate(
            {
                "schema_version": "assessment_v3.1",
                "session_id": "sess_1",
                "expected_input_revision": 1,
                "understanding_ref": {
                    "understanding_id": "und_1",
                    "revision": 2,
                },
                "user_goal": {
                    "primary_goal": "sleep",
                    "secondary_goal": "relaxation",
                    "custom_goal_text": None,
                },
            }
        )
    assert exc.value.errors()[0]["type"] == "extra_forbidden"


def test_assessment_v31_without_document_requires_questionnaire():
    with pytest.raises(ValidationError):
        AssessmentV31Request.model_validate(
            {
                "schema_version": "assessment_v3.1",
                "session_id": "sess_1",
                "expected_input_revision": 1,
                "understanding_ref": None,
                "questionnaire_ref": None,
            }
        )

    valid = AssessmentV31Request.model_validate(
        {
            "schema_version": "assessment_v3.1",
            "session_id": "sess_1",
            "expected_input_revision": 3,
            "understanding_ref": None,
            "questionnaire_ref": _questionnaire_ref(),
        }
    )
    assert valid.understanding_ref is None
    assert valid.questionnaire_ref is not None
    assert valid.expected_input_revision == 3


def test_assessment_v31_with_document_allows_optional_questionnaire():
    valid = AssessmentV31Request.model_validate(
        {
            "schema_version": "assessment_v3.1",
            "session_id": "sess_1",
            "expected_input_revision": 4,
            "understanding_ref": {"understanding_id": "und_1", "revision": 2},
            "questionnaire_ref": None,
        }
    )
    assert valid.understanding_ref.revision == 2


def test_assessment_v31_accepts_narrative_understanding_plus_questionnaire():
    """Narrative facts (own understanding) plus a complete questionnaire can
    feed Agent 1 together; both refs are accepted by the v3.1 input."""
    valid = AssessmentV31Request.model_validate(
        {
            "schema_version": "assessment_v3.1",
            "session_id": "sess_1",
            "expected_input_revision": 5,
            "understanding_ref": {"understanding_id": "und_narrative", "revision": 1},
            "questionnaire_ref": _questionnaire_ref(),
        }
    )
    assert valid.understanding_ref.understanding_id == "und_narrative"
    assert valid.questionnaire_ref.questionnaire_submission_id == "qsub_1"


def test_assessment_v31_response_has_null_safety_and_no_goal_summary():
    base = {
        "schema_version": "assessment_v3.1",
        "agent_id": "assessment_agent",
        "assessment_id": "asmt_1",
        "revision": 1,
        "status": "needs_confirmation",
        "understanding_ref": None,
        "state_summary": "多源状态评估",
        "recent_context_summary": "",
        "organ_profile": {
            "status": "insufficient",
            "weights": None,
            "score_semantics": "relative_evidence_distribution",
        },
        "fact_evidence": [],
        "organ_evidence_links": [],
        "conflicts": [],
        "missing_information": [],
        "evidence_coverage": 0.5,
        "evidence_coverage_semantics": "confirmed_available_source_coverage",
        "source_diversity": 0,
        "requires_user_confirmation": True,
        "safety_status": None,
        "degradation": {"active": False, "reason_codes": []},
        "flow_contract_version": "v3-owner-flow-1",
        "input_revision": 3,
        "safety_policy": "deferred_v3",
        "safety_evaluation_status": "not_run",
        "presentation": {
            "title": "近期状态评估",
            "summary": "评估摘要",
            "body_summaries": [],
            "recent_context": "",
        },
    }
    response = AssessmentV31Response.model_validate(base)
    assert response.safety_status is None
    assert response.flow_contract_version == "v3-owner-flow-1"
    assert "goal_summary" not in response.presentation.model_dump()


def test_assessment_v31_response_rejects_goal_summary_presentation():
    with pytest.raises(ValidationError):
        AssessmentV31Response.model_validate(
            {
                "schema_version": "assessment_v3.1",
                "agent_id": "assessment_agent",
                "assessment_id": "asmt_1",
                "revision": 1,
                "status": "needs_confirmation",
                "understanding_ref": None,
                "state_summary": "多源状态评估",
                "recent_context_summary": "",
                "organ_profile": {
                    "status": "insufficient",
                    "weights": None,
                    "score_semantics": "relative_evidence_distribution",
                },
                "fact_evidence": [],
                "organ_evidence_links": [],
                "conflicts": [],
                "missing_information": [],
                "evidence_coverage": 0.5,
                "evidence_coverage_semantics": "confirmed_available_source_coverage",
                "source_diversity": 0,
                "requires_user_confirmation": True,
                "safety_status": None,
                "degradation": {"active": False, "reason_codes": []},
                "flow_contract_version": "v3-owner-flow-1",
                "input_revision": 3,
                "safety_policy": "deferred_v3",
                "safety_evaluation_status": "not_run",
                "presentation": {
                    "title": "近期状态评估",
                    "summary": "评估摘要",
                    "body_summaries": [],
                    "recent_context": "",
                    "goal_summary": "放松",
                },
            }
        )


def test_prescription_v31_rejects_user_goal():
    with pytest.raises(ValidationError) as exc:
        PrescriptionV31Request.model_validate(
            {
                "schema_version": "prescription_v3.1",
                "diagnosis_id": "diag_1",
                "user_goal": {
                    "primary_goal": "sleep",
                    "secondary_goal": None,
                    "custom_goal_text": None,
                },
            }
        )
    assert exc.value.errors()[0]["type"] == "extra_forbidden"

    valid = PrescriptionV31Request.model_validate(
        {
            "schema_version": "prescription_v3.1",
            "diagnosis_id": "diag_1",
            "preference_snapshot": None,
        }
    )
    assert valid.diagnosis_id == "diag_1"


def _organ_profile_available():
    return OrganProfile(
        status="available",
        weights={
            "liver": 0.2,
            "heart": 0.2,
            "spleen": 0.2,
            "lung": 0.2,
            "kidney": 0.2,
        },
        score_semantics="relative_evidence_distribution",
    )


def test_diagnosis_v31_replaces_legacy_safety_gate_with_policy():
    base = {
        "schema_version": "diagnosis_v3.1",
        "diagnosis_id": "diag_1",
        "assessment_ref": {
            "assessment_id": "asmt_1",
            "revision": 2,
            "confirmation_status": "confirmed",
            "flow_contract_version": "v3-owner-flow-1",
            "input_revision": 4,
            "safety_policy": "deferred_v3",
            "safety_status": None,
        },
        "organ_profile": _organ_profile_available().model_dump(),
        "fact_evidence": [],
        "organ_evidence_links": [],
        "conflicts": [],
        "missing_information": [],
    }
    valid = DiagnosisV31Input.model_validate(base)
    assert valid.assessment_ref.safety_policy == "deferred_v3"
    assert valid.assessment_ref.safety_status is None


def test_diagnosis_v31_rejects_legacy_clear_safety_ref():
    with pytest.raises(ValidationError):
        DiagnosisV31Input.model_validate(
            {
                "schema_version": "diagnosis_v3.1",
                "diagnosis_id": "diag_1",
                "assessment_ref": {
                    "assessment_id": "asmt_1",
                    "revision": 2,
                    "confirmation_status": "confirmed",
                    "flow_contract_version": "v3-owner-flow-1",
                    "input_revision": 4,
                    "safety_policy": "deferred_v3",
                    "safety_status": SafetyStatus.clear.value,
                },
                "organ_profile": _organ_profile_available().model_dump(),
                "fact_evidence": [],
                "organ_evidence_links": [],
                "conflicts": [],
                "missing_information": [],
            }
        )


def test_assessment_ref_v31_requires_null_safety():
    with pytest.raises(ValidationError):
        AssessmentRefV31.model_validate(
            {
                "assessment_id": "asmt_1",
                "revision": 1,
                "confirmation_status": "confirmed",
                "flow_contract_version": "v3-owner-flow-1",
                "input_revision": 1,
                "safety_policy": "deferred_v3",
                "safety_status": SafetyStatus.clear.value,
            }
        )


def test_understanding_v31_response_safety_is_null():
    response = UnderstandingV31Response.model_validate(
        {
            "schema_version": "understanding_v3.1",
            "understanding_id": "und_1",
            "revision": 1,
            "status": "needs_confirmation",
            "case_summary": None,
            "voice_transcripts": [],
            "normalized_facts": [],
            "source_statuses": [],
            "safety_status": None,
            "safety_signal_refs": [],
            "degradation": {"active": False, "reason_codes": []},
            "flow_contract_version": "v3-owner-flow-1",
            "safety_policy": "deferred_v3",
            "safety_evaluation_status": "not_run",
        }
    )
    assert response.safety_status is None
    assert response.safety_policy == "deferred_v3"


def test_v31_confirmation_full_edit_shape_rules():
    with pytest.raises(ValidationError):
        UnderstandingV31ConfirmationRequest.model_validate(
            {
                "schema_version": "understanding_v3.1",
                "expected_revision": 1,
                "expected_input_revision": 2,
                "decision": "confirm_with_changes",
                "edited_summary_text": "   ",
                "reprocess_requested": True,
            }
        )

    with pytest.raises(ValidationError):
        UnderstandingV31ConfirmationRequest.model_validate(
            {
                "schema_version": "understanding_v3.1",
                "expected_revision": 1,
                "expected_input_revision": 2,
                "decision": "confirm",
                "edited_summary_text": "多余文本不应出现在 confirm",
            }
        )
