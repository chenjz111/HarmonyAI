"""Executable HarmonyAI V3.1 flow freeze-candidate contracts."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path

from pydantic import TypeAdapter, ValidationError
import pytest

from backend.app.schemas.v3.flow_v31 import (
    ConfirmedUserState,
    DocumentRelevanceResult,
    DocumentSet,
    FinalConfirmedSummary,
    FiveToneAnalysisReadModel,
    QuestionnaireResult,
    RelevanceOutcome,
    ToneProfileV31,
    UserGoalV31,
    UserGoalSubmissionV31,
)


QUESTIONNAIRE_CHECKSUM = (
    "sha256:fef9830e3d269236a58213f95e2fd3449baf0ef52c0ffd74f516792f96910211"
)


def _document_set(count: int = 1) -> dict:
    return {
        "schema_version": "document_set_v3.1",
        "document_set_id": "dset_1",
        "session_id": "sess_1",
        "revision": 2,
        "session_input_revision": 4,
        "authority_status": "current",
        "documents": [
            {
                "document_id": f"doc_{index}",
                "position": index,
                "content_checksum": f"sha256:doc-{index}",
            }
            for index in range(1, count + 1)
        ],
    }


def _answers() -> list[dict]:
    return [
        {
            "question_id": f"q{index:02d}",
            "answer_type": "frequency_0_4",
            "value": 1,
        }
        for index in range(1, 6)
    ] + [
        {
            "question_id": f"q{index:02d}",
            "answer_type": "multi_choice_evidence",
            "value": ["none"],
        }
        for index in range(6, 11)
    ]


def _questionnaire_result(input_mode: str = "without_document") -> dict:
    return {
        "schema_version": "questionnaire_result_v3.1",
        "questionnaire_result_id": "qres_1",
        "session_id": "sess_1",
        "revision": 1,
        "authority_status": "current",
        "input_mode": input_mode,
        "entry_requirement": (
            "required" if input_mode == "without_document" else "optional"
        ),
        "schema_id": "questionnaire_v3",
        "questionnaire_schema_version": "3.0.0",
        "manifest_version": "medical_v3.0",
        "content_checksum": QUESTIONNAIRE_CHECKSUM,
        "answers": _answers(),
        "started_at": "2026-09-05T01:00:00Z",
        "completed_at": "2026-09-05T01:03:00Z",
    }


def _summary_ref() -> dict:
    return {
        "summary_id": "sum_1",
        "revision": 2,
        "content_checksum": "sha256:summary",
        "confirmation_status": "confirmed",
    }


def _questionnaire_ref() -> dict:
    return {
        "questionnaire_result_id": "qres_1",
        "revision": 1,
        "content_checksum": QUESTIONNAIRE_CHECKSUM,
        "completion_status": "complete",
    }


def _confirmed_state(mode: str) -> dict:
    summary = mode in {"document_only", "document_plus_questionnaire"}
    questionnaire = mode in {"document_plus_questionnaire", "questionnaire_only"}
    return {
        "schema_version": "confirmed_user_state_v3.1",
        "confirmed_user_state_id": "cus_1",
        "session_id": "sess_1",
        "source_mode": mode,
        "final_confirmed_summary_ref": _summary_ref() if summary else None,
        "questionnaire_result_ref": _questionnaire_ref() if questionnaire else None,
        "user_goal_ref": None,
        "confirmed_state_text": "最近一周睡眠恢复感一般。",
        "normalized_projection": [
            {
                "fact_id": "fact_1",
                "claim_code": "unrefreshing_sleep",
                "display_text": "睡后恢复感不足",
                "source_refs": ["qres_1:q01"],
            }
        ],
        "revision": 2,
        "content_checksum": "sha256:confirmed-state",
        "authority_status": "current",
        "confirmation_status": "confirmed",
        "confirmed_by": "user",
        "session_input_revision": 5,
        "created_at": "2026-09-05T01:04:00Z",
    }


def _tone_profile(secondary: str | None = None) -> dict:
    return {
        "schema_version": "tone_profile_v3.1",
        "weights": {
            "jiao": 0.15,
            "zhi": 0.10,
            "gong": 0.45,
            "shang": 0.10,
            "yu": 0.20,
        },
        "primary_tone": "gong",
        "secondary_tone": secondary,
        "score_semantics": "relative_tone_distribution",
        "mapping_version": "medical_v3.0",
        "basis": {
            "diagnosis_id": "diag_1",
            "diagnosis_revision": 1,
            "supporting_evidence_refs": ["fev_1"],
        },
    }


def _read_model(secondary: bool = False) -> dict:
    return {
        "schema_version": "five_tone_analysis_read_model_v3.1",
        "confirmed_user_state_ref": {
            "confirmed_user_state_id": "cus_1",
            "revision": 2,
            "content_checksum": "sha256:confirmed-state",
        },
        "confirmed_state": "最近一周睡眠恢复感一般。",
        "state_tendency": "整体偏向需要舒缓与稳定。",
        "analysis_rationales": [
            {
                "summary": "依据已确认状态与问卷结果整理。",
                "evidence_refs": ["fev_1"],
            }
        ],
        "primary_tone": {
            "tone": "gong",
            "display_name": "宫音",
            "explanation": "作为本次方案的主要声音方向。",
        },
        "secondary_tone": (
            {
                "tone": "yu",
                "display_name": "羽音",
                "explanation": "作为辅助声音方向。",
            }
            if secondary
            else None
        ),
        "bpm": {"value": 60, "explanation": "较舒缓的速度。"},
        "instruments": {
            "values": ["古琴"],
            "explanation": "音色较柔和。",
        },
        "ambience": {
            "values": ["细雨"],
            "explanation": "用于保持安静的听感。",
        },
        "duration": {"seconds": 900, "explanation": "适合一次完整聆听。"},
        "generation": {
            "status": "ready",
            "message": "方案已准备好，可以开始生成音乐。",
        },
        "disclaimer": "仅用于音乐调适参考，不构成医学诊断。",
    }


@pytest.mark.parametrize("count", [1, 3])
def test_document_set_accepts_one_to_three_ordered_documents(count: int):
    result = DocumentSet.model_validate(_document_set(count))
    assert [item.position for item in result.documents] == list(range(1, count + 1))


@pytest.mark.parametrize("count", [0, 4])
def test_document_set_rejects_out_of_range_document_count(count: int):
    with pytest.raises(ValidationError):
        DocumentSet.model_validate(_document_set(count))


def test_document_set_rejects_duplicate_or_nonsequential_documents():
    duplicate = _document_set(2)
    duplicate["documents"][1]["document_id"] = "doc_1"
    with pytest.raises(ValidationError):
        DocumentSet.model_validate(duplicate)

    unordered = _document_set(2)
    unordered["documents"][1]["position"] = 3
    with pytest.raises(ValidationError):
        DocumentSet.model_validate(unordered)


@pytest.mark.parametrize("outcome", ["VALID", "INVALID", "IRRELEVANT", "INSUFFICIENT"])
def test_relevance_outcomes_are_executable_and_preserve_routing(outcome: str):
    may_continue = outcome == "VALID"
    result = DocumentRelevanceResult.model_validate(
        {
            "schema_version": "document_relevance_result_v3.1",
            "relevance_result_id": "rel_1",
            "run_id": "run_1",
            "revision": 1,
            "document_set_ref": {"document_set_id": "dset_1", "revision": 2},
            "outcome": outcome,
            "reason_code": f"{outcome}_TEST",
            "reason": "用于合同测试的公开说明。",
            "may_enter_summary": may_continue,
            "may_form_evidence": may_continue,
            "may_enter_agent2": may_continue,
            "completed_at": "2026-09-05T01:01:00Z",
        }
    )
    assert result.may_enter_summary is may_continue


def test_relevance_unknown_outcome_and_false_valid_routing_fail():
    payload = {
        "schema_version": "document_relevance_result_v3.1",
        "relevance_result_id": "rel_1",
        "run_id": "run_1",
        "revision": 1,
        "document_set_ref": {"document_set_id": "dset_1", "revision": 2},
        "outcome": "UNKNOWN",
        "reason_code": "UNKNOWN_TEST",
        "reason": "测试",
        "may_enter_summary": False,
        "may_form_evidence": False,
        "may_enter_agent2": False,
        "completed_at": "2026-09-05T01:01:00Z",
    }
    with pytest.raises(ValidationError):
        DocumentRelevanceResult.model_validate(payload)
    payload["outcome"] = "VALID"
    with pytest.raises(ValidationError):
        DocumentRelevanceResult.model_validate(payload)


def test_final_confirmed_summary_separates_user_text_from_ai_and_ocr_sources():
    summary = FinalConfirmedSummary.model_validate(
        {
            "schema_version": "final_confirmed_summary_v3.1",
            "summary_id": "sum_1",
            "session_id": "sess_1",
            "source_document_set_ref": {"document_set_id": "dset_1", "revision": 2},
            "source_relevance_result_ref": {
                "relevance_result_id": "rel_1",
                "revision": 1,
                "outcome": "VALID",
            },
            "source_ai_summary_ref": {"summary_id": "ai_sum_1", "revision": 1},
            "ocr_source_refs": [
                {"document_id": "doc_1", "ocr_result_id": "ocr_1", "revision": 1}
            ],
            "confirmed_text": "近期资料显示睡眠恢复感不足。",
            "revision": 2,
            "content_checksum": "sha256:summary",
            "authority_status": "current",
            "confirmation_authority": "user",
            "confirmed_at": "2026-09-05T01:02:00Z",
        }
    )
    assert summary.source_ai_summary_ref.summary_id == "ai_sum_1"
    assert summary.confirmed_text != summary.source_ai_summary_ref.summary_id


def test_authoritative_questionnaire_asset_identity_and_five_page_structure():
    path = Path(__file__).parents[3] / "knowledge" / "v3" / "questionnaire-v3.0.json"
    questionnaire = json.loads(path.read_text(encoding="utf-8"))
    declared_checksum = questionnaire["content_checksum"]
    canonical = {key: value for key, value in questionnaire.items() if key != "content_checksum"}
    payload = json.dumps(
        canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")

    assert declared_checksum == f"sha256:{hashlib.sha256(payload).hexdigest()}"
    assert declared_checksum == QUESTIONNAIRE_CHECKSUM
    assert questionnaire["question_count"] == 10

    questions = sorted(questionnaire["questions"], key=lambda item: item["position"])
    assert [item["question_id"] for item in questions] == [
        f"q{index:02d}" for index in range(1, 11)
    ]
    assert [item["position"] for item in questions] == list(range(1, 11))
    assert all(item["required"] is True for item in questions)
    assert [item["answer_type"] for item in questions[:5]] == [
        "frequency_0_4"
    ] * 5
    assert [item["answer_type"] for item in questions[5:]] == [
        "multi_choice_evidence"
    ] * 5
    assert [
        [item["question_id"] for item in questions[offset : offset + 2]]
        for offset in range(0, 10, 2)
    ] == [
        ["q01", "q02"],
        ["q03", "q04"],
        ["q05", "q06"],
        ["q07", "q08"],
        ["q09", "q10"],
    ]


def test_questionnaire_result_requires_complete_canonical_q1_to_q10():
    result = QuestionnaireResult.model_validate(_questionnaire_result())
    assert len(result.answers) == 10
    assert result.content_checksum == QUESTIONNAIRE_CHECKSUM

    incomplete = _questionnaire_result()
    incomplete["answers"] = incomplete["answers"][:-1]
    with pytest.raises(ValidationError):
        QuestionnaireResult.model_validate(incomplete)


def test_questionnaire_requirement_is_bound_to_input_mode():
    QuestionnaireResult.model_validate(_questionnaire_result("without_document"))
    QuestionnaireResult.model_validate(_questionnaire_result("with_document"))

    invalid = _questionnaire_result("without_document")
    invalid["entry_requirement"] = "optional"
    with pytest.raises(ValidationError):
        QuestionnaireResult.model_validate(invalid)


def test_user_goal_is_nullable_and_accepts_one_or_two_distinct_codes():
    adapter = TypeAdapter(UserGoalV31 | None)
    assert adapter.validate_python(None) is None
    one = adapter.validate_python(
        {"primary_goal": "sleep", "secondary_goal": None, "custom_goal_text": None}
    )
    assert one.primary_goal.value == "sleep"
    two = adapter.validate_python(
        {
            "primary_goal": "sleep",
            "secondary_goal": "relaxation",
            "custom_goal_text": None,
        }
    )
    assert two.secondary_goal.value == "relaxation"


def test_user_goal_accepts_custom_text_only_and_other_without_text():
    custom_only = UserGoalV31.model_validate(
        {
            "primary_goal": None,
            "secondary_goal": None,
            "custom_goal_text": "希望音乐像流水一样",
        }
    )
    assert custom_only.primary_goal is None
    assert custom_only.custom_goal_text == "希望音乐像流水一样"

    other_without_text = UserGoalV31.model_validate(
        {"primary_goal": "other", "secondary_goal": None, "custom_goal_text": None}
    )
    assert other_without_text.primary_goal.value == "other"


def test_user_goal_accepts_goal_with_independent_custom_text():
    goal = UserGoalV31.model_validate(
        {
            "primary_goal": "sleep",
            "secondary_goal": "relaxation",
            "custom_goal_text": "想有一点雨声",
        }
    )
    assert goal.custom_goal_text == "想有一点雨声"


def test_empty_and_skipped_user_goal_are_canonical_null():
    adapter = TypeAdapter(UserGoalSubmissionV31)

    assert adapter.validate_python(None) is None
    assert adapter.validate_python(
        {"primary_goal": None, "secondary_goal": None, "custom_goal_text": None}
    ) is None
    assert adapter.validate_python(
        {"primary_goal": None, "secondary_goal": None, "custom_goal_text": "   "}
    ) is None


def test_user_goal_rejects_secondary_without_primary():
    with pytest.raises(ValidationError):
        UserGoalV31.model_validate(
            {
                "primary_goal": None,
                "secondary_goal": "relaxation",
                "custom_goal_text": None,
            }
        )


def test_user_goal_rejects_three_invalid_duplicate_and_long_text():
    cases = [
        {
            "primary_goal": "sleep",
            "secondary_goal": "relaxation",
            "tertiary_goal": "focus",
            "custom_goal_text": None,
        },
        {"primary_goal": "unknown", "secondary_goal": None, "custom_goal_text": None},
        {"primary_goal": "sleep", "secondary_goal": "sleep", "custom_goal_text": None},
        {"primary_goal": "other", "secondary_goal": None, "custom_goal_text": "x" * 201},
    ]
    for payload in cases:
        with pytest.raises(ValidationError):
            UserGoalV31.model_validate(payload)


@pytest.mark.parametrize(
    "mode", ["document_only", "document_plus_questionnaire", "questionnaire_only"]
)
def test_confirmed_user_state_accepts_exactly_three_source_combinations(mode: str):
    state = ConfirmedUserState.model_validate(_confirmed_state(mode))
    assert state.source_mode == mode
    assert state.authority_status == "current"


def test_confirmed_user_state_documents_internal_confirmation_authority():
    description = ConfirmedUserState.model_json_schema().get("description", "")

    assert "INTERNAL CONTRACT OBJECT" in description
    assert "not a user-facing page" in description
    assert "document_only inherits" in description
    assert "FinalConfirmedSummary" in description
    assert "does not require a second user confirmation" in description
    assert "questionnaire paths" in description
    assert "recent state summary confirmation" in description


def test_confirmed_user_state_rejects_source_mode_mismatch_and_stale_authority():
    mismatch = _confirmed_state("document_only")
    mismatch["questionnaire_result_ref"] = _questionnaire_ref()
    with pytest.raises(ValidationError):
        ConfirmedUserState.model_validate(mismatch)

    stale = _confirmed_state("questionnaire_only")
    stale["authority_status"] = "superseded"
    with pytest.raises(ValidationError):
        ConfirmedUserState.model_validate(stale)


def test_tone_profile_accepts_optional_secondary_and_rejects_invalid_tone():
    assert ToneProfileV31.model_validate(_tone_profile()).secondary_tone is None
    assert ToneProfileV31.model_validate(_tone_profile("yu")).secondary_tone.value == "yu"
    invalid = _tone_profile("invalid")
    with pytest.raises(ValidationError):
        ToneProfileV31.model_validate(invalid)


def test_tone_profile_rejects_secondary_equal_to_primary():
    with pytest.raises(ValidationError):
        ToneProfileV31.model_validate(_tone_profile("gong"))


def test_five_tone_read_model_supports_primary_only_and_optional_secondary():
    assert FiveToneAnalysisReadModel.model_validate(_read_model()).secondary_tone is None
    assert FiveToneAnalysisReadModel.model_validate(_read_model(True)).secondary_tone is not None


def test_five_tone_read_model_requires_public_explanations_and_forbids_internals():
    missing_explanation = _read_model()
    missing_explanation["bpm"]["explanation"] = ""
    with pytest.raises(ValidationError):
        FiveToneAnalysisReadModel.model_validate(missing_explanation)

    leaked = _read_model()
    leaked["provider_prompt"] = "private chain-of-thought"
    with pytest.raises(ValidationError):
        FiveToneAnalysisReadModel.model_validate(leaked)
