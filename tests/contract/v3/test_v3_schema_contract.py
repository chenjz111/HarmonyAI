from copy import deepcopy

from pydantic import ValidationError
import pytest

from backend.app.schemas.v3.common import (
    ElementCode,
    ElementProfile,
    OrganCode,
    OrganProfile,
    SafetyStatus,
    ToneCode,
    UserGoal,
)


def test_v3_canonical_enums_are_frozen():
    assert {item.value for item in ToneCode} == {
        "jiao",
        "zhi",
        "gong",
        "shang",
        "yu",
    }
    assert {item.value for item in OrganCode} == {
        "liver",
        "heart",
        "spleen",
        "lung",
        "kidney",
    }
    assert {item.value for item in ElementCode} == {
        "wood",
        "fire",
        "earth",
        "metal",
        "water",
    }
    assert "resolved" in {item.value for item in SafetyStatus}
    assert "blocked" not in {item.value for item in SafetyStatus}


def test_available_profiles_require_complete_normalized_weights():
    profile = OrganProfile.model_validate(
        {
            "status": "available",
            "weights": {
                "liver": 0.18,
                "heart": 0.12,
                "spleen": 0.46,
                "lung": 0.09,
                "kidney": 0.15,
            },
            "score_semantics": "relative_evidence_distribution",
        }
    )
    assert profile.weights is not None
    assert sum(profile.weights.values()) == pytest.approx(1.0)

    with pytest.raises(ValidationError):
        OrganProfile.model_validate(
            {
                "status": "available",
                "weights": {"liver": 1.0},
                "score_semantics": "relative_evidence_distribution",
            }
        )

    with pytest.raises(ValidationError):
        ElementProfile.model_validate(
            {
                "status": "available",
                "weights": {
                    "wood": 0.4,
                    "fire": 0.2,
                    "earth": 0.2,
                    "metal": 0.1,
                    "water": 0.3,
                },
                "score_semantics": "relative_element_support",
            }
        )


def test_insufficient_profiles_cannot_claim_weights():
    profile = OrganProfile.model_validate(
        {
            "status": "insufficient",
            "weights": None,
            "score_semantics": "relative_evidence_distribution",
        }
    )
    assert profile.weights is None

    with pytest.raises(ValidationError):
        OrganProfile.model_validate(
            {
                "status": "insufficient",
                "weights": {
                    "liver": 0.2,
                    "heart": 0.2,
                    "spleen": 0.2,
                    "lung": 0.2,
                    "kidney": 0.2,
                },
                "score_semantics": "relative_evidence_distribution",
            }
        )


def test_user_goal_allows_at_most_two_distinct_choices_and_requires_custom_text():
    goal = UserGoal.model_validate(
        {
            "primary_goal": "sleep",
            "secondary_goal": "relaxation",
            "custom_goal_text": None,
        }
    )
    assert goal.primary_goal.value == "sleep"

    with pytest.raises(ValidationError):
        UserGoal.model_validate(
            {
                "primary_goal": "sleep",
                "secondary_goal": "sleep",
                "custom_goal_text": None,
            }
        )

    custom = UserGoal.model_validate(
        {
            "primary_goal": "other",
            "secondary_goal": None,
            "custom_goal_text": "希望脑子不要一直想事情",
        }
    )
    assert custom.custom_goal_text == "希望脑子不要一直想事情"

    with pytest.raises(ValidationError):
        UserGoal.model_validate(
            {
                "primary_goal": "other",
                "secondary_goal": None,
                "custom_goal_text": None,
            }
        )

    with pytest.raises(ValidationError):
        UserGoal.model_validate(
            {
                "primary_goal": "sleep",
                "secondary_goal": None,
                "custom_goal_text": "不应出现",
            }
        )


def test_external_models_reject_unknown_fields():
    with pytest.raises(ValidationError):
        UserGoal.model_validate(
            {
                "primary_goal": "sleep",
                "secondary_goal": None,
                "custom_goal_text": None,
                "unexpected": True,
            }
        )


def test_normalized_fact_value_is_discriminated_and_cannot_leak_agent_outputs():
    from backend.app.schemas.v3.understanding import NormalizedFact

    fact = NormalizedFact.model_validate(
        {
            "fact_id": "fact_sleep_1",
            "fact_code": "sleep_unrefreshing",
            "display_name": "睡眠后仍感疲惫",
            "category": "sleep",
            "value": {"type": "severity", "value": "moderate"},
            "time_window": "past_7_days",
            "negated": False,
            "subject": "self",
            "source_refs": [
                {
                    "source_id": "nar_1",
                    "source_type": "narrative",
                    "span_ref": "span_1",
                }
            ],
            "confirmation_status": "confirmed",
            "extraction": {"method": "qwen", "confidence": 0.84},
        }
    )
    assert fact.value.type == "severity"

    with pytest.raises(ValidationError):
        NormalizedFact.model_validate(
            {
                **fact.model_dump(mode="json"),
                "organ": "heart",
            }
        )

    invalid_value = fact.model_dump(mode="json")
    invalid_value["value"] = {"type": "severity", "value": "very_high"}
    with pytest.raises(ValidationError):
        NormalizedFact.model_validate(invalid_value)


def test_fact_owner_requires_exactly_one_authoritative_snapshot():
    from backend.app.schemas.v3.understanding import FactOwnerRef

    understanding_owner = FactOwnerRef.model_validate(
        {
            "owner_type": "understanding",
            "understanding_id": "und_1",
            "understanding_revision": 2,
            "questionnaire_submission_id": None,
        }
    )
    assert understanding_owner.understanding_revision == 2

    questionnaire_owner = FactOwnerRef.model_validate(
        {
            "owner_type": "questionnaire",
            "understanding_id": None,
            "understanding_revision": None,
            "questionnaire_submission_id": "qsub_1",
        }
    )
    assert questionnaire_owner.questionnaire_submission_id == "qsub_1"

    with pytest.raises(ValidationError):
        FactOwnerRef.model_validate(
            {
                "owner_type": "questionnaire",
                "understanding_id": "und_fake",
                "understanding_revision": 1,
                "questionnaire_submission_id": "qsub_1",
            }
        )


def test_understanding_response_preserves_revision_and_safety_authority():
    from backend.app.schemas.v3.understanding import UnderstandingV3Response

    response = UnderstandingV3Response.model_validate(
        {
            "schema_version": "understanding_v3.0",
            "understanding_id": "und_1",
            "revision": 2,
            "status": "confirmed",
            "case_summary": None,
            "voice_transcripts": [],
            "normalized_facts": [],
            "source_statuses": [
                {
                    "source_id": "nar_1",
                    "source_type": "narrative",
                    "status": "ready",
                }
            ],
            "safety_status": "resolved",
            "safety_signal_refs": [],
            "degradation": {"active": False, "reason_codes": []},
        }
    )
    assert response.revision == 2
    assert response.safety_status is SafetyStatus.resolved

    with pytest.raises(ValidationError):
        UnderstandingV3Response.model_validate(
            {
                **response.model_dump(mode="json"),
                "status": "success",
            }
        )

def test_assessment_request_accepts_resource_refs_not_client_built_facts():
    from backend.app.schemas.v3.assessment import AssessmentV3Request

    payload = {
        "schema_version": "assessment_v3.0",
        "session_id": "sess_1",
        "understanding_ref": {"understanding_id": "und_1", "revision": 2},
        "questionnaire_ref": None,
        "user_goal": {
            "primary_goal": "sleep",
            "secondary_goal": "relaxation",
            "custom_goal_text": None,
        },
    }
    request = AssessmentV3Request.model_validate(payload)
    assert request.understanding_ref.revision == 2

    with pytest.raises(ValidationError):
        AssessmentV3Request.model_validate(
            {
                **payload,
                "normalized_facts": [],
            }
        )


def test_one_fact_evidence_can_link_multiple_organs_without_fact_duplication():
    from backend.app.schemas.v3.assessment import AssessmentV3Response

    payload = {
        "schema_version": "assessment_v3.0",
        "agent_id": "assessment_agent",
        "assessment_id": "asmt_1",
        "revision": 1,
        "status": "needs_confirmation",
        "understanding_ref": {"understanding_id": "und_1", "revision": 2},
        "state_summary": "近期睡眠恢复不足。",
        "recent_context_summary": "近期学习安排较紧。",
        "organ_profile": {
            "status": "available",
            "weights": {
                "liver": 0.1,
                "heart": 0.3,
                "spleen": 0.4,
                "lung": 0.1,
                "kidney": 0.1,
            },
            "score_semantics": "relative_evidence_distribution",
        },
        "fact_evidence": [
            {
                "fact_evidence_id": "fev_1",
                "assessment_id": "asmt_1",
                "assessment_revision": 1,
                "fact_id": "fact_1",
                "claim_code": "sleep_unrefreshing",
                "display_name": "睡眠后仍感疲惫",
                "category": "sleep",
                "value": {"type": "severity", "value": "moderate"},
                "time_window": "past_7_days",
                "direction": "supporting",
                "reliability": 0.84,
                "source_refs": [
                    {"source_id": "nar_1", "source_type": "narrative"}
                ],
                "confirmation_status": "confirmed",
            }
        ],
        "organ_evidence_links": [
            {
                "organ_evidence_link_id": "oel_1",
                "fact_evidence_id": "fev_1",
                "organ": "heart",
                "element": "fire",
                "direction": "supporting",
                "link_strength": 0.7,
                "mapping_rule_id": "map_heart_1",
                "mapping_version": "organ_mapping_v3.0",
                "explanation_summary": "作为心相关倾向的辅助依据。",
            },
            {
                "organ_evidence_link_id": "oel_2",
                "fact_evidence_id": "fev_1",
                "organ": "spleen",
                "element": "earth",
                "direction": "supporting",
                "link_strength": 0.6,
                "mapping_rule_id": "map_spleen_1",
                "mapping_version": "organ_mapping_v3.0",
                "explanation_summary": "作为脾相关倾向的辅助依据。",
            },
        ],
        "conflicts": [],
        "missing_information": [],
        "evidence_coverage": 1.0,
        "evidence_coverage_semantics": "confirmed_available_source_coverage",
        "source_diversity": 1,
        "requires_user_confirmation": True,
        "safety_status": "clear",
        "degradation": {"active": False, "reason_codes": []},
        "presentation": {
            "title": "确认一下我们对你当前状态的理解",
            "summary": "近期睡眠恢复不足。",
            "body_summaries": ["睡眠恢复不足"],
            "recent_context": "近期学习安排较紧。",
            "goal_summary": "本次希望帮助入睡并放松紧张",
        },
    }
    assessment = AssessmentV3Response.model_validate(payload)
    assert len(assessment.fact_evidence) == 1
    assert len(assessment.organ_evidence_links) == 2

    duplicate_fact = assessment.model_dump(mode="json")
    duplicate_fact["fact_evidence"].append(duplicate_fact["fact_evidence"][0])
    with pytest.raises(ValidationError):
        AssessmentV3Response.model_validate(duplicate_fact)

    dangling_link = assessment.model_dump(mode="json")
    dangling_link["organ_evidence_links"][0]["fact_evidence_id"] = "fev_missing"
    with pytest.raises(ValidationError):
        AssessmentV3Response.model_validate(dangling_link)

def test_diagnosis_status_union_rejects_successful_abstention():
    from backend.app.schemas.v3.diagnosis import DiagnosisV3

    payload = {
        "schema_version": "diagnosis_v3.0",
        "agent_id": "diagnosis_agent",
        "diagnosis_id": "diag_1",
        "assessment_ref": {"assessment_id": "asmt_1", "revision": 2},
        "status": "success",
        "abstained": False,
        "abstain_reason": None,
        "candidate_tendencies": [
            {
                "candidate_id": "cand_1",
                "syndrome_code": "heart_spleen_deficiency_tendency",
                "display_name": "心脾两虚倾向",
                "relative_support": 0.73,
                "supporting_fact_ids": ["fev_1"],
                "contradicting_fact_ids": [],
                "knowledge_chunk_ids": ["kb_1"],
                "reasoning_summary": "多条已确认状态证据共同支持该倾向。",
            }
        ],
        "primary_tendency_id": "cand_1",
        "element_profile": {
            "status": "available",
            "weights": {
                "wood": 0.16,
                "fire": 0.24,
                "earth": 0.42,
                "metal": 0.08,
                "water": 0.10,
            },
            "score_semantics": "relative_element_support",
        },
        "rag_result_ref": "rag_1",
        "execution_versions": {
            "prompt_version": "diagnosis_prompt_v3.0",
            "response_schema_version": "diagnosis_provider_response_v3.0",
            "knowledge_version": "medical_v3.0",
            "mapping_version": "organ_mapping_v3.0",
        },
        "degradation": {"active": False, "reason_codes": []},
        "presentation": {
            "title": "辅助辨证倾向",
            "primary_tendency": "心脾两虚倾向",
            "basis_summaries": ["睡眠恢复不足"],
            "knowledge_references": [
                {"title": "审核后的知识来源", "summary": "相关依据摘要"}
            ],
            "disclaimer": "本结果仅用于音乐调养参考，不构成医学诊断。",
        },
    }
    diagnosis = DiagnosisV3.model_validate(payload)
    assert diagnosis.abstained is False

    invalid = diagnosis.model_dump(mode="json")
    invalid["abstained"] = True
    invalid["abstain_reason"] = "INSUFFICIENT_EVIDENCE"
    with pytest.raises(ValidationError):
        DiagnosisV3.model_validate(invalid)


def test_abstained_diagnosis_has_no_candidates_and_insufficient_element_profile():
    from backend.app.schemas.v3.diagnosis import DiagnosisV3

    diagnosis = DiagnosisV3.model_validate(
        {
            "schema_version": "diagnosis_v3.0",
            "agent_id": "diagnosis_agent",
            "diagnosis_id": "diag_2",
            "assessment_ref": {"assessment_id": "asmt_1", "revision": 2},
            "status": "abstained",
            "abstained": True,
            "abstain_reason": "INSUFFICIENT_EVIDENCE",
            "candidate_tendencies": [],
            "primary_tendency_id": None,
            "element_profile": {
                "status": "insufficient",
                "weights": None,
                "score_semantics": "relative_element_support",
            },
            "rag_result_ref": None,
            "execution_versions": {
                "prompt_version": "diagnosis_prompt_v3.0",
                "response_schema_version": "diagnosis_provider_response_v3.0",
                "knowledge_version": "medical_v3.0",
                "mapping_version": "organ_mapping_v3.0",
            },
            "degradation": {
                "active": True,
                "reason_codes": ["INSUFFICIENT_EVIDENCE"],
            },
            "presentation": {
                "title": "辅助辨证倾向",
                "primary_tendency": None,
                "basis_summaries": [],
                "knowledge_references": [],
                "disclaimer": "本结果仅用于音乐调养参考，不构成医学诊断。",
            },
        }
    )
    assert diagnosis.candidate_tendencies == []

    invalid = diagnosis.model_dump(mode="json")
    invalid["element_profile"] = {
        "status": "available",
        "weights": {
            "wood": 0.2,
            "fire": 0.2,
            "earth": 0.2,
            "metal": 0.2,
            "water": 0.2,
        },
        "score_semantics": "relative_element_support",
    }
    with pytest.raises(ValidationError):
        DiagnosisV3.model_validate(invalid)


def test_rag_result_never_labels_empty_retrieval_as_success():
    from backend.app.schemas.v3.diagnosis import RagResult

    with pytest.raises(ValidationError):
        RagResult.model_validate(
            {
                "retrieval_id": "rag_1",
                "status": "success",
                "knowledge_version": "medical_v3.0",
                "embedding_version": "embedding_v1",
                "retrieval_score_semantics": "one_minus_cosine_distance",
                "hits": [],
                "degradation": {"active": False, "reason_codes": []},
            }
        )

    empty = RagResult.model_validate(
        {
            "retrieval_id": "rag_2",
            "status": "empty",
            "knowledge_version": "medical_v3.0",
            "embedding_version": "embedding_v1",
            "retrieval_score_semantics": "one_minus_cosine_distance",
            "hits": [],
            "degradation": {"active": True, "reason_codes": ["NO_RAG_HIT"]},
        }
    )
    assert empty.status == "empty"

def _question(question_number: int) -> dict:
    question_id = f"q{question_number:02d}"
    return {
        "question_id": question_id,
        "position": question_number,
        "prompt": f"测试结构题目 {question_number}",
        "answer_type": "multi_choice_evidence",
        "required": True,
        "min_selections": 1,
        "max_selections": 2,
        "options": [
            {
                "option_code": f"test_option_{question_number}",
                "label": "测试选项",
                "claim_code": f"test_claim_{question_number}",
                "is_none": False,
                "exclusive_with": [],
            },
            {
                "option_code": "none",
                "label": "无以上情况",
                "claim_code": None,
                "is_none": True,
                "exclusive_with": ["*"],
            },
        ],
    }


def test_questionnaire_manifest_shape_requires_exactly_ten_reviewed_questions():
    from backend.app.schemas.v3.common import QuestionnaireSchemaV3

    payload = {
        "schema_id": "questionnaire_v3",
        "schema_version": "3.0.0",
        "manifest_version": "medical_test_v3.0",
        "time_window": "past_7_days",
        "time_window_days": 7,
        "question_count": 10,
        "questions": [_question(index) for index in range(1, 11)],
        "claim_dictionary_version": "medical_test_v3.0",
        "content_checksum": "sha256:test-only",
        "review_status": "approved",
    }
    schema = QuestionnaireSchemaV3.model_validate(payload)
    assert schema.question_count == 10

    too_short = deepcopy(payload)
    too_short["questions"] = too_short["questions"][:-1]
    with pytest.raises(ValidationError):
        QuestionnaireSchemaV3.model_validate(too_short)

    invalid_none = deepcopy(payload)
    invalid_none["questions"][0]["options"][1]["exclusive_with"] = []
    with pytest.raises(ValidationError):
        QuestionnaireSchemaV3.model_validate(invalid_none)


def test_questionnaire_submission_answer_value_matches_answer_type():
    from backend.app.schemas.v3.common import QuestionnaireV3Submission

    payload = {
        "questionnaire_submission_id": "qsub_1",
        "schema_id": "questionnaire_v3",
        "schema_version": "3.0.0",
        "manifest_version": "medical_test_v3.0",
        "content_checksum": "sha256:test-only",
        "time_window_days": 7,
        "answers": [
            {
                "question_id": "q01",
                "answer_type": "multi_choice_evidence",
                "value": ["test_option_1"],
            }
        ],
        "started_at": "2026-08-22T08:05:00Z",
        "completed_at": "2026-08-22T08:08:00Z",
    }
    submission = QuestionnaireV3Submission.model_validate(payload)
    assert submission.answers[0].answer_type == "multi_choice_evidence"

    invalid = deepcopy(payload)
    invalid["answers"][0]["value"] = "test_option_1"
    with pytest.raises(ValidationError):
        QuestionnaireV3Submission.model_validate(invalid)


def test_guest_auth_principal_has_explicit_expiry_and_registered_user_does_not():
    from backend.app.schemas.v3.common import AuthPrincipal

    guest = AuthPrincipal.model_validate(
        {
            "internal_user_pk": 42,
            "public_user_id": "u_guest_1",
            "auth_type": "guest",
            "guest_expires_at": "2026-08-23T08:00:00Z",
        }
    )
    assert guest.auth_type == "guest"

    with pytest.raises(ValidationError):
        AuthPrincipal.model_validate(
            {
                "internal_user_pk": 42,
                "public_user_id": "u_guest_1",
                "auth_type": "guest",
                "guest_expires_at": None,
            }
        )

    with pytest.raises(ValidationError):
        AuthPrincipal.model_validate(
            {
                "internal_user_pk": 43,
                "public_user_id": "u_registered_1",
                "auth_type": "registered",
                "guest_expires_at": "2026-08-23T08:00:00Z",
            }
        )

def test_claim_dictionary_entry_is_structured_and_medically_approved():
    from backend.app.schemas.v3.common import ClaimDictionaryEntry

    entry = ClaimDictionaryEntry.model_validate(
        {
            "claim_code": "flank_discomfort",
            "display_name": "胁肋部不适",
            "category": "physical_signal",
            "value_type": "boolean",
            "allowed_values": [True, False],
            "questionnaire_option_refs": ["q01:flank_discomfort"],
            "organ_mapping_allowed": True,
            "medical_review": {
                "status": "approved",
                "review_version": "medical_v3.0",
            },
        }
    )
    assert entry.medical_review.status == "approved"

    invalid = entry.model_dump(mode="json")
    invalid["medical_review"]["status"] = "pending"
    with pytest.raises(ValidationError):
        ClaimDictionaryEntry.model_validate(invalid)


def test_contract_timestamps_must_be_timezone_aware_utc():
    from backend.app.schemas.v3.common import GuestAuthResponse

    valid = GuestAuthResponse.model_validate(
        {
            "access_token": "guest-token",
            "token_type": "Bearer",
            "expires_at": "2026-08-24T08:00:00Z",
            "public_user_id": "usr_guest_1",
        }
    )
    assert valid.expires_at.utcoffset().total_seconds() == 0

    with pytest.raises(ValidationError):
        GuestAuthResponse.model_validate(
            {
                "access_token": "guest-token",
                "token_type": "Bearer",
                "expires_at": "2026-08-24T08:00:00",
                "public_user_id": "usr_guest_1",
            }
        )

def test_claim_dictionary_allowed_values_match_declared_value_type():
    from backend.app.schemas.v3.common import ClaimDictionaryEntry

    with pytest.raises(ValidationError):
        ClaimDictionaryEntry.model_validate(
            {
                "claim_code": "flank_discomfort",
                "display_name": "胁肋部不适",
                "category": "physical_signal",
                "value_type": "boolean",
                "allowed_values": ["true", "false"],
                "questionnaire_option_refs": ["q01:flank_discomfort"],
                "organ_mapping_allowed": True,
                "medical_review": {
                    "status": "approved",
                    "review_version": "medical_v3.0",
                },
            }
        )