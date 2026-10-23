"""R1/R2 audit -- neutral exclusion of negated facts (D-8 / D-1 / D-4).

Owner ruling: negated facts must be handled conservatively -- they must NOT
contribute positive organ support, and must NOT be converted (via ``-1``) into
positive evidence for another organ. The proposed policy is *neutral
exclusion*: drop them from the positive scoring chain, keep them as audit /
contradiction signals.

These tests prove, with a prototype filter (NOT production code), that neutral
exclusion produces the correct outcome: an all-negated population can no longer
manufacture a personalised tone, and a negated fact never inflates any organ.
"""

from __future__ import annotations

from backend.app.schemas.v3.common import EvidenceDirection

from tests.sprint7_audit.harness import decide, make_evidence, production_links


def neutral_exclude_negated(evidence):
    """Prototype: negated facts are dropped from positive scoring only.

    They are NOT mapped to -1 (no fabricated reverse evidence) and NOT moved to
    another organ (no fabricated cross-organ support).
    """

    return [item for item in evidence if item.direction is EvidenceDirection.supporting]


def _snap_support(evidence, mapping):
    from backend.app.services.v3 import organ_dominance_service as ods

    effective = ods.canonical_effective_evidence(evidence, mapping)
    links = production_links(effective, mapping)
    return ods.build_organ_aggregation_snapshot(effective, links, mapping)


def test_negated_fact_inflates_support_but_neutral_exclusion_removes_it(mapping: dict) -> None:
    """Observed: baseline lets a negated flank count toward liver; neutral
    exclusion removes that contribution."""

    facts = [
        make_evidence("f_anger", "anger_tendency"),
        make_evidence("f_flank", "flank_discomfort", negated=True),
    ]

    baseline = _snap_support(facts, mapping).raw_support_by_organ["liver"]
    neutral = _snap_support(neutral_exclude_negated(facts), mapping).raw_support_by_organ["liver"]

    # baseline counts flank (link direction is supporting); neutral drops it
    assert baseline > neutral


def test_neutral_exclusion_never_produces_negative_support(mapping: dict) -> None:
    """Observed: exclusion subtracts by absence, not by a negative score.

    No organ's support goes below zero, and no organ gains support from the
    removal -- the negated fact is simply not there.
    """

    facts = [
        make_evidence("f_anger", "anger_tendency"),
        make_evidence("f_flank", "flank_discomfort", negated=True),
    ]
    snap = _snap_support(neutral_exclude_negated(facts), mapping)

    assert all(v >= 0 for v in snap.raw_support_by_organ.values())
    # liver keeps only anger's contribution, no phantom organ appears
    assert snap.raw_support_by_organ["liver"] > 0


def test_all_negated_population_cannot_manufacture_a_tone(assets) -> None:
    """Observed: after neutral exclusion an all-negated population is empty,
    so it routes to basic_wellness instead of personalised (fixes D-4 / D-8)."""

    facts = [
        make_evidence("f_anger", "anger_tendency", negated=True),
        make_evidence("f_flank", "flank_discomfort", negated=True),
    ]

    evidence = neutral_exclude_negated(facts)
    assert evidence == []

    decision = decide(evidence, assets, coverage=1.0)

    assert decision.regulation_mode == "basic_wellness"
    assert decision.dominant_organ is None
    assert decision.primary_tone is None


def test_negated_fact_is_not_converted_into_another_organ_support(mapping: dict) -> None:
    """Observed: a negated heart claim is removed, not re-scored onto another organ."""

    facts = [
        make_evidence("f_anger", "anger_tendency"),
        make_evidence("f_flank", "flank_discomfort"),
        make_evidence("f_agitation", "agitation_tendency", negated=True),
    ]

    snap = _snap_support(neutral_exclude_negated(facts), mapping)

    # agitation is a heart claim; its negation must not add to heart or anywhere else
    assert snap.raw_support_by_organ["heart"] == 0.0
    assert "heart" not in snap.legal_candidate_organs
