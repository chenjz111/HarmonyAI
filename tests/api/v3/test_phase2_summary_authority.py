"""Sprint 6 Phase 2 — Summary Authority (Option B) contract tests.

Owner decisions under test:

* D1 remove = ``rejected`` on the current revision;
* D2 contradicting/negated evidence survives narrative edits;
* D3 text cannot re-authorize rejected/unconfirmed evidence;
* D4 provider/diagnosis authority derives from structured confirmed evidence;
* D5 an explicit zero-confirmed-evidence revision is allowed;
* D6 the old full-text-only UX freeze is superseded;
* D7 no text reconciliation / NLU is used anywhere.

Everything is provider-free and runs over the in-memory SQLite fixture.
"""

from __future__ import annotations

import json
import uuid

import pytest

from backend.app.models.v3.assessment import AssessmentRevisionV3
from backend.app.models.v3.assessment import FactEvidence as FactEvidenceRow
from backend.app.services.v3.assessment_service import load_revision_evidence
from backend.app.services.v3.knowledge_assets import (
    load_five_tone_mapping,
    load_organ_mapping,
)
from backend.app.services.v3.organ_dominance_service import (
    build_organ_aggregation_snapshot,
    load_configured_dominance_rule,
    resolve_organ_dominance,
    select_effective_evidence,
    verify_candidate_policy_consistency,
    verify_mapping_identity,
)
from tests.api.v3.test_assessment_summary_authority import (
    client,
    create_summary_assessment,
    _v3_data,
)
from tests.api.v3.test_assessment_v3 import _guest_headers
from tests.api.v3.test_diagnosis_dominance_routing import (
    _create_questionnaire_assessment,
    _frozen_case_answers,
    _seed_questionnaire_state,
)
from tests.api.v3.test_diagnosis_v3 import _setup_flow_session
from tests.api.v3.test_understanding_ai_extraction import (
    _confirm as _confirm_understanding,
    _document_source,
    _mock_chain,
    _post as _post_understanding,
    _seed_document,
    _setup_guest as _setup_understanding_guest,
    _user_pk,
)
from backend.app.services.v3 import understanding_service

MODES = ["document", "questionnaire", "combined"]


def _statuses(payload):
    return {
        item["fact_evidence_id"]: item["confirmation_status"]
        for item in payload["fact_evidence"]
    }


def _status_change(item, new_value):
    return {
        "target_type": "fact_evidence",
        "target_id": item["fact_evidence_id"],
        "field": "confirmation_status",
        "old_value": item["confirmation_status"],
        "new_value": new_value,
    }


def _confirm(
    headers,
    assessment_id,
    *,
    expected_revision,
    expected_input_revision,
    changes=None,
    text=None,
):
    body = {
        "expected_revision": expected_revision,
        "expected_input_revision": expected_input_revision,
        "decision": "confirm_with_changes",
        "changes": changes or [],
    }
    if text is not None:
        body["edited_summary_text"] = text
    return client.post(
        f"/api/v3/assessments/{assessment_id}/confirmations",
        headers=headers,
        json=body,
    )


def _seed_severity_row(db_session_factory, *, assessment_id, claim_code):
    """Seed one approved severity-valued row into the current revision.

    The approved questionnaire/provider fixtures only emit ``frequency_0_4`` and
    ``multi_choice_evidence`` values, so the preserved severity-edit path needs
    one real persisted severity row to be exercised end to end.
    """

    from backend.app.models.v3.understanding import FactSourceRef, NormalizedFact

    suffix = uuid.uuid4().hex
    row_id = f"sev_{suffix}"
    with db_session_factory() as db:
        db.add(
            NormalizedFact(
                fact_row_id=row_id,
                fact_id=f"fact_{suffix}",
                owner_type="understanding",
                understanding_id=f"und_{suffix}",
                understanding_revision=1,
                questionnaire_submission_id=None,
                fact_code=claim_code,
                category="somatic",
                display_name="食欲不振",
                value_json={"type": "severity", "value": "mild"},
                time_window="past_7_days",
                negated=0,
                subject="self",
                confirmation_status="confirmed",
                extraction_method="deterministic_questionnaire_mapping",
                extraction_confidence=0.8,
            )
        )
        db.add(
            FactSourceRef(
                fact_row_id=row_id,
                source_type="questionnaire",
                source_id=f"q_{suffix}",
                span_ref=None,
            )
        )
        db.add(
            FactEvidenceRow(
                fact_evidence_row_id=f"fer_{suffix}",
                fact_evidence_id=f"fev_{suffix}",
                assessment_id=assessment_id,
                assessment_revision=1,
                normalized_fact_row_id=row_id,
                claim_code=claim_code,
                category="somatic",
                display_name="食欲不振",
                value_json={"type": "severity", "value": "mild"},
                time_window="past_7_days",
                direction="supporting",
                reliability=0.8,
                confirmation_status="confirmed",
            )
        )
        db.commit()


def _questionnaire_assessment(db_session_factory, case_id="F"):
    """The real questionnaire source of a ConfirmedUserState (provider-free)."""

    headers = _guest_headers()
    db = db_session_factory()
    session_id, _user_pk, session_row = _setup_flow_session(db, headers)
    questionnaire_id, manifest = _seed_questionnaire_state(
        db,
        headers,
        session_id=session_id,
        session_row=session_row,
        answers=_frozen_case_answers(case_id),
    )
    db.close()
    assessment_id = _create_questionnaire_assessment(
        headers, session_id, questionnaire_id, manifest
    )
    created = _v3_data(
        client.get(f"/api/v3/assessments/{assessment_id}", headers=headers)
    )
    return headers, assessment_id, created


# --------------------------------------------------------------------------- #
# P2-S1 — paraphrase
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("mode", MODES)
def test_p2_s1_paraphrase_never_changes_structured_status(
    monkeypatch, db_session_factory, mode
):
    headers, _, original = create_summary_assessment(
        monkeypatch, db_session_factory, mode
    )
    before = _statuses(original)
    response = _confirm(
        headers,
        original["assessment_id"],
        expected_revision=1,
        expected_input_revision=original["input_revision"],
        text="最近的状态和资料里写的不太一样，我也说不太清楚。",
    )
    assert response.status_code == 201, response.text
    current = _v3_data(response)
    assert _statuses(current) == before
    assert current["presentation"]["summary"] == (
        "最近的状态和资料里写的不太一样，我也说不太清楚。"
    )
    # D4: the authoritative state text is the projection, not the narrative.
    assert current["state_summary"] != current["presentation"]["summary"]
    assert current["state_summary"].startswith("已确认的近期状态：")


# --------------------------------------------------------------------------- #
# P2-S2 — explicit reject
# --------------------------------------------------------------------------- #


def test_p2_s2_explicit_reject_copies_every_row_and_excludes_the_target(
    monkeypatch, db_session_factory
):
    headers, _, original = create_summary_assessment(
        monkeypatch, db_session_factory, "combined"
    )
    target = original["fact_evidence"][0]
    response = _confirm(
        headers,
        original["assessment_id"],
        expected_revision=1,
        expected_input_revision=original["input_revision"],
        changes=[_status_change(target, "rejected")],
    )
    assert response.status_code == 201, response.text
    current = _v3_data(response)
    assert current["revision"] == 2
    # every current row is copied: reject never deletes evidence
    assert len(current["fact_evidence"]) == len(original["fact_evidence"])
    assert {i["fact_evidence_id"] for i in current["fact_evidence"]} == set(
        _statuses(original)
    )
    assert current["fact_evidence"] and (
        next(
            i
            for i in current["fact_evidence"]
            if i["fact_evidence_id"] == target["fact_evidence_id"]
        )["confirmation_status"]
        == "rejected"
    )
    assert {
        i["confirmation_status"]
        for i in current["fact_evidence"]
        if i["fact_evidence_id"] != target["fact_evidence_id"]
    } == {"confirmed"}

    with db_session_factory() as db:
        confirmed, _links = load_revision_evidence(
            db,
            assessment_id=original["assessment_id"],
            revision=2,
            confirmed_only=True,
        )
        every, _links_all = load_revision_evidence(
            db,
            assessment_id=original["assessment_id"],
            revision=2,
            confirmed_only=False,
        )
        old_rows = (
            db.query(FactEvidenceRow)
            .filter_by(
                assessment_id=original["assessment_id"], assessment_revision=1
            )
            .all()
        )
    assert target["fact_evidence_id"] not in {
        item.fact_evidence_id for item in confirmed
    }
    assert target["fact_evidence_id"] in {item.fact_evidence_id for item in every}
    # the old revision is immutable
    assert {row.confirmation_status for row in old_rows} == {"confirmed"}


# --------------------------------------------------------------------------- #
# P2-S3 — narrative negation
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("mode", MODES)
def test_p2_s3_narrative_negation_changes_no_structured_status(
    monkeypatch, db_session_factory, mode
):
    headers, _, original = create_summary_assessment(
        monkeypatch, db_session_factory, mode
    )
    before = _statuses(original)
    response = _confirm(
        headers,
        original["assessment_id"],
        expected_revision=1,
        expected_input_revision=original["input_revision"],
        text="近日无明显耳鸣，也没有胁肋不适，睡眠尚可。",
    )
    assert response.status_code == 201, response.text
    current = _v3_data(response)
    # D3: nothing is promoted, nothing is dropped, nothing is re-scored by text.
    assert _statuses(current) == before
    assert len(current["fact_evidence"]) == len(before)
    assert current["organ_profile"] == original["organ_profile"]
    assert current["evidence_coverage"] == original["evidence_coverage"]
    assert current["conflicts"] == original["conflicts"]


# --------------------------------------------------------------------------- #
# P2-S4 — duplicate claims from two sources
# --------------------------------------------------------------------------- #


def test_p2_s4_duplicate_claims_keep_distinct_identities(
    monkeypatch, db_session_factory
):
    headers, _, original = create_summary_assessment(
        monkeypatch, db_session_factory, "combined"
    )
    duplicates = [
        item
        for item in original["fact_evidence"]
        if item["claim_code"] == "flank_discomfort"
    ]
    assert len(duplicates) == 2, "combined mode must produce the same claim twice"
    assert len({item["fact_evidence_id"] for item in duplicates}) == 2
    document_side = next(
        item
        for item in duplicates
        if not any(
            ref["source_type"] == "questionnaire" for ref in item["source_refs"]
        )
    )
    response = _confirm(
        headers,
        original["assessment_id"],
        expected_revision=1,
        expected_input_revision=original["input_revision"],
        changes=[_status_change(document_side, "rejected")],
    )
    assert response.status_code == 201, response.text
    current = _v3_data(response)
    by_id = {item["fact_evidence_id"]: item for item in current["fact_evidence"]}
    assert by_id[document_side["fact_evidence_id"]]["confirmation_status"] == "rejected"
    questionnaire_side = next(
        item
        for item in duplicates
        if item["fact_evidence_id"] != document_side["fact_evidence_id"]
    )
    # the explicit decision targets exactly one stable id
    assert by_id[questionnaire_side["fact_evidence_id"]][
        "confirmation_status"
    ] == "confirmed"

    with db_session_factory() as db:
        evidence, _links = load_revision_evidence(
            db,
            assessment_id=original["assessment_id"],
            revision=2,
            confirmed_only=True,
        )
    # approved source priority is unchanged: the questionnaire row still wins
    effective = select_effective_evidence(evidence, load_organ_mapping())
    flank = [item for item in effective if item.claim_code == "flank_discomfort"]
    assert len(flank) == 1
    assert any(
        ref.source_type == "questionnaire" for ref in flank[0].source_refs
    )


# --------------------------------------------------------------------------- #
# P2-S5 — contradiction
# --------------------------------------------------------------------------- #


def test_p2_s5_conflict_survives_narrative_and_recomputes_on_reject(
    monkeypatch, db_session_factory
):
    headers, _, original = create_summary_assessment(
        monkeypatch, db_session_factory, "combined"
    )
    assert original["conflicts"], "combined mode must expose the cross-source conflict"
    conflict_ids = {item["conflict_id"] for item in original["conflicts"]}

    narrative = _confirm(
        headers,
        original["assessment_id"],
        expected_revision=1,
        expected_input_revision=original["input_revision"],
        text="近期状态一般。",
    )
    assert narrative.status_code == 201, narrative.text
    after_text = _v3_data(narrative)
    # D2: a text-only edit preserves the conflict population exactly
    assert {item["conflict_id"] for item in after_text["conflicts"]} == conflict_ids

    member_fact_ids = set(original["conflicts"][0]["fact_ids"])
    members = [
        item
        for item in after_text["fact_evidence"]
        if item["fact_id"] in member_fact_ids
    ]
    assert len(members) >= 2
    rejected = _confirm(
        headers,
        original["assessment_id"],
        expected_revision=after_text["revision"],
        expected_input_revision=original["input_revision"],
        changes=[_status_change(members[0], "rejected")],
    )
    assert rejected.status_code == 201, rejected.text
    after_reject = _v3_data(rejected)
    # the conflict is recomputed from the confirmed population only
    assert after_reject["conflicts"] == []


# --------------------------------------------------------------------------- #
# P2-S6 / P2-S12 — rejected and unconfirmed evidence is never text-reauthorized
# --------------------------------------------------------------------------- #


def test_p2_s6_and_s12_text_cannot_reauthorize_rejected_evidence(
    monkeypatch, db_session_factory
):
    headers, _, original = create_summary_assessment(
        monkeypatch, db_session_factory, "combined"
    )
    target = original["fact_evidence"][0]
    name = target["display_name"]
    rejected = _confirm(
        headers,
        original["assessment_id"],
        expected_revision=1,
        expected_input_revision=original["input_revision"],
        changes=[_status_change(target, "rejected")],
    )
    assert rejected.status_code == 201, rejected.text
    revision_two = _v3_data(rejected)
    assert _statuses(revision_two)[target["fact_evidence_id"]] == "rejected"

    # the narrative contains the rejected display name verbatim
    text_only = _confirm(
        headers,
        original["assessment_id"],
        expected_revision=2,
        expected_input_revision=original["input_revision"],
        text=f"资料中记录的近期状态：{name}。",
    )
    assert text_only.status_code == 201, text_only.text
    revision_three = _v3_data(text_only)
    assert _statuses(revision_three)[target["fact_evidence_id"]] == "rejected"

    # only an explicit structured decision may re-authorize it
    confirmed = _confirm(
        headers,
        original["assessment_id"],
        expected_revision=3,
        expected_input_revision=original["input_revision"],
        changes=[
            {
                "target_type": "fact_evidence",
                "target_id": target["fact_evidence_id"],
                "field": "confirmation_status",
                "old_value": "rejected",
                "new_value": "confirmed",
            }
        ],
    )
    assert confirmed.status_code == 201, confirmed.text
    revision_four = _v3_data(confirmed)
    assert _statuses(revision_four)[target["fact_evidence_id"]] == "confirmed"
    others = [
        item
        for item in revision_four["fact_evidence"]
        if item["fact_evidence_id"] != target["fact_evidence_id"]
    ]
    assert {item["confirmation_status"] for item in others} == {"confirmed"}


# --------------------------------------------------------------------------- #
# P2-S7 — questionnaire-only path
# --------------------------------------------------------------------------- #


def test_p2_s7_questionnaire_only_path_uses_the_same_contract(db_session_factory):
    headers, assessment_id, original = _questionnaire_assessment(db_session_factory)
    assert original["understanding_ref"] is None
    target = original["fact_evidence"][0]
    narrative = "最近只是有点累，睡不太好。"
    response = _confirm(
        headers,
        assessment_id,
        expected_revision=1,
        expected_input_revision=2,
        changes=[_status_change(target, "rejected")],
        text=narrative,
    )
    assert response.status_code == 201, response.text
    current = _v3_data(response)
    assert current["presentation"]["summary"] == narrative
    assert _statuses(current)[target["fact_evidence_id"]] == "rejected"
    assert {
        status
        for fact_id, status in _statuses(current).items()
        if fact_id != target["fact_evidence_id"]
    } == {"confirmed"}
    assert current["state_summary"].startswith("已确认的近期状态：")


# --------------------------------------------------------------------------- #
# P2-S8 — reject everything
# --------------------------------------------------------------------------- #


def test_p2_s8_reject_every_fact_is_a_valid_zero_evidence_revision(
    db_session_factory,
):
    headers, assessment_id, original = _questionnaire_assessment(db_session_factory)
    changes = [_status_change(item, "rejected") for item in original["fact_evidence"]]
    response = _confirm(
        headers,
        assessment_id,
        expected_revision=1,
        expected_input_revision=2,
        changes=changes,
    )
    assert response.status_code == 201, response.text
    current = _v3_data(response)
    assert current["revision"] == 2
    assert current["status"] == "confirmed"
    # every row is retained for audit, all structured statuses reflect the user
    assert len(current["fact_evidence"]) == len(original["fact_evidence"])
    assert {item["confirmation_status"] for item in current["fact_evidence"]} == {
        "rejected"
    }
    assert current["organ_profile"]["status"] == "insufficient"
    assert current["evidence_coverage"] == 0
    assert current["source_diversity"] == 0
    assert current["conflicts"] == []
    assert current["state_summary"] == "当前没有已确认的状态事实。"

    with db_session_factory() as db:
        evidence, links = load_revision_evidence(
            db, assessment_id=assessment_id, revision=2, confirmed_only=True
        )
        revision = (
            db.query(AssessmentRevisionV3)
            .filter_by(assessment_id=assessment_id, revision=2)
            .one()
        )
    assert evidence == []
    assert links == []
    organ_mapping = load_organ_mapping()
    tone_mapping = load_five_tone_mapping()
    rule = load_configured_dominance_rule()
    verify_candidate_policy_consistency(rule, organ_mapping=organ_mapping)
    snapshot = build_organ_aggregation_snapshot(evidence, links, organ_mapping)
    assert snapshot.is_available is False
    assert snapshot.legal_candidate_organs == ()
    decision = resolve_organ_dominance(
        assessment_id=assessment_id,
        assessment_revision=2,
        input_revision=2,
        aggregation=snapshot,
        conflicts=json.loads(revision.conflicts_json or "[]"),
        fact_claims=snapshot.fact_claims_by_fact_id,
        dominance_rule=rule,
        five_tone_mapping=tone_mapping,
        assets=verify_mapping_identity(
            rule, organ_mapping=organ_mapping, five_tone_mapping=tone_mapping
        ),
    )
    # D5: the frozen insufficiency path applies — never a fabricated tone
    assert decision.regulation_mode == "basic_wellness"
    assert decision.dominant_organ is None
    assert decision.primary_tone is None
    assert decision.decision_reason_code.startswith("BASIC_")


# --------------------------------------------------------------------------- #
# P2-S9 — revision 3
# --------------------------------------------------------------------------- #


def test_p2_s9_two_structured_edits_reach_revision_three(
    monkeypatch, db_session_factory
):
    headers, _, original = create_summary_assessment(
        monkeypatch, db_session_factory, "combined"
    )
    first, second = original["fact_evidence"][0], original["fact_evidence"][1]
    stable_ids = {item["fact_evidence_id"] for item in original["fact_evidence"]}

    edit_one = _confirm(
        headers,
        original["assessment_id"],
        expected_revision=1,
        expected_input_revision=original["input_revision"],
        changes=[_status_change(first, "rejected")],
    )
    assert edit_one.status_code == 201, edit_one.text
    revision_two = _v3_data(edit_one)
    edit_two = _confirm(
        headers,
        original["assessment_id"],
        expected_revision=2,
        expected_input_revision=original["input_revision"],
        changes=[_status_change(second, "rejected")],
        text="第二次修改的叙述文本。",
    )
    assert edit_two.status_code == 201, edit_two.text
    revision_three = _v3_data(edit_two)

    assert revision_three["revision"] == 3
    assert {item["fact_evidence_id"] for item in revision_three["fact_evidence"]} == stable_ids
    statuses = _statuses(revision_three)
    assert statuses[first["fact_evidence_id"]] == "rejected"
    assert statuses[second["fact_evidence_id"]] == "rejected"
    assert revision_three["presentation"]["summary"] == "第二次修改的叙述文本。"
    # no duplication
    assert len(revision_three["fact_evidence"]) == len(original["fact_evidence"])

    with db_session_factory() as db:
        rows = (
            db.query(FactEvidenceRow)
            .filter_by(assessment_id=original["assessment_id"])
            .all()
        )
    per_revision = {}
    for row in rows:
        per_revision.setdefault(row.assessment_revision, set()).add(
            row.fact_evidence_id
        )
    assert per_revision[1] == stable_ids
    assert per_revision[2] == stable_ids
    assert per_revision[3] == stable_ids
    # old revisions stay immutable and nothing is resurrected
    assert {row.confirmation_status for row in rows if row.assessment_revision == 1} == {
        "confirmed"
    }
    assert (
        next(
            row
            for row in rows
            if row.assessment_revision == 2
            and row.fact_evidence_id == first["fact_evidence_id"]
        ).confirmation_status
        == "rejected"
    )


# --------------------------------------------------------------------------- #
# P2-S10 — stale revision
# --------------------------------------------------------------------------- #


def test_p2_s10_stale_revision_is_rejected_without_partial_write(
    monkeypatch, db_session_factory
):
    headers, _, original = create_summary_assessment(
        monkeypatch, db_session_factory, "combined"
    )
    target = original["fact_evidence"][0]
    first = _confirm(
        headers,
        original["assessment_id"],
        expected_revision=1,
        expected_input_revision=original["input_revision"],
        changes=[_status_change(target, "rejected")],
    )
    assert first.status_code == 201, first.text

    stale = _confirm(
        headers,
        original["assessment_id"],
        expected_revision=1,
        expected_input_revision=original["input_revision"],
        changes=[_status_change(original["fact_evidence"][1], "rejected")],
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "REVISION_CONFLICT"

    current = _v3_data(
        client.get(f"/api/v3/assessments/{original['assessment_id']}", headers=headers)
    )
    assert current["revision"] == 2
    statuses = _statuses(current)
    assert statuses[target["fact_evidence_id"]] == "rejected"
    assert statuses[original["fact_evidence"][1]["fact_evidence_id"]] == "confirmed"


# --------------------------------------------------------------------------- #
# P2-S11 — narrative + structured change in one request
# --------------------------------------------------------------------------- #


def test_p2_s11_narrative_and_structured_change_in_one_request(
    monkeypatch, db_session_factory
):
    headers, _, original = create_summary_assessment(
        monkeypatch, db_session_factory, "combined"
    )
    target = original["fact_evidence"][0]
    narrative = "我重新写了一段描述，和上面的条目不完全一致。"
    response = _confirm(
        headers,
        original["assessment_id"],
        expected_revision=1,
        expected_input_revision=original["input_revision"],
        changes=[_status_change(target, "rejected")],
        text=narrative,
    )
    assert response.status_code == 201, response.text
    current = _v3_data(response)
    assert current["presentation"]["summary"] == narrative
    statuses = _statuses(current)
    assert statuses[target["fact_evidence_id"]] == "rejected"
    assert {
        status
        for fact_id, status in statuses.items()
        if fact_id != target["fact_evidence_id"]
    } == {"confirmed"}


# --------------------------------------------------------------------------- #
# Request-contract validation (fail closed)
# --------------------------------------------------------------------------- #


def test_p2_unknown_target_and_unsupported_values_fail_closed(
    monkeypatch, db_session_factory
):
    headers, _, original = create_summary_assessment(
        monkeypatch, db_session_factory, "combined"
    )
    target = original["fact_evidence"][0]

    unknown = _confirm(
        headers,
        original["assessment_id"],
        expected_revision=1,
        expected_input_revision=original["input_revision"],
        changes=[
            {
                "target_type": "fact_evidence",
                "target_id": "fev_does_not_exist",
                "field": "confirmation_status",
                "old_value": "confirmed",
                "new_value": "rejected",
            }
        ],
    )
    assert unknown.status_code == 409

    bad_status = _confirm(
        headers,
        original["assessment_id"],
        expected_revision=1,
        expected_input_revision=original["input_revision"],
        changes=[
            {
                "target_type": "fact_evidence",
                "target_id": target["fact_evidence_id"],
                "field": "confirmation_status",
                "old_value": target["confirmation_status"],
                "new_value": "unconfirmed",
            }
        ],
    )
    assert bad_status.status_code == 409

    stale_value = _confirm(
        headers,
        original["assessment_id"],
        expected_revision=1,
        expected_input_revision=original["input_revision"],
        changes=[
            {
                "target_type": "fact_evidence",
                "target_id": target["fact_evidence_id"],
                "field": "confirmation_status",
                "old_value": "rejected",
                "new_value": "confirmed",
            }
        ],
    )
    assert stale_value.status_code == 409

    unsupported_field = _confirm(
        headers,
        original["assessment_id"],
        expected_revision=1,
        expected_input_revision=original["input_revision"],
        changes=[
            {
                "target_type": "fact_evidence",
                "target_id": target["fact_evidence_id"],
                "field": "display_name",
                "old_value": target["display_name"],
                "new_value": "改写后的名称",
            }
        ],
    )
    assert unsupported_field.status_code == 409

    # no partial write from any rejected request
    current = _v3_data(
        client.get(f"/api/v3/assessments/{original['assessment_id']}", headers=headers)
    )
    assert current["revision"] == 1
    assert _statuses(current) == _statuses(original)


# --------------------------------------------------------------------------- #
# Understanding / uploaded-material path structured authority (D1/D3)
# --------------------------------------------------------------------------- #


def _uploaded_understanding(monkeypatch, db_session_factory):
    monkeypatch.setattr(
        understanding_service, "build_provider_chain", lambda: _mock_chain()
    )
    headers, session_id = _setup_understanding_guest()
    with db_session_factory() as db:
        document_id = _seed_document(
            db,
            user_pk=_user_pk(db, headers),
            session_id=session_id,
            ocr_text="睡眠后仍感疲惫。",
        )
    original = _v3_data(
        _post_understanding(headers, session_id, [_document_source(document_id)])
    )
    return headers, original


def _read_understanding(headers, understanding_id, revision=None):
    suffix = f"?revision={revision}" if revision is not None else ""
    return _v3_data(
        client.get(
            f"/api/v3/understandings/{understanding_id}{suffix}", headers=headers
        )
    )


def test_p2_understanding_structured_reject_copies_all_facts(
    monkeypatch, db_session_factory
):
    headers, original = _uploaded_understanding(monkeypatch, db_session_factory)
    fact = original["normalized_facts"][0]
    assert fact["confirmation_status"] == "unconfirmed"

    response = _confirm_understanding(
        headers,
        original["understanding_id"],
        decision="confirm_with_changes",
        changes=[
            {
                "target_type": "normalized_fact",
                "target_id": fact["fact_id"],
                "field": "confirmation_status",
                "old_value": "unconfirmed",
                "new_value": "rejected",
            }
        ],
    )
    assert response.status_code == 201, response.text
    result = _v3_data(response)
    assert result["affected_fact_ids"] == [fact["fact_id"]]

    latest = _read_understanding(headers, original["understanding_id"])
    assert [item["fact_id"] for item in latest["normalized_facts"]] == [
        item["fact_id"] for item in original["normalized_facts"]
    ]
    kept = latest["normalized_facts"][0]
    assert kept["confirmation_status"] == "rejected"
    # source refs are recreated for rejected rows too
    assert kept["source_refs"] == fact["source_refs"]

    previous = _read_understanding(headers, original["understanding_id"], revision=1)
    assert previous["normalized_facts"][0]["confirmation_status"] == "unconfirmed"


def test_p2_understanding_narrative_keeps_statuses_and_explicit_confirm_changes_only_target(
    monkeypatch, db_session_factory
):
    headers, original = _uploaded_understanding(monkeypatch, db_session_factory)
    fact = original["normalized_facts"][0]

    rejected = _confirm_understanding(
        headers,
        original["understanding_id"],
        decision="confirm_with_changes",
        changes=[
            {
                "target_type": "normalized_fact",
                "target_id": fact["fact_id"],
                "field": "confirmation_status",
                "old_value": "unconfirmed",
                "new_value": "rejected",
            }
        ],
    )
    assert rejected.status_code == 201, rejected.text

    # narrative mentions the rejected display name verbatim and changes nothing
    text_only = _confirm_understanding(
        headers,
        original["understanding_id"],
        decision="confirm_with_changes",
        expected_revision=2,
        edited_summary_text=f"资料中记录的近期状态：{fact['display_name']}。",
        reprocess_requested=True,
    )
    assert text_only.status_code == 201, text_only.text
    latest = _read_understanding(headers, original["understanding_id"])
    assert latest["normalized_facts"][0]["confirmation_status"] == "rejected"
    assert latest["case_summary"]["summary"] == (
        f"资料中记录的近期状态：{fact['display_name']}。"
    )

    # only an explicit structured decision re-authorizes it
    confirmed = _confirm_understanding(
        headers,
        original["understanding_id"],
        decision="confirm_with_changes",
        expected_revision=3,
        changes=[
            {
                "target_type": "normalized_fact",
                "target_id": fact["fact_id"],
                "field": "confirmation_status",
                "old_value": "rejected",
                "new_value": "confirmed",
            }
        ],
    )
    assert confirmed.status_code == 201, confirmed.text
    latest = _read_understanding(headers, original["understanding_id"])
    assert latest["normalized_facts"][0]["confirmation_status"] == "confirmed"


def test_p2_understanding_structured_changes_fail_closed(
    monkeypatch, db_session_factory
):
    headers, original = _uploaded_understanding(monkeypatch, db_session_factory)
    fact = original["normalized_facts"][0]
    base = {
        "target_type": "normalized_fact",
        "target_id": fact["fact_id"],
        "field": "confirmation_status",
        "old_value": "unconfirmed",
        "new_value": "confirmed",
    }

    unknown = _confirm_understanding(
        headers,
        original["understanding_id"],
        decision="confirm_with_changes",
        changes=[{**base, "target_id": "fact_missing"}],
    )
    assert unknown.status_code == 422
    assert unknown.json()["error"]["code"] == "FACT_NOT_FOUND"

    unsupported = _confirm_understanding(
        headers,
        original["understanding_id"],
        decision="confirm_with_changes",
        changes=[{**base, "field": "display_name", "new_value": "改写后的名称"}],
    )
    assert unsupported.status_code == 422
    assert unsupported.json()["error"]["code"] == "UNSUPPORTED_FIELD"

    invalid = _confirm_understanding(
        headers,
        original["understanding_id"],
        decision="confirm_with_changes",
        changes=[{**base, "new_value": "unconfirmed"}],
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "INVALID_VALUE"

    stale = _confirm_understanding(
        headers,
        original["understanding_id"],
        decision="confirm_with_changes",
        changes=[{**base, "old_value": "rejected"}],
    )
    assert stale.status_code == 422
    assert stale.json()["error"]["code"] == "FACT_STATUS_CONFLICT"

    # no partial write
    current = _read_understanding(headers, original["understanding_id"])
    assert current["normalized_facts"][0]["confirmation_status"] == "unconfirmed"


def test_p2_existing_severity_edit_still_supported(monkeypatch, db_session_factory):
    headers, _, original = create_summary_assessment(
        monkeypatch, db_session_factory, "combined"
    )
    severity_items = [
        item
        for item in original["fact_evidence"]
        if item["value"].get("type") == "severity"
    ]
    if not severity_items:
        # The approved questionnaire/provider fixtures only emit frequency and
        # multi-choice values, so seed one approved severity row to exercise the
        # preserved severity-edit path over the real API.
        _seed_severity_row(
            db_session_factory,
            assessment_id=original["assessment_id"],
            claim_code="poor_appetite",
        )
        original = _v3_data(
            client.get(
                f"/api/v3/assessments/{original['assessment_id']}", headers=headers
            )
        )
        severity_items = [
            item
            for item in original["fact_evidence"]
            if item["value"].get("type") == "severity"
        ]
    assert severity_items
    target = severity_items[0]
    new_value = "severe" if target["value"]["value"] != "severe" else "mild"
    response = _confirm(
        headers,
        original["assessment_id"],
        expected_revision=1,
        expected_input_revision=original["input_revision"],
        changes=[
            {
                "target_type": "fact_evidence",
                "target_id": target["fact_evidence_id"],
                "field": "severity",
                "old_value": target["value"]["value"],
                "new_value": new_value,
            }
        ],
    )
    assert response.status_code == 201, response.text
    current = _v3_data(response)
    updated = next(
        item
        for item in current["fact_evidence"]
        if item["fact_evidence_id"] == target["fact_evidence_id"]
    )
    assert updated["value"]["value"] == new_value
    assert updated["confirmation_status"] == "confirmed"
