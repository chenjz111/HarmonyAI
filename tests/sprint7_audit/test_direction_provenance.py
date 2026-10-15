"""R1/R2 audit -- the two ``direction`` fields are not the same field.

Source anchors (published baseline ``feat/s6-product-recovery``):

* ``assessment_service._fact_evidence()`` lines 594-598
  ``FactEvidence.direction <- fact["negated"]``  (fact direction)
* ``assessment_service._organ_links()`` line 661
  ``OrganEvidenceLink.direction <- rule["direction"]``  (rule direction,
  read from the approved organ mapping -- never from the fact)
* ``organ_dominance_service.build_organ_aggregation_snapshot()`` lines 521-528
  ``direction_signed = 1.0 if link.direction == "supporting" else -1.0``
  so the score consumes the **rule** direction only.

These tests record observed behaviour. They do not assert that the behaviour
is medically correct; that is a separate sign-off item (see D-1 in the audit
report).
"""

from __future__ import annotations

from backend.app.schemas.v3.common import EvidenceDirection

from tests.sprint7_audit.harness import make_evidence, production_links


def test_approved_mapping_declares_no_contradicting_link(mapping: dict) -> None:
    """Observed: every approved link is ``supporting``.

    With no ``contradicting`` link available, ``direction_signed`` can never
    become ``-1.0`` in the current asset release.
    """

    directions = {row["direction"] for row in mapping["single_mappings"]}
    for row in mapping.get("multi_organ_rules", []):
        directions.update(link["direction"] for link in row.get("links", []))

    assert directions == {"supporting"}, (
        "an approved contradicting link appeared; the negative-contribution "
        "analysis in the audit report must be re-derived"
    )


def test_organ_links_use_rule_direction_not_fact_direction(mapping: dict) -> None:
    """Observed: a negated fact still yields ``supporting`` links."""

    fact = make_evidence("f_neg_flank", "flank_discomfort", negated=True)
    assert fact.direction is EvidenceDirection.contradicting

    links = production_links([fact], mapping)

    assert links, "the approved mapping must produce at least one link"
    assert {link.direction for link in links} == {EvidenceDirection.supporting}


def test_fact_direction_is_not_read_by_organ_links(mapping: dict) -> None:
    """Observed: flipping only ``negated`` leaves the produced links identical.

    If the link layer ever started reading ``ev.direction``, the two link sets
    would diverge and this audit would need re-running.
    """

    positive = make_evidence("f_flank", "flank_discomfort")
    negated = make_evidence("f_flank", "flank_discomfort", negated=True)

    links_positive = production_links([positive], mapping)
    links_negated = production_links([negated], mapping)

    def shape(links):
        return sorted(
            (link.organ.value, link.direction.value, link.link_strength)
            for link in links
        )

    assert shape(links_positive) == shape(links_negated)
