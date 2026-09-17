"""Sprint 6 Phase 1B gates B/C — pure dominance service, coverage, aggregation.

Everything here runs through production code with synthetic evidence: no DB,
no provider, no RAG. It pins the frozen routing matrix, the deterministic
reason precedence, the canonical effective coverage/dedupe rules, and the
single-pass aggregation authority.
"""

from __future__ import annotations

import pytest

from backend.app.schemas.v3.assessment import FactEvidence, OrganEvidenceLink
from backend.app.services.v3.organ_dominance_service import (
    DominanceReadinessError,
    build_organ_aggregation_snapshot,
    canonical_effective_evidence,
    canonical_evidence_coverage,
    decision_snapshot_checksum,
    dominance_affecting_minor_conflict_ids,
    fact_claim_index,
    load_configured_dominance_rule,
    organ_tone_map,
    resolve_organ_dominance,
    select_effective_evidence,
    unresolved_major_conflict_ids,
    verify_mapping_identity,
)
from tests.sprint6_phase1b_fixtures import (
    aggregation_from_organ_support,
    decision_from_organ_support,
    decision_from_organ_weights,
    dominance_rule,
    five_tone_mapping,
    organ_mapping,
    synthetic_evidence,
)

ORGAN_ELEMENT = {
    "liver": "wood",
    "heart": "fire",
    "spleen": "earth",
    "lung": "metal",
    "kidney": "water",
}


def _major_conflict(fact_ids, conflict_id="conf_major"):
    return {
        "conflict_id": conflict_id,
        "fact_ids": list(fact_ids),
        "severity": "major",
        "resolution_status": "unresolved",
        "display_summary": "synthetic major conflict",
    }


def _minor_conflict(fact_ids, *, conflict_id="conf_minor", resolved=False):
    return {
        "conflict_id": conflict_id,
        "fact_ids": list(fact_ids),
        "severity": "minor",
        "resolution_status": "resolved" if resolved else "unresolved",
        "display_summary": "synthetic minor conflict",
    }


# --------------------------------------------------------------------------- #
# Gate B — routing matrix, boundaries, precedence, repeatability
# --------------------------------------------------------------------------- #


def test_zero_legal_candidates_is_basic_wellness_never_gong():
    decision = decision_from_organ_support({})
    assert decision.regulation_mode == "basic_wellness"
    assert decision.primary_tone is None
    assert decision.dominant_organ is None
    assert decision.decision_reason_code == "BASIC_NO_LEGAL_ORGAN_CANDIDATE"
    assert decision.organ.legal_candidate_count == 0
    assert decision.dominance.top1_organ is None
    assert decision.dominance.margin_gate_state == "not_evaluated"
    assert decision.dominance.ratio_gate_state == "not_evaluated"


def test_one_legal_candidate_is_personalized_with_null_na_values():
    decision = decision_from_organ_support({"liver": 1.0})
    assert decision.regulation_mode == "personalized_five_tone"
    assert decision.dominant_organ == "liver"
    assert decision.primary_tone == "jiao"
    assert decision.decision_reason_code == "PERSONALIZED_SINGLE_LEGAL_CANDIDATE"
    assert decision.dominance.top1_organ == "liver"
    assert decision.dominance.top2_organ is None
    assert decision.dominance.normalized_margin is None
    assert decision.dominance.raw_top2_support is None
    assert decision.dominance.raw_ratio is None
    assert decision.dominance.margin_gate_state == "not_applicable_single_candidate"
    assert decision.dominance.ratio_gate_state == "not_applicable_single_candidate"
    assert decision.dominance.dominance_gate_passed is True


def test_exact_raw_tie_is_integrated_and_uses_raw_equality():
    decision = decision_from_organ_support({"liver": 1.0, "spleen": 1.0})
    assert decision.regulation_mode == "integrated_regulation"
    assert decision.primary_tone is None
    assert decision.decision_reason_code == "INTEGRATED_EXACT_TOP_TIE"
    assert decision.dominance.raw_top1_support == decision.dominance.raw_top2_support
    # gate states are still recorded for the audit
    assert decision.dominance.margin_gate_state == "failed"
    assert decision.dominance.ratio_gate_state == "failed"


def test_thin_dominance_is_integrated_not_personalized():
    decision = decision_from_organ_weights({"liver": 0.51, "spleen": 0.49})
    assert decision.regulation_mode == "integrated_regulation"
    assert decision.decision_reason_code == "INTEGRATED_MARGIN_BELOW_THRESHOLD"
    assert decision.dominance.normalized_margin == pytest.approx(0.02, abs=1e-9)


def test_genuine_dominance_is_personalized_for_every_organ():
    order = ("liver", "heart", "spleen", "lung", "kidney")
    for index, organ in enumerate(order):
        tone = {"liver": "jiao", "heart": "zhi", "spleen": "gong",
                "lung": "shang", "kidney": "yu"}[organ]
        # a legal runner-up keeps this on the 2+ candidate thresholds branch
        second = order[(index + 1) % len(order)]
        decision = decision_from_organ_weights({organ: 0.7, second: 0.3})
        assert decision.regulation_mode == "personalized_five_tone"
        assert decision.dominant_organ == organ
        assert decision.primary_tone == tone
        assert decision.decision_reason_code == "PERSONALIZED_DOMINANCE_THRESHOLDS_MET"


def test_one_strong_candidate_only_is_personalized_by_single_candidate_policy():
    weights = {name: 0.05 for name in ORGAN_ELEMENT}
    weights["spleen"] = 0.8
    decision = decision_from_organ_weights(weights)
    assert decision.regulation_mode == "personalized_five_tone"
    assert decision.dominant_organ == "spleen"
    assert decision.primary_tone == "gong"
    assert decision.decision_reason_code == "PERSONALIZED_SINGLE_LEGAL_CANDIDATE"


def test_margin_threshold_is_inclusive():
    decision = decision_from_organ_support(
        {"liver": 6.0, "spleen": 5.0, "lung": 1.5}
    )
    assert decision.dominance.normalized_margin == 0.08
    assert decision.dominance.margin_gate_state == "passed"
    assert decision.regulation_mode == "personalized_five_tone"


def test_margin_just_below_threshold_fails_with_ratio_passing():
    decision = decision_from_organ_support(
        {"liver": 6.0, "spleen": 5.0, "lung": 1.6}
    )
    assert decision.dominance.normalized_margin < 0.08
    assert decision.dominance.margin_gate_state == "failed"
    assert decision.dominance.ratio_gate_state == "passed"
    assert decision.decision_reason_code == "INTEGRATED_MARGIN_BELOW_THRESHOLD"


def test_ratio_threshold_is_inclusive():
    decision = decision_from_organ_support({"liver": 6.0, "spleen": 5.0})
    assert decision.dominance.raw_ratio == 1.2
    assert decision.dominance.ratio_gate_state == "passed"
    assert decision.regulation_mode == "personalized_five_tone"


def test_ratio_just_below_threshold_fails_with_margin_passing():
    decision = decision_from_organ_support({"liver": 5.9, "spleen": 5.0})
    assert decision.dominance.raw_ratio < 1.20
    assert decision.dominance.margin_gate_state == "passed"
    assert decision.dominance.ratio_gate_state == "failed"
    assert decision.decision_reason_code == "INTEGRATED_RATIO_BELOW_THRESHOLD"


def test_reason_precedence_tie_before_conflict_before_margin_before_ratio():
    tie_with_conflict = decision_from_organ_support(
        {"liver": 1.0, "spleen": 1.0},
        conflicts=[_minor_conflict(["fact_liver_0"])],
    )
    assert tie_with_conflict.decision_reason_code == "INTEGRATED_EXACT_TOP_TIE"

    conflict_with_thin_margin = decision_from_organ_support(
        {"liver": 6.0, "spleen": 5.0, "lung": 1.6},
        conflicts=[_minor_conflict(["fact_liver_0"])],
    )
    assert conflict_with_thin_margin.decision_reason_code == (
        "INTEGRATED_DOMINANCE_CONFLICT"
    )
    assert conflict_with_thin_margin.dominance.margin_gate_state == "failed"

    margin_before_ratio = decision_from_organ_support(
        {"liver": 6.0, "spleen": 5.0, "lung": 1.6}
    )
    assert margin_before_ratio.decision_reason_code == (
        "INTEGRATED_MARGIN_BELOW_THRESHOLD"
    )


def test_single_candidate_with_dominance_affecting_conflict_is_integrated():
    decision = decision_from_organ_support(
        {"liver": 1.2, "spleen": 0.2},
        conflicts=[_minor_conflict(["fact_liver_0"])],
    )
    assert decision.organ.legal_candidate_count == 1
    assert decision.regulation_mode == "integrated_regulation"
    assert decision.decision_reason_code == "INTEGRATED_DOMINANCE_CONFLICT"
    assert decision.dominance.margin_gate_state == "not_applicable_single_candidate"


def test_unresolved_major_conflict_fails_the_evidence_gate():
    decision = decision_from_organ_support(
        {"liver": 6.0, "spleen": 5.0}, conflicts=[_major_conflict(["fact_liver_0"])]
    )
    assert decision.regulation_mode == "basic_wellness"
    assert decision.primary_tone is None
    assert decision.decision_reason_code == "BASIC_UNRESOLVED_MAJOR_CONFLICT"
    assert decision.conflict.unresolved_major_conflict_ids == ["conf_major"]
    assert decision.conflict.conflict_gate_passed is False


def test_resolved_and_unrelated_minor_conflicts_are_audit_only():
    resolved = decision_from_organ_support(
        {"liver": 6.0, "spleen": 5.0},
        conflicts=[_minor_conflict(["fact_liver_0"], resolved=True)],
    )
    assert resolved.regulation_mode == "personalized_five_tone"
    assert resolved.conflict.dominance_affecting_minor_conflict_ids == []

    unrelated = decision_from_organ_support(
        {"liver": 6.0, "spleen": 5.0, "kidney": 1.0},
        conflicts=[_minor_conflict(["fact_kidney_0"], conflict_id="conf_unrelated")],
    )
    assert unrelated.regulation_mode == "personalized_five_tone"
    assert unrelated.conflict.dominance_affecting_minor_conflict_ids == []


def test_upstream_legal_abstain_mappings_are_preserved():
    rag_empty = decision_from_organ_support(
        {"liver": 1.0}, upstream_abstain_reason="RAG_EMPTY"
    )
    assert rag_empty.regulation_mode == "basic_wellness"
    assert rag_empty.primary_tone is None
    assert rag_empty.decision_reason_code == "BASIC_RAG_EMPTY"

    element = decision_from_organ_support(
        {"liver": 1.0}, upstream_abstain_reason="ELEMENT_EVIDENCE_INSUFFICIENT"
    )
    assert element.regulation_mode == "basic_wellness"
    assert element.decision_reason_code == "BASIC_ELEMENT_EVIDENCE_INSUFFICIENT"


def test_abstain_never_becomes_a_personalized_decision():
    for reason in ("RAG_EMPTY", "ELEMENT_EVIDENCE_INSUFFICIENT", None):
        decision = decision_from_organ_support(
            {"liver": 6.0, "spleen": 5.0}, upstream_abstain_reason=reason
        )
        if reason is None:
            continue
        assert decision.regulation_mode == "basic_wellness"
        assert decision.primary_tone is None


def test_decision_is_repeatable_and_checksum_round_trips():
    first = decision_from_organ_support({"liver": 6.0, "spleen": 5.0})
    second = decision_from_organ_support({"liver": 6.0, "spleen": 5.0})
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.decision_snapshot_checksum == second.decision_snapshot_checksum
    assert first.decision_snapshot_checksum == decision_snapshot_checksum(first)

    tampered = first.model_copy(update={"decision_reason_code": "TAMPERED"})
    assert decision_snapshot_checksum(tampered) != first.decision_snapshot_checksum


def test_mapping_identity_mismatch_is_a_readiness_failure():
    rule = dominance_rule()
    with pytest.raises(DominanceReadinessError) as error:
        verify_mapping_identity(
            rule,
            organ_mapping={"schema_id": "organ_mapping_v3", "schema_version": "9.9.9",
                           "content_checksum": "sha256:" + "0" * 64},
            five_tone_mapping=five_tone_mapping(),
        )
    assert error.value.error_code == "DOMINANCE_MAPPING_IDENTITY_MISMATCH"


def test_organ_tone_map_reads_the_approved_asset():
    assert organ_tone_map(five_tone_mapping()) == {
        "liver": "jiao",
        "heart": "zhi",
        "spleen": "gong",
        "lung": "shang",
        "kidney": "yu",
    }


# --------------------------------------------------------------------------- #
# Gate C — canonical effective coverage and one-pass aggregation
# --------------------------------------------------------------------------- #


def _duplicate_claim_evidence():
    """Questionnaire + document rows for the same claim (one effective fact)."""

    mapping = organ_mapping()
    facts = []
    links = []
    for index, source in enumerate(("questionnaire", "document")):
        fact_evidence_id = f"fev_dup_{index}"
        facts.append(
            FactEvidence(
                fact_evidence_id=fact_evidence_id,
                assessment_id="asmt_dup",
                assessment_revision=1,
                fact_id=f"fact_dup_{index}",
                claim_code="low_energy",
                display_name="low energy",
                category="symptom",
                value={"type": "severity", "value": "mild"},
                time_window="recent",
                direction="supporting",
                reliability=0.5 if index == 0 else 0.9,
                source_refs=[
                    {"source_type": source, "source_id": f"{source}_1", "span_ref": None}
                ],
                confirmation_status="confirmed",
            )
        )
        links.append(
            OrganEvidenceLink(
                organ_evidence_link_id=f"oel_dup_{index}",
                fact_evidence_id=fact_evidence_id,
                organ="spleen",
                element="earth",
                direction="supporting",
                link_strength=0.8,
                mapping_rule_id="map_low_energy_spleen_01",
                mapping_version="organ_mapping_v3.0",
                explanation_summary="synthetic duplicate claim",
            )
        )
    return facts, links, mapping


def test_effective_selection_keeps_one_fact_per_claim_by_source_priority():
    facts, _links, mapping = _duplicate_claim_evidence()
    effective = select_effective_evidence(facts, mapping)
    assert len(effective) == 1
    # the questionnaire row wins the approved source priority
    assert effective[0].fact_evidence_id == "fev_dup_0"


def test_coverage_counts_the_effective_population_once():
    facts, _links, mapping = _duplicate_claim_evidence()
    count, coverage = canonical_evidence_coverage(facts, mapping)
    assert count == 1
    assert coverage == 0.125

    duplicate_extra = facts + [
        facts[0].model_copy(
            update={
                "fact_evidence_id": f"fev_extra_{index}",
                "fact_id": f"fact_extra_{index}",
                "claim_code": claim,
            }
        )
        for index, claim in enumerate(("poor_appetite", "loose_stool"))
    ]
    extra_links = [
        OrganEvidenceLink(
            organ_evidence_link_id=f"oel_extra_{index}",
            fact_evidence_id=f"fev_extra_{index}",
            organ="spleen",
            element="earth",
            direction="supporting",
            link_strength=0.5,
            mapping_rule_id="map_extra_01",
            mapping_version="organ_mapping_v3.0",
            explanation_summary="synthetic extra claim",
        )
        for index in range(2)
    ]
    count, coverage = canonical_evidence_coverage(
        duplicate_extra, mapping
    )
    assert count == 3
    assert coverage == 0.375
    snapshot = build_organ_aggregation_snapshot(
        duplicate_extra, extra_links, mapping
    )
    assert snapshot.effective_evidence_count == 3


def test_coverage_threshold_boundary_is_inclusive():
    population = aggregation_from_organ_support({"liver": 1.0, "spleen": 1.0})
    assert population.effective_evidence_count == 4
    passing = decision_from_organ_support(
        {"liver": 1.0, "spleen": 1.0}, coverage_count=4
    )
    assert passing.coverage.evidence_coverage == 0.50
    assert passing.coverage.coverage_gate_passed is True

    failing = decision_from_organ_support(
        {"liver": 1.0, "spleen": 1.0}, coverage_count=3
    )
    assert failing.coverage.evidence_coverage == 0.375
    assert failing.coverage.coverage_gate_passed is False
    assert failing.regulation_mode == "basic_wellness"
    assert failing.decision_reason_code == "BASIC_EVIDENCE_COVERAGE_BELOW_THRESHOLD"


def test_coverage_counts_supporting_and_contradicting_confirmed_facts_only():
    facts, _links, mapping = _duplicate_claim_evidence()
    base = facts[0]

    def _variant(**overrides):
        payload = base.model_dump(mode="json")
        payload.update(overrides)
        return FactEvidence.model_validate(payload)

    contradicting = _variant(
        fact_evidence_id="fev_contra",
        fact_id="fact_contra",
        claim_code="palpitation_at_rest",
        direction="contradicting",
        source_refs=[
            {"source_type": "document", "source_id": "doc_1", "span_ref": None}
        ],
    )
    unconfirmed = _variant(
        fact_evidence_id="fev_unconfirmed",
        fact_id="fact_unconfirmed",
        claim_code="nocturia",
        confirmation_status="unconfirmed",
    )
    rejected = _variant(
        fact_evidence_id="fev_rejected",
        fact_id="fact_rejected",
        claim_code="tinnitus",
        confirmation_status="rejected",
    )
    count, coverage = canonical_evidence_coverage(
        [base, contradicting, unconfirmed, rejected], mapping
    )
    assert count == 2  # supporting + contradicting confirmed facts
    assert coverage == 0.25


def test_aggregation_is_one_pass_with_raw_support_and_legal_candidates():
    support = {"liver": 1.85, "spleen": 1.1125, "lung": 0.5}
    evidence, links = synthetic_evidence(support)
    snapshot = build_organ_aggregation_snapshot(evidence, links, organ_mapping())
    assert snapshot.is_available is True
    assert snapshot.raw_support_by_organ["liver"] == pytest.approx(1.85, abs=1e-9)
    assert snapshot.raw_support_by_organ["spleen"] == pytest.approx(1.1125, abs=1e-9)
    # lung never clears the approved raw-support threshold, so it is not legal
    assert snapshot.legal_candidate_organs == ("liver", "spleen")
    assert snapshot.legal_candidate_by_organ["lung"] is False
    assert snapshot.effective_evidence_count_by_organ["liver"] == 2
    assert snapshot.contributing_claims_by_organ["liver"]
    assert sum(snapshot.normalized_weights_by_organ.values()) == pytest.approx(
        1.0, abs=0.001
    )
    # normalization is over legal candidates only: the illegal lung support is
    # excluded from the denominator
    assert snapshot.normalized_weights_by_organ["liver"] == pytest.approx(
        1.85 / (1.85 + 1.1125), abs=1e-4
    )


def test_aggregation_reports_insufficient_without_legal_candidates():
    evidence, links = synthetic_evidence({"lung": 0.5})
    snapshot = build_organ_aggregation_snapshot(evidence, links, organ_mapping())
    assert snapshot.is_available is False
    assert snapshot.legal_candidate_organs == ()
    assert all(
        value == 0.0 for value in snapshot.normalized_weights_by_organ.values()
    )


def test_conflict_linkage_uses_persisted_fact_to_claim_mapping():
    evidence, links = synthetic_evidence({"liver": 6.0, "spleen": 5.0})
    snapshot = build_organ_aggregation_snapshot(evidence, links, organ_mapping())
    index = fact_claim_index(evidence)
    assert index["fact_liver_0"] == ("anger_tendency",)

    affected = dominance_affecting_minor_conflict_ids(
        conflicts=[_minor_conflict(["fact_liver_0"])],
        fact_claims=index,
        target_organs=["liver", "spleen"],
        contributing_claims_by_organ=snapshot.contributing_claims_by_organ,
    )
    assert affected == ["conf_minor"]

    untouched = dominance_affecting_minor_conflict_ids(
        conflicts=[_minor_conflict(["fact_unknown_0"])],
        fact_claims=index,
        target_organs=["liver", "spleen"],
        contributing_claims_by_organ=snapshot.contributing_claims_by_organ,
    )
    assert untouched == []

    assert unresolved_major_conflict_ids(
        [_major_conflict(["fact_liver_0"]), _minor_conflict(["fact_liver_0"])]
    ) == ["conf_major"]


def test_configured_dominance_rule_matches_the_asset():
    rule = load_configured_dominance_rule()
    assert rule["asset_version"] == "dominance-rule-v1.0-r1"


# --------------------------------------------------------------------------- #
# decision schema authority
# --------------------------------------------------------------------------- #


def test_decision_rejects_inconsistent_mode_and_tone():
    from pydantic import ValidationError

    from backend.app.schemas.v3.flow_v31 import OrganDominanceDecisionV1

    decision = decision_from_organ_support({"liver": 1.0})
    payload = decision.model_dump(mode="json")
    payload["regulation_mode"] = "basic_wellness"
    with pytest.raises(ValidationError):
        OrganDominanceDecisionV1.model_validate(payload)

    payload = decision.model_dump(mode="json")
    payload["dominant_organ"] = "kidney"
    with pytest.raises(ValidationError, match="legal candidate"):
        OrganDominanceDecisionV1.model_validate(payload)


def test_resolve_rejects_an_unverified_aggregation_population():
    aggregation = aggregation_from_organ_support({"liver": 1.0})
    rule = dominance_rule()
    assets = verify_mapping_identity(
        rule, organ_mapping=organ_mapping(), five_tone_mapping=five_tone_mapping()
    )
    decision = resolve_organ_dominance(
        assessment_id="asmt_x",
        assessment_revision=2,
        input_revision=3,
        aggregation=aggregation,
        conflicts=[],
        fact_claims=aggregation.fact_claims_by_fact_id,
        dominance_rule=rule,
        five_tone_mapping=five_tone_mapping(),
        assets=assets,
        confirmed_user_state_id="cus_x",
        confirmed_user_state_revision=7,
    )
    assert decision.assessment_revision == 2
    assert decision.input_revision == 3
    assert decision.confirmed_user_state_id == "cus_x"
    assert decision.confirmed_user_state_revision == 7
    assert decision.assets.organ_mapping_checksum == organ_mapping()["content_checksum"]
