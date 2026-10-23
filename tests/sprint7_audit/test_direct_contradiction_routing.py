"""R1/R2 audit -- V2.1 direct-contradiction routing (the new safety net).

The baseline introduces ``conflict_kind="direct_contradiction"`` plus
``temporal_comparable``; ``blocking_direct_contradiction_ids`` only blocks
routing when the contradiction unseats the unique top1 after a counterfactual
recompute. These two cases pin that boundary down. (Moved here from the local
draft that the owner's original characterization files replaced.)
"""

from __future__ import annotations

from backend.app.services.v3 import assessment_service

from tests.sprint7_audit.harness import (
    decide,
    liver_claims,
    make_evidence,
)


def test_direct_contradiction_on_top1_blocks_to_basic(assets) -> None:
    """Observed: a temporal-comparable polarity flip on a top1 claim -> basic.

    A liver claim (flank_discomfort) is asserted by the questionnaire and
    negated by a document. Same claim, opposite direction, temporally
    comparable -> ``_build_conflicts`` marks it ``direct_contradiction``; the
    counterfactual recompute drops the claim and liver no longer survives as the
    unique top1 -> ``basic_wellness``.
    """

    facts = [
        make_evidence("f_anger", "anger_tendency"),
        make_evidence(
            "f_flank_q",
            "flank_discomfort",
            source_id="src_q_1",
            source_type="questionnaire",
        ),
        make_evidence("f_flank_d", "flank_discomfort", negated=True),
    ]
    conflicts = assessment_service._build_conflicts(facts, assets.mapping)

    assert len(conflicts) == 1
    assert conflicts[0].conflict_kind == "direct_contradiction"
    assert conflicts[0].temporal_comparable is True

    decision = decide(facts, assets, coverage=1.0, conflicts=conflicts)

    assert decision.regulation_mode == "basic_wellness"
    assert decision.decision_reason_code == "BASIC_UNRESOLVED_DIRECT_CONTRADICTION"
    assert decision.dominant_organ is None


def test_direct_contradiction_off_top1_does_not_block(assets) -> None:
    """Observed: the same polarity flip on a non-top1 claim leaves the mode alone.

    liver is the only legal candidate; the contradicted claim (sleep_disturbance)
    maps to heart/spleen/kidney and never touches liver's contributing claims,
    so the recompute does not unseat top1 and routing continues.
    """

    facts = liver_claims() + [
        make_evidence(
            "f_sleep_q",
            "sleep_disturbance",
            source_id="src_q_1",
            source_type="questionnaire",
        ),
        make_evidence("f_sleep_d", "sleep_disturbance", negated=True),
    ]
    conflicts = assessment_service._build_conflicts(facts, assets.mapping)

    assert conflicts and conflicts[0].conflict_kind == "direct_contradiction"

    decision = decide(facts, assets, coverage=1.0, conflicts=conflicts)

    assert decision.regulation_mode == "personalized_five_tone"
    assert decision.dominant_organ == "liver"
