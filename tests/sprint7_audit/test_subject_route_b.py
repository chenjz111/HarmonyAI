"""R1/R2 audit -- subject route B feasibility (exclude other/unknown at input).

Owner ruling (2026-10-15): prefer route B -- do not add a ``FactEvidence``
field or a migration; instead exclude ``subject in ("other", "unknown")`` at
the authoritative evidence-input stage, keep the original facts for audit, and
keep Assessment / Diagnosis / tone selection / public explanation consistent.

These tests prove the *data supports route B* and that a minimal split function
(prototype only, not production code) yields four-layer consistency. No
production file is modified.
"""

from __future__ import annotations

from backend.app.schemas.v3.assessment import FactEvidence
from backend.app.schemas.v3.understanding import NormalizedFact
from backend.app.services.v3 import assessment_service

from tests.sprint7_audit.harness import decide, production_links


# --------------------------------------------------------------------------- #
# route B prototype (NOT production code -- proof of concept only)
# --------------------------------------------------------------------------- #


def split_by_subject(facts: list[dict]) -> tuple[list[dict], list[dict]]:
    """Prototype: separate self from other/unknown at the evidence-input stage.

    ``self`` proceeds into the personal five-tone scoring chain; ``other`` and
    ``unknown`` are excluded from scoring but preserved verbatim for audit.
    """

    self_facts = [f for f in facts if f.get("subject") == "self"]
    excluded = [f for f in facts if f.get("subject") in ("other", "unknown")]
    return self_facts, excluded


def _fact_dict(fact_id: str, claim_code: str, subject: str) -> dict:
    """A de-identified fact dict shaped like ``presentation_json["normalized_facts"]``."""

    return {
        "fact_id": fact_id,
        "fact_code": claim_code,
        "display_name": claim_code,
        "category": "sprint7_audit",
        "value": {"type": "frequency_0_4", "value": 3},
        "time_window": "past_7_days",
        "negated": False,
        "subject": subject,
        "source_refs": [{"source_id": f"src_{fact_id}", "source_type": "document"}],
        "confirmation_status": "confirmed",
        "extraction": {"method": "rule", "confidence": 0.8},
    }


# --------------------------------------------------------------------------- #
# 1. subject is present upstream, absent on FactEvidence
# --------------------------------------------------------------------------- #


def test_subject_is_present_on_normalized_fact_but_not_fact_evidence() -> None:
    """Observed: the data supports route B -- subject exists upstream, drops at FactEvidence."""

    assert "subject" in NormalizedFact.model_fields
    assert "subject" not in FactEvidence.model_fields

    fact = NormalizedFact.model_validate(
        _fact_dict("f_1", "flank_discomfort", "self")
    )
    assert fact.subject == "self"


def test_fact_evidence_builder_still_drops_subject() -> None:
    """Observed: the production builder does not read subject -- hence route B
    must split *before* this call, exactly where the prototype operates."""

    row = assessment_service._fact_evidence(
        "asmt_probe", _fact_dict("f_1", "flank_discomfort", "other"), index=0
    )
    assert not hasattr(row, "subject")


# --------------------------------------------------------------------------- #
# 2. the split separates self from other/unknown, preserving the rest
# --------------------------------------------------------------------------- #


def test_split_separates_self_from_other_and_unknown() -> None:
    """Observed: route B split yields exactly the self facts for scoring."""

    facts = [
        _fact_dict("f_self", "anger_tendency", "self"),
        _fact_dict("f_other", "flank_discomfort", "other"),
        _fact_dict("f_unknown", "tendon_stiffness", "unknown"),
    ]
    self_facts, excluded = split_by_subject(facts)

    assert [f["fact_id"] for f in self_facts] == ["f_self"]
    assert {f["fact_id"] for f in excluded} == {"f_other", "f_unknown"}


def test_excluded_facts_are_preserved_verbatim_for_audit() -> None:
    """Observed: other/unknown facts keep every original field for traceability."""

    facts = [
        _fact_dict("f_other", "flank_discomfort", "other"),
    ]
    _, excluded = split_by_subject(facts)

    assert excluded[0]["subject"] == "other"
    assert excluded[0]["claim_code" if False else "fact_code"] == "flank_discomfort"
    assert excluded[0]["source_refs"][0]["source_id"] == "src_f_other"


# --------------------------------------------------------------------------- #
# 3. four-layer consistency: only self drives score and public wording
# --------------------------------------------------------------------------- #


def test_self_facts_alone_drive_the_decision(assets) -> None:
    """Observed: after the split, only self facts enter the scoring chain.

    Two self liver facts qualify liver; the other/unknown facts never reach
    ``build_organ_aggregation_snapshot``, so they cannot contribute support.
    """

    facts = [
        _fact_dict("f_anger", "anger_tendency", "self"),
        _fact_dict("f_flank", "flank_discomfort", "self"),
        _fact_dict("f_cramp", "muscle_cramp", "other"),
    ]
    self_facts, _excluded = split_by_subject(facts)

    evidence = [
        assessment_service._fact_evidence("asmt_probe", fact, index=i)
        for i, fact in enumerate(self_facts)
    ]
    decision = decide(evidence, assets, coverage=1.0)

    assert decision.regulation_mode == "personalized_five_tone"
    assert decision.dominant_organ == "liver"

    # the other fact's claim must not appear among the organ's supporting claims
    from backend.app.services.v3 import organ_dominance_service as ods

    effective = ods.canonical_effective_evidence(evidence, assets.mapping)
    links = production_links(effective, assets.mapping)
    aggregation = ods.build_organ_aggregation_snapshot(
        effective, links, assets.mapping
    )
    liver_claims = aggregation.contributing_claims_by_organ.get("liver", ())
    assert "muscle_cramp" not in liver_claims


def test_public_explanation_matches_the_self_only_decision(assets) -> None:
    """Observed: with other/unknown excluded at input, public wording and the
    internal decision agree -- no "chose a tone but cite nothing" gap."""

    from backend.ai_engine.v3.public_explanation import direction_explanation, public_facts

    facts = [
        _fact_dict("f_anger", "anger_tendency", "self"),
        _fact_dict("f_flank", "flank_discomfort", "self"),
        _fact_dict("f_cramp", "muscle_cramp", "other"),
    ]
    self_facts, _excluded = split_by_subject(facts)

    evidence = [
        assessment_service._fact_evidence("asmt_probe", fact, index=i)
        for i, fact in enumerate(self_facts)
    ]
    decision = decide(evidence, assets, coverage=1.0)

    public = public_facts(evidence, production_links(evidence, assets.mapping))
    text, refs = direction_explanation(public, decision, mode=decision.regulation_mode)

    assert decision.regulation_mode == "personalized_five_tone"
    assert "肝" in text  # the public wording cites the organ, consistent with the decision
    assert refs, "the self facts should be cited by id"
