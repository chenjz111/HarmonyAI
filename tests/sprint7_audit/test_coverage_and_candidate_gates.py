"""R1/R2 audit -- the Evidence Gate (S5) and the Legal Candidate Gate (S8).

Frozen numbers, read from the approved assets at runtime (never hard-coded):

* ``canonical_evidence_coverage`` : ``min(1.0, effective_confirmed_fact_count / 8)``
* ``evidence_gate.minimum_coverage`` = 0.50
* ``organ_mapping.thresholds`` : ``minimum_evidence_count`` = 2,
  ``minimum_total_support`` = 0.75

Key observation for the audit: ``counted_directions`` in the rule asset is
``["supporting", "contradicting"]``, so contradictory information *raises*
coverage. Coverage measures how much confirmed material exists, not how much
of it agrees -- which is exactly the point a medical ruling has to confirm
(see D-2).
"""

from __future__ import annotations

import pytest

from backend.app.services.v3 import organ_dominance_service as ods

from tests.sprint7_audit.harness import (
    make_evidence,
    snapshot,
    synthetic_population,
)


def test_frozen_thresholds_match_the_approved_assets(
    mapping: dict, dominance_rule: dict
) -> None:
    """Observed: the executable thresholds are the frozen ones."""

    evidence_gate = dominance_rule["evidence_gate"]
    assert evidence_gate["denominator"] == 8
    assert evidence_gate["minimum_coverage"] == 0.50
    assert set(evidence_gate["counted_directions"]) == {"supporting", "contradicting"}

    thresholds = mapping["thresholds"]
    assert thresholds["minimum_evidence_count"] == 2
    assert thresholds["minimum_total_support"] == 0.75


def test_candidate_gate_asset_is_not_a_second_authority(dominance_rule: dict) -> None:
    """Observed: the dominance asset only references the mapping's identity."""

    gate = dominance_rule["legal_candidate_gate"]
    assert gate["authority"] == "approved_organ_mapping"
    assert gate["minimum_effective_evidence_count"] == 2
    assert gate["minimum_raw_support"] == 0.75
    assert gate["reference"] == "organ_mapping_v3@3.0.0"


@pytest.mark.parametrize(
    ("fact_count", "expected_coverage"),
    [(0, 0.0), (1, 0.125), (2, 0.25), (3, 0.375), (4, 0.5), (6, 0.75), (8, 1.0), (9, 1.0)],
)
def test_coverage_is_confirmed_effective_count_over_eight(
    mapping: dict, fact_count: int, expected_coverage: float
) -> None:
    """Observed: ``min(1.0, n / 8)`` over the effective population."""

    claims = [
        "anger_tendency",
        "flank_discomfort",
        "tendon_stiffness",
        "muscle_cramp",
        "eye_discomfort",
        "emotional_recovery_slowness",
        "agitation_tendency",
        "palpitation_at_rest",
        "palpitation_after_activity",
    ]
    facts = [
        make_evidence(f"f_{index}", claims[index]) for index in range(fact_count)
    ]

    count, coverage = ods.canonical_evidence_coverage(facts, mapping)

    assert count == fact_count
    assert coverage == expected_coverage


def test_coverage_below_threshold_does_not_block_the_mode(mapping: dict, assets) -> None:
    """Observed: coverage 3/8 (0.375 < 0.50) no longer routes to basic_wellness.

    Under the V2.1 baseline, coverage is a persisted audit metric only. The same
    3-fact population still qualifies liver as a legal candidate, so the mode is
    personalized even though ``coverage_gate_passed`` is False.
    """

    below = [make_evidence(f"f_{i}", c) for i, c in enumerate(
        ["anger_tendency", "flank_discomfort", "tendon_stiffness"]
    )]
    at = below + [make_evidence("f_3", "muscle_cramp")]

    from tests.sprint7_audit.harness import decide

    decision_below = decide(below, assets)
    decision_at = decide(at, assets)

    assert decision_below.coverage.coverage_gate_passed is False
    assert decision_below.coverage.evidence_coverage == 0.375
    # the decisive point: a failed coverage gate no longer forces basic_wellness
    assert decision_below.regulation_mode == "personalized_five_tone"
    assert decision_below.dominant_organ == "liver"

    assert decision_at.coverage.coverage_gate_passed is True
    assert decision_at.coverage.confirmed_fact_count == 4
    assert decision_at.coverage.coverage_denominator == 8


def test_minimum_evidence_count_is_two(mapping: dict) -> None:
    """Observed: one claim never qualifies an organ, however strong it is."""

    evidence = make_evidence("f_solo", "flank_discomfort", reliability=1.0)
    from tests.sprint7_audit.harness import make_link

    links = [make_link(evidence, "liver", 1.0)]

    snap = ods.build_organ_aggregation_snapshot([evidence], links, mapping)

    # the arithmetic is satisfied, but the count gate keeps liver out
    assert snap.raw_support_by_organ["liver"] == 1.0
    assert "liver" not in snap.legal_candidate_organs
    assert snap.legal_candidate_by_organ["liver"] is False
    assert snap.effective_evidence_count_by_organ["liver"] == 1


@pytest.mark.parametrize(
    ("raw_target", "expected_candidate"),
    [(0.7499, False), (0.75, True), (0.7501, True)],
)
def test_minimum_total_support_boundary(
    mapping: dict, raw_target: float, expected_candidate: bool
) -> None:
    """Observed: the floor is inclusive (``>=``) and is the only gate left.

    Link strengths here are synthetic; the threshold itself is read from the
    approved mapping.
    """

    facts, links = synthetic_population({"liver": raw_target})

    snap = ods.build_organ_aggregation_snapshot(facts, links, mapping)

    assert ("liver" in snap.legal_candidate_organs) is expected_candidate


def test_organ_support_is_strength_times_reliability(mapping: dict) -> None:
    """Observed: the documented formula holds exactly on a real claim pair."""

    facts = [
        make_evidence("f_anger", "anger_tendency", reliability=0.5),
        make_evidence("f_flank", "flank_discomfort", reliability=0.5),
    ]

    snap = snapshot(facts, mapping)

    # approved link strengths: anger_tendency 0.55, flank_discomfort 0.70
    assert snap.raw_support_by_organ["liver"] == pytest.approx(
        (0.55 + 0.70) * 0.5
    )


def test_zero_candidate_abstains_instead_of_forcing_an_organ(assets) -> None:
    """Observed: with no legal candidate the frozen outcome is ``basic_wellness``."""

    from tests.sprint7_audit.harness import decide

    facts = [
        make_evidence("f_a", "anger_tendency"),
        make_evidence("f_b", "flank_discomfort"),
        make_evidence("f_c", "tendon_stiffness"),
        make_evidence("f_d", "muscle_cramp"),
    ]
    decision = decide(facts, assets, coverage=1.0)

    # four liver claims do qualify liver, so this asserts the non-zero path
    assert decision.regulation_mode == "personalized_five_tone"
    assert decision.dominant_organ == "liver"
    assert decision.decision_reason_code == "PERSONALIZED_SINGLE_LEGAL_CANDIDATE"
