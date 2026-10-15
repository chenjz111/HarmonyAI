"""R1/R2 audit -- the canonical effective evidence population (stage S4).

Source anchors:

* ``organ_dominance_service.select_effective_evidence()`` lines 336-365
  one effective ``FactEvidence`` per ``claim_code``; ordering key is
  ``(is_questionnaire_evidence, reliability, fact_id)``, applied whenever the
  approved mapping declares the ``questionnaire_priority`` conflict rule.
* ``organ_dominance_service.confirmed_evidence()`` line 368 -- only
  ``confirmation_status == "confirmed"`` counts.

Two observations matter for the audit:

1. the dedupe is **not** questionnaire-only; two document facts carrying the
   same claim collapse into one, so coverage can be lower than the number of
   extracted facts;
2. ties are broken by ``fact_id`` -- deterministic, but not medically ranked.
"""

from __future__ import annotations

from backend.app.services.v3 import organ_dominance_service as ods

from tests.sprint7_audit.harness import make_evidence, production_links


def test_mapping_declares_the_questionnaire_priority_rule(mapping: dict) -> None:
    """Observed: the rule that switches dedupe on is present in the asset."""

    rules = {row["rule"] for row in mapping["conflict_rules"]}
    assert "questionnaire_priority" in rules


def test_unconfirmed_evidence_never_enters_the_population(mapping: dict) -> None:
    """Observed: ``unconfirmed`` / ``rejected`` facts are dropped first."""

    confirmed = make_evidence("f_ok", "flank_discomfort")
    unconfirmed = make_evidence(
        "f_wait", "anger_tendency", confirmation_status="unconfirmed"
    )

    assert ods.confirmed_evidence([confirmed, unconfirmed]) == [confirmed]
    assert ods.canonical_effective_evidence(
        [confirmed, unconfirmed], mapping
    ) == [confirmed]


def test_same_claim_from_two_documents_collapses_to_one(mapping: dict) -> None:
    """Observed: document-vs-document duplicates are deduped too.

    Only the higher-reliability document survives, so the second source stops
    contributing to coverage even though it is a genuinely independent record.
    """

    low = make_evidence("f_a", "flank_discomfort", source_id="src_doc_a", reliability=0.5)
    high = make_evidence("f_b", "flank_discomfort", source_id="src_doc_b", reliability=0.9)

    kept = ods.canonical_effective_evidence([low, high], mapping)

    assert len(kept) == 1
    assert kept[0].fact_id == "f_b"


def test_identical_reliability_falls_back_to_fact_id_order(mapping: dict) -> None:
    """Observed: an exact tie is settled by ``fact_id``, not by medicine."""

    first = make_evidence("f_alpha", "flank_discomfort", source_id="src_doc_a")
    second = make_evidence("f_beta", "flank_discomfort", source_id="src_doc_b")

    kept = ods.canonical_effective_evidence([first, second], mapping)

    assert len(kept) == 1
    assert kept[0].fact_id == "f_beta"


def test_questionnaire_beats_a_more_reliable_document(mapping: dict) -> None:
    """Observed: the questionnaire wins regardless of reliability."""

    document = make_evidence(
        "f_doc", "flank_discomfort", source_id="src_doc_1", reliability=1.0
    )
    questionnaire = make_evidence(
        "f_q",
        "flank_discomfort",
        source_id="src_q_1",
        source_type="questionnaire",
        reliability=0.25,
    )

    kept = ods.canonical_effective_evidence([document, questionnaire], mapping)

    assert len(kept) == 1
    assert kept[0].fact_id == "f_q"


def test_distinct_claims_are_both_kept(mapping: dict) -> None:
    """Observed: dedupe is per claim, so different claims survive together."""

    facts = [
        make_evidence("f_anger", "anger_tendency"),
        make_evidence("f_flank", "flank_discomfort"),
    ]

    kept = ods.canonical_effective_evidence(facts, mapping)

    assert {item.fact_id for item in kept} == {"f_anger", "f_flank"}


def test_duplicate_claim_reduces_what_the_summary_can_see(mapping: dict) -> None:
    """Observed: the summary is built from the effective evidence, not the raw list.

    The dedupe happens before ``_authoritative_state_summary`` in
    ``assessment_service._recompute_derived_state``, so a second source for the
    same claim cannot even be counted there.
    """

    facts = [
        make_evidence("f_a", "flank_discomfort"),
        make_evidence("f_b", "flank_discomfort", source_id="src_doc_b"),
    ]
    effective = ods.canonical_effective_evidence(facts, mapping)

    assert len(production_links(effective, mapping)) == 1
