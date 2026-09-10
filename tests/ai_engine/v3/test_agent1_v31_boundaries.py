from datetime import datetime, timezone

import pytest


def _document_set(count: int = 1, *, owner_user_pk: int = 7) -> dict:
    return {
        "schema_version": "document_set_v3.1",
        "document_set_id": "dset_1",
        "session_id": "sess_1",
        "revision": 4,
        "session_input_revision": 9,
        "authority_status": "current",
        "documents": [
            {
                "document_id": f"doc_{index}",
                "position": index,
                "content_checksum": f"sha256:doc-{index}",
            }
            for index in range(1, count + 1)
        ],
        "owner_user_pk": owner_user_pk,
    }


def _relevance(
    document_ids: list[str],
    *,
    outcome: str = "VALID",
    outcomes: dict[str, str] | None = None,
    revision: int = 4,
):
    outcomes = outcomes or {}
    return [
        {
            "relevance_result_id": f"rel_{document_id}",
            "document_set_id": "dset_1",
            "document_set_revision": revision,
            "document_id": document_id,
            "outcome": outcomes.get(document_id, outcome),
            "reason_code": f"{outcomes.get(document_id, outcome)}_TEST",
            "evaluated_at": datetime.now(timezone.utc),
        }
        for document_id in document_ids
    ]


@pytest.mark.parametrize("count", [1, 3])
def test_agent1_resolves_one_to_three_current_valid_documents_in_saved_order(count):
    from backend.ai_engine.v3.agent1_v31 import resolve_active_document_set

    result = resolve_active_document_set(
        _document_set(count),
        _relevance([f"doc_{index}" for index in range(1, count + 1)]),
        expected_user_pk=7,
        expected_session_id="sess_1",
        expected_document_set_id="dset_1",
        expected_document_set_revision=4,
        expected_session_input_revision=9,
    )

    assert [item.document_id for item in result.valid_documents] == [
        f"doc_{index}" for index in range(1, count + 1)
    ]
    assert [item.source_ref.source_id for item in result.valid_documents] == [
        f"doc_{index}" for index in range(1, count + 1)
    ]


def test_agent1_excludes_invalid_and_irrelevant_documents_from_downstream():
    from backend.ai_engine.v3.agent1_v31 import resolve_active_document_set

    result = resolve_active_document_set(
        _document_set(3),
        _relevance(
            ["doc_1", "doc_2", "doc_3"],
            outcomes={"doc_2": "INVALID", "doc_3": "IRRELEVANT"},
        ),
        expected_user_pk=7,
        expected_session_id="sess_1",
        expected_document_set_id="dset_1",
        expected_document_set_revision=4,
        expected_session_input_revision=9,
    )

    assert [item.document_id for item in result.valid_documents] == ["doc_1"]
    assert result.excluded_document_ids == ("doc_2", "doc_3")


@pytest.mark.parametrize(
    "outcome,expected_code",
    [
        ("INSUFFICIENT", "RELEVANCE_INSUFFICIENT"),
        ("INVALID", "DOCUMENT_SET_NO_VALID_DOCUMENT"),
    ],
)
def test_agent1_does_not_treat_unresolved_or_all_invalid_documents_as_valid(
    outcome, expected_code
):
    from backend.ai_engine.v3.agent1_v31 import Agent1InputBlocked, resolve_active_document_set

    with pytest.raises(Agent1InputBlocked, match=expected_code):
        resolve_active_document_set(
            _document_set(1),
            _relevance(["doc_1"], outcome=outcome),
            expected_user_pk=7,
            expected_session_id="sess_1",
            expected_document_set_id="dset_1",
            expected_document_set_revision=4,
            expected_session_input_revision=9,
        )


def test_agent1_requires_complete_current_relevance_results():
    from backend.ai_engine.v3.agent1_v31 import Agent1InputBlocked, resolve_active_document_set

    with pytest.raises(Agent1InputBlocked, match="RELEVANCE_NOT_READY"):
        resolve_active_document_set(
            _document_set(2),
            _relevance(["doc_1"]),
            expected_user_pk=7,
            expected_session_id="sess_1",
            expected_document_set_id="dset_1",
            expected_document_set_revision=4,
            expected_session_input_revision=9,
        )


@pytest.mark.parametrize(
    "kwargs,expected_code",
    [
        ({"expected_user_pk": 8}, "DOCUMENT_SET_NOT_OWNED"),
        ({"expected_session_id": "sess_other"}, "DOCUMENT_SET_NOT_OWNED"),
        ({"expected_document_set_id": "dset_old"}, "DOCUMENT_SET_NOT_ACTIVE"),
        ({"expected_document_set_revision": 3}, "DOCUMENT_SET_NOT_ACTIVE"),
        ({"expected_session_input_revision": 8}, "DOCUMENT_SET_NOT_ACTIVE"),
    ],
)
def test_agent1_rejects_cross_scope_or_stale_document_set(kwargs, expected_code):
    from backend.ai_engine.v3.agent1_v31 import Agent1InputBlocked, resolve_active_document_set

    params = {
        "expected_user_pk": 7,
        "expected_session_id": "sess_1",
        "expected_document_set_id": "dset_1",
        "expected_document_set_revision": 4,
        "expected_session_input_revision": 9,
    }
    params.update(kwargs)
    with pytest.raises(Agent1InputBlocked, match=expected_code):
        resolve_active_document_set(
            _document_set(1),
            _relevance(["doc_1"]),
            **params,
        )


def test_agent1_requires_relevance_document_identity_and_never_defaults_missing_result_to_valid():
    from backend.ai_engine.v3.agent1_v31 import Agent1InputBlocked, resolve_active_document_set

    missing_document_id = _relevance(["doc_1"])[0]
    missing_document_id.pop("document_id")
    with pytest.raises(Agent1InputBlocked, match="RELEVANCE_NOT_READY"):
        resolve_active_document_set(
            _document_set(1),
            [missing_document_id],
            expected_user_pk=7,
            expected_session_id="sess_1",
            expected_document_set_id="dset_1",
            expected_document_set_revision=4,
            expected_session_input_revision=9,
        )


def test_questionnaire_301_adapter_emits_confirmed_facts_with_questionnaire_provenance():
    from backend.ai_engine.v3.agent1_v31 import questionnaire_result_to_normalized_facts
    from backend.app.schemas.v3.flow_v31 import QuestionnaireResult

    questionnaire = QuestionnaireResult.model_validate(
        {
            "schema_version": "questionnaire_result_v3.1",
            "questionnaire_result_id": "qres_1",
            "session_id": "sess_1",
            "revision": 1,
            "authority_status": "current",
            "input_mode": "without_document",
            "entry_requirement": "required",
            "schema_id": "questionnaire_v3",
            "questionnaire_schema_version": "3.0.1",
            "manifest_version": "medical_v3.0.1",
            "content_checksum": "sha256:69a01d0753908e3e48e41ea947219818436f24eb4e97aeca260f4b4ca4951031",
            "answers": [
                *[
                    {"question_id": f"q{index:02d}", "answer_type": "frequency_0_4", "value": 1}
                    for index in range(1, 6)
                ],
                *[
                    {"question_id": f"q{index:02d}", "answer_type": "multi_choice_evidence", "value": ["none"]}
                    for index in range(6, 11)
                ],
            ],
            "started_at": "2026-09-07T01:00:00Z",
            "completed_at": "2026-09-07T01:03:00Z",
        }
    )

    facts = questionnaire_result_to_normalized_facts(questionnaire)

    assert facts
    assert all(fact["confirmation_status"] == "confirmed" for fact in facts)
    assert all(
        ref["source_id"] == "qres_1"
        and ref["source_type"] == "questionnaire"
        for fact in facts
        for ref in fact["source_refs"]
    )
    assert all("user_goal" not in fact for fact in facts)


def _questionnaire_result():
    from backend.app.schemas.v3.flow_v31 import QuestionnaireResult

    return QuestionnaireResult.model_validate(
        {
            "schema_version": "questionnaire_result_v3.1",
            "questionnaire_result_id": "qres_1",
            "session_id": "sess_1",
            "revision": 1,
            "authority_status": "current",
            "input_mode": "with_document",
            "entry_requirement": "optional",
            "schema_id": "questionnaire_v3",
            "questionnaire_schema_version": "3.0.1",
            "manifest_version": "medical_v3.0.1",
            "content_checksum": "sha256:69a01d0753908e3e48e41ea947219818436f24eb4e97aeca260f4b4ca4951031",
            "answers": [
                *[
                    {"question_id": f"q{index:02d}", "answer_type": "frequency_0_4", "value": 1}
                    for index in range(1, 6)
                ],
                *[
                    {"question_id": f"q{index:02d}", "answer_type": "multi_choice_evidence", "value": ["none"]}
                    for index in range(6, 11)
                ],
            ],
            "started_at": "2026-09-07T01:00:00Z",
            "completed_at": "2026-09-07T01:03:00Z",
        }
    )


def test_agent1_fuses_valid_document_and_questionnaire_facts_from_confirmed_state():
    from backend.ai_engine.v3.agent1_v31 import (
        build_confirmed_agent1_input,
        resolve_active_document_set,
    )
    from backend.app.schemas.v3.flow_v31 import ConfirmedUserState

    document_input = resolve_active_document_set(
        _document_set(1),
        _relevance(["doc_1"]),
        expected_user_pk=7,
        expected_session_id="sess_1",
        expected_document_set_id="dset_1",
        expected_document_set_revision=4,
        expected_session_input_revision=9,
    )
    state = ConfirmedUserState.model_validate(
        {
            "schema_version": "confirmed_user_state_v3.1",
            "confirmed_user_state_id": "cus_1",
            "session_id": "sess_1",
            "source_mode": "document_plus_questionnaire",
            "final_confirmed_summary_ref": {
                "summary_id": "sum_1",
                "revision": 1,
                "content_checksum": "sha256:summary",
                "confirmation_status": "confirmed",
            },
            "questionnaire_result_ref": {
                "questionnaire_result_id": "qres_1",
                "revision": 1,
                "content_checksum": "sha256:69a01d0753908e3e48e41ea947219818436f24eb4e97aeca260f4b4ca4951031",
                "completion_status": "complete",
            },
            "user_goal_ref": None,
            "confirmed_state_text": "近期状态已确认。",
            "normalized_projection": [
                {
                    "fact_id": "doc_fact_1",
                    "claim_code": "unrefreshing_sleep",
                    "display_text": "睡后恢复感不足",
                    "source_refs": ["doc_1:span_1"],
                }
            ],
            "revision": 2,
            "content_checksum": "sha256:state",
            "authority_status": "current",
            "confirmation_status": "confirmed",
            "confirmed_by": "user",
            "session_input_revision": 9,
            "created_at": "2026-09-07T01:04:00Z",
        }
    )
    facts = [
        {
            "fact_id": "doc_fact_1",
            "fact_code": "unrefreshing_sleep",
            "display_name": "睡后恢复感不足",
            "category": "sleep",
            "value": {"type": "frequency_0_4", "value": 3},
            "time_window": "past_7_days",
            "negated": False,
            "subject": "self",
            "source_refs": [
                {"source_id": "doc_1", "source_type": "document", "span_ref": "span_1"}
            ],
            "confirmation_status": "confirmed",
            "extraction": {"method": "rule", "confidence": 0.8},
        }
    ]

    bundle = build_confirmed_agent1_input(
        state,
        document_input=document_input,
        document_facts=facts,
        questionnaire_result=_questionnaire_result(),
    )

    assert {fact["fact_id"] for fact in bundle.facts} >= {"doc_fact_1"}
    assert any(
        fact["source_refs"][0]["source_type"] == "questionnaire"
        for fact in bundle.facts
    )
    assert all("user_goal" not in fact for fact in bundle.facts)


def test_agent1_questionnaire_only_path_uses_confirmed_state_without_documents():
    from backend.ai_engine.v3.agent1_v31 import build_confirmed_agent1_input
    from backend.app.schemas.v3.flow_v31 import ConfirmedUserState

    state = ConfirmedUserState.model_validate(
        {
            "schema_version": "confirmed_user_state_v3.1",
            "confirmed_user_state_id": "cus_q_only",
            "session_id": "sess_1",
            "source_mode": "questionnaire_only",
            "final_confirmed_summary_ref": None,
            "questionnaire_result_ref": {
                "questionnaire_result_id": "qres_1",
                "revision": 1,
                "content_checksum": "sha256:69a01d0753908e3e48e41ea947219818436f24eb4e97aeca260f4b4ca4951031",
                "completion_status": "complete",
            },
            "user_goal_ref": None,
            "confirmed_state_text": "近期状态已确认。",
            "normalized_projection": [],
            "revision": 1,
            "content_checksum": "sha256:state-q-only",
            "authority_status": "current",
            "confirmation_status": "confirmed",
            "confirmed_by": "user",
            "session_input_revision": 5,
            "created_at": "2026-09-07T01:04:00Z",
        }
    )

    bundle = build_confirmed_agent1_input(
        state,
        document_input=None,
        document_facts=[],
        questionnaire_result=_questionnaire_result().model_copy(
            update={"input_mode": "without_document", "entry_requirement": "required"}
        ),
    )

    assert bundle.document_ids == ()
    assert bundle.facts
