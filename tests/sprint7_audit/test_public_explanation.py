"""R1/R2 audit -- stage S12 ``public_explanation``.

``public_facts`` is the only gate between the internal evidence and what the
user is told. Its docstring is explicit about the asymmetry under test:

    Negation/subject exclusions are supplied by the DB owner. False/zero,
    contradicting, unconfirmed, stale and unresolved-conflict facts cannot be
    presented as positive reasons, even if their mapping links are positive.

The decisive audit question is whether the internal decision (which lets a
negated fact still contribute positive organ support -- see
``test_negation_contribution``) can disagree with the public wording, which
drops exactly those facts.
"""

from __future__ import annotations

from backend.ai_engine.v3.public_explanation import (
    direction_explanation,
    public_facts,
    state_tendency,
)
from backend.app.services.v3 import organ_dominance_service as ods

from tests.sprint7_audit.harness import (
    decide,
    liver_claims,
    make_evidence,
    production_links,
)


def _public(facts, mapping, *, excluded_ids=()):
    effective = ods.canonical_effective_evidence(facts, mapping)
    links = production_links(effective, mapping)
    return public_facts(effective, links, excluded_ids=excluded_ids)


def test_supporting_facts_are_presented(mapping: dict) -> None:
    """Observed: confirmed positive evidence survives into the public set."""

    public = _public(liver_claims(), mapping)
    assert len(public) == 2
    assert {fact.claim_code for fact in public} == {
        "anger_tendency",
        "flank_discomfort",
    }


def test_contradicting_facts_are_dropped(mapping: dict) -> None:
    """Observed: a negated fact is excluded from public reasons even though its
    mapping link is ``supporting``."""

    facts = [
        make_evidence("f_anger", "anger_tendency"),
        make_evidence("f_flank", "flank_discomfort", negated=True),
    ]
    public = _public(facts, mapping)
    assert [fact.claim_code for fact in public] == ["anger_tendency"]


def test_excluded_ids_remove_facts(mapping: dict) -> None:
    """Observed: the DB-owner exclusion list (subject exclusions) drops rows."""

    effective = ods.canonical_effective_evidence(liver_claims(), mapping)
    excluded = [effective[0].fact_evidence_id]
    public = public_facts(
        effective,
        production_links(effective, mapping),
        excluded_ids=excluded,
    )
    assert all(fact.evidence_id != excluded[0] for fact in public)


def test_zero_reliability_is_dropped(mapping: dict) -> None:
    """Observed: a fact scoring 0 can never become a positive reason."""

    facts = [
        make_evidence("f_anger", "anger_tendency"),
        make_evidence("f_flank", "flank_discomfort", reliability=0.0),
    ]
    public = _public(facts, mapping)
    assert [fact.claim_code for fact in public] == ["anger_tendency"]


def test_empty_value_is_dropped(mapping: dict) -> None:
    """Observed: a present fact whose value is 0 is not a usable reason."""

    facts = [
        make_evidence("f_anger", "anger_tendency"),
        make_evidence("f_flank", "flank_discomfort", value=0),
    ]
    public = _public(facts, mapping)
    assert [fact.claim_code for fact in public] == ["anger_tendency"]


def test_state_tendency_empty_wording(mapping: dict) -> None:
    """Observed: no public facts -> the frozen "insufficient" sentence."""

    assert "缺少可公开引用的正向状态依据" in state_tendency(())


# --------------------------------------------------------------------------- #
# internal decision vs public wording -- the decisive counterfactual
# --------------------------------------------------------------------------- #


def test_negated_only_population_personalizes_internally_but_explains_nothing(
    assets,
) -> None:
    """Observed: an all-negated population still selects a tone internally,
    while the public layer has nothing to cite.

    Both liver facts are negated, so ``public_facts`` drops them, yet the
    aggregation layer (whose links are all ``supporting``) still qualifies liver
    and ``resolve_organ_dominance`` returns ``personalized_five_tone``. The
    public explanation then reports "缺少可公开引用的具体状态依据" -- a direct
    internal/public inconsistency that needs a medical ruling (D-4 / D-8).
    """

    facts = [
        make_evidence("f_anger", "anger_tendency", negated=True),
        make_evidence("f_flank", "flank_discomfort", negated=True),
    ]

    decision = decide(facts, assets, coverage=1.0)

    # internal: liver qualifies and is chosen
    assert decision.regulation_mode == "personalized_five_tone"
    assert decision.dominant_organ == "liver"
    assert decision.primary_tone == "jiao"

    # public: every fact is contradicting and therefore dropped
    public = _public(facts, assets.mapping)
    assert public == ()

    text, refs = direction_explanation(
        public, decision, mode=decision.regulation_mode
    )
    assert "缺少可公开引用的具体状态依据" in text
    assert refs == []


def test_supporting_population_aligns_public_and_internal(assets) -> None:
    """Observed: with positive evidence the public wording does cite the organ."""

    facts = liver_claims()
    decision = decide(facts, assets, coverage=1.0)

    assert decision.regulation_mode == "personalized_five_tone"
    public = _public(facts, assets.mapping)
    text, refs = direction_explanation(public, decision, mode=decision.regulation_mode)

    assert "肝" in text
    assert refs, "the positive facts should be cited by id"


def test_direction_explanation_basic_wellness_wording() -> None:
    """Observed: the frozen basic_wellness wording never names a tone."""

    text, refs = direction_explanation((), None, mode="basic_wellness")
    assert "不指定五音主音" in text or "不作五脏或五音主音判断" in text
    assert refs == []
