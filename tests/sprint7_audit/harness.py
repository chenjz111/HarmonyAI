"""Pure helpers for the Sprint 7 R1/R2 evidence counterfactual audit.

Everything here calls the **real** production functions and reads the
**approved** JSON assets. No provider, no network, no database.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.schemas.v3.assessment import (
    _ORGAN_ELEMENT,
    FactEvidence,
    OrganEvidenceLink,
)
from backend.app.schemas.v3.common import (
    EvidenceDirection,
    OrganCode,
    SourceRef,
    SourceType,
)
from backend.app.schemas.v3.flow_v31 import (
    OrganDominanceAssetIdentity,
    OrganDominanceDecisionV1,
)
from backend.app.services.v3 import assessment_service
from backend.app.services.v3 import organ_dominance_service as ods
from backend.app.services.v3.knowledge_assets import (
    load_five_tone_mapping,
    load_organ_mapping,
)

SOURCE_TYPE_BY_NAME = {
    "document": SourceType.document,
    "questionnaire": SourceType.questionnaire,
    "case_summary": SourceType.case_summary,
    "narrative": SourceType.narrative,
}


# --------------------------------------------------------------------------- #
# asset loading
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class AuditAssets:
    """The three approved assets the decision chain consumes."""

    mapping: dict
    five_tone: dict
    dominance_rule: dict
    identity: OrganDominanceAssetIdentity


def load_audit_assets() -> AuditAssets:
    mapping = load_organ_mapping()
    five_tone = load_five_tone_mapping()
    rule = ods.load_configured_dominance_rule()
    identity = ods.verify_mapping_identity(
        rule, organ_mapping=mapping, five_tone_mapping=five_tone
    )
    return AuditAssets(
        mapping=mapping,
        five_tone=five_tone,
        dominance_rule=rule,
        identity=identity,
    )


# --------------------------------------------------------------------------- #
# synthetic (de-identified) builders
# --------------------------------------------------------------------------- #


def make_evidence(
    fact_id: str,
    claim_code: str,
    *,
    negated: bool = False,
    source_id: str = "src_doc_1",
    source_type: str = "document",
    reliability: float = 0.8,
    value: int = 3,
    time_window: str = "past_7_days",
    confirmation_status: str = "confirmed",
) -> FactEvidence:
    """Build a ``FactEvidence`` exactly as ``_fact_evidence`` would.

    ``direction`` comes from ``negated`` only. There is deliberately no
    ``subject`` parameter: the production model has no such field.
    """

    return FactEvidence(
        fact_evidence_id=f"fev_{fact_id}",
        assessment_id="asmt_s7_audit",
        assessment_revision=1,
        fact_id=fact_id,
        claim_code=claim_code,
        display_name=claim_code,
        category="sprint7_audit",
        value={"type": "frequency_0_4", "value": value},
        time_window=time_window,
        direction=(
            EvidenceDirection.contradicting
            if negated
            else EvidenceDirection.supporting
        ),
        reliability=reliability,
        source_refs=[
            SourceRef(
                source_id=source_id,
                source_type=SOURCE_TYPE_BY_NAME[source_type],
            )
        ],
        confirmation_status=confirmation_status,
    )


def make_link(
    evidence: FactEvidence,
    organ: str,
    link_strength: float,
    *,
    direction: str = "supporting",
    rule_id: str = "audit_synthetic_rule",
) -> OrganEvidenceLink:
    """Build an ``OrganEvidenceLink`` with an explicitly chosen direction."""

    return OrganEvidenceLink(
        organ_evidence_link_id=f"oel_{evidence.fact_evidence_id}_{organ}",
        fact_evidence_id=evidence.fact_evidence_id,
        organ=OrganCode(organ),
        element=_ORGAN_ELEMENT[OrganCode(organ)],
        direction=EvidenceDirection(direction),
        link_strength=link_strength,
        mapping_rule_id=rule_id,
        mapping_version="organ_mapping_v3.0",
        explanation_summary="sprint7 audit fixture",
    )


# --------------------------------------------------------------------------- #
# production pipeline slices
# --------------------------------------------------------------------------- #


def production_links(
    evidence: list[FactEvidence], mapping: dict
) -> list[OrganEvidenceLink]:
    """Real ``assessment_service._organ_links`` over the approved mapping."""

    return assessment_service._organ_links(evidence, mapping)


def snapshot(evidence: list[FactEvidence], mapping: dict):
    """Real single scoring pass over the canonical effective population."""

    effective = ods.canonical_effective_evidence(evidence, mapping)
    links = production_links(effective, mapping)
    return ods.build_organ_aggregation_snapshot(effective, links, mapping)


def decide(
    evidence: list[FactEvidence],
    assets: AuditAssets,
    *,
    coverage: float | None = None,
    conflicts: list | None = None,
    upstream_abstain_reason: str | None = None,
) -> OrganDominanceDecisionV1:
    """Run the frozen decision chain end to end (pure, offline)."""

    effective = ods.canonical_effective_evidence(evidence, assets.mapping)
    links = production_links(effective, assets.mapping)
    aggregation = ods.build_organ_aggregation_snapshot(
        effective, links, assets.mapping
    )
    return ods.resolve_organ_dominance(
        assessment_id="asmt_s7_audit",
        assessment_revision=1,
        input_revision=1,
        aggregation=aggregation,
        conflicts=list(conflicts or []),
        fact_claims=ods.fact_claim_index(effective),
        dominance_rule=assets.dominance_rule,
        five_tone_mapping=assets.five_tone,
        assets=assets.identity,
        evidence_coverage=coverage,
        confirmed_fact_count=len(effective),
        upstream_abstain_reason=upstream_abstain_reason,
    )


def liver_claims() -> list[FactEvidence]:
    """Two distinct liver claims -- the minimum a liver candidate needs."""

    return [
        make_evidence("f_anger", "anger_tendency"),
        make_evidence("f_flank", "flank_discomfort"),
    ]


def heart_claims() -> list[FactEvidence]:
    """Two distinct heart claims -- the minimum a heart candidate needs."""

    return [
        make_evidence("f_agitation", "agitation_tendency"),
        make_evidence("f_palpitation", "palpitation_at_rest"),
    ]


# --------------------------------------------------------------------------- #
# boundary harness -- synthetic link strengths for threshold arithmetic
# --------------------------------------------------------------------------- #

#: Two combination claims per organ, deliberately chosen so that none of them
#: is governed by a ``multi_organ_rules`` entry (those would change the link
#: shape and are covered separately).
COMBINATION_CLAIMS: dict[str, tuple[str, str]] = {
    "liver": ("anger_tendency", "flank_discomfort"),
    "heart": ("agitation_tendency", "palpitation_at_rest"),
    "spleen": ("poor_appetite", "postmeal_bloating"),
    "lung": ("throat_cough", "nasal_discomfort"),
    "kidney": ("fear_tendency", "nocturia"),
}


def synthetic_population(
    targets: dict[str, float], *, reliability: float = 1.0
):
    """Facts + links engineered so each organ lands on an exact raw support.

    This bypasses ``_organ_links`` on purpose: the point is to hit a threshold
    from both sides, not to exercise the mapping asset. The mapping asset is
    still what the aggregation reads for ``min_count`` / ``minimum_total_support``.
    """

    facts: list[FactEvidence] = []
    links: list[OrganEvidenceLink] = []
    for organ, target in targets.items():
        claims = COMBINATION_CLAIMS[organ]
        per_claim = target / len(claims)
        for index, claim in enumerate(claims):
            evidence = make_evidence(
                f"f_{organ}_{index}", claim, reliability=reliability
            )
            facts.append(evidence)
            links.append(make_link(evidence, organ, per_claim))
    return facts, links


def decide_with_population(
    facts: list[FactEvidence],
    links: list[OrganEvidenceLink],
    assets: AuditAssets,
    *,
    coverage: float | None = None,
    conflicts: list | None = None,
) -> OrganDominanceDecisionV1:
    """Run the frozen decision chain over an explicitly supplied link set."""

    aggregation = ods.build_organ_aggregation_snapshot(
        facts, links, assets.mapping
    )
    return ods.resolve_organ_dominance(
        assessment_id="asmt_s7_audit",
        assessment_revision=1,
        input_revision=1,
        aggregation=aggregation,
        conflicts=list(conflicts or []),
        fact_claims=ods.fact_claim_index(facts),
        dominance_rule=assets.dominance_rule,
        five_tone_mapping=assets.five_tone,
        assets=assets.identity,
        evidence_coverage=coverage,
        confirmed_fact_count=len(facts),
    )
