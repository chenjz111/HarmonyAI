"""Sprint 6 Phase 1B test support: authoritative decision fixtures.

Two helpers, with deliberately different purposes:

* :func:`decision_from_organ_support` / :func:`decision_from_organ_weights`
  drive the **real** dominance service over synthetic evidence, so routing
  behaviour (gates, precedence, boundaries) is exercised through production
  code only;
* :func:`synthetic_decision` builds an explicitly shaped decision object for
  tests that only need *a* valid authoritative decision (Agent3 construction,
  serialization, compatibility) without asserting routing.

Nothing here is production code: Agent3/prescription never derive a mode.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from backend.app.schemas.v3.assessment import FactEvidence, OrganEvidenceLink
from backend.app.services.v3.knowledge_assets import load_five_tone_mapping
from backend.app.services.v3.organ_dominance_service import (
    build_organ_aggregation_snapshot,
    load_configured_dominance_rule,
    resolve_organ_dominance,
    verify_mapping_identity,
)
from backend.app.services.v3.organ_dominance_service import (
    REASON_BASIC_NO_LEGAL_ORGAN_CANDIDATE,
    REASON_PERSONALIZED_DOMINANCE_THRESHOLDS_MET,
)

_ORGAN_CLAIMS: dict[str, tuple[str, ...]] = {}


def claims_for(organ: str) -> tuple[str, ...]:
    """The approved distinct claims of an organ (from the organ mapping asset)."""

    if not _ORGAN_CLAIMS:
        rules = organ_mapping().get("combination_rules") or []
        for rule in rules:
            _ORGAN_CLAIMS[str(rule["organ"])] = tuple(
                str(claim) for claim in (rule.get("claims") or [])
            )
    return _ORGAN_CLAIMS[organ]


def five_tone_mapping() -> dict:
    return load_five_tone_mapping()


def organ_mapping() -> dict:
    from backend.app.services.v3.knowledge_assets import load_organ_mapping

    return load_organ_mapping()


def dominance_rule() -> dict:
    return load_configured_dominance_rule()


def synthetic_evidence(
    organ_support: Mapping[str, float],
) -> tuple[list[FactEvidence], list[OrganEvidenceLink]]:
    """Synthetic confirmed evidence whose canonical raw support equals the input.

    Each organ gets the approved distinct claims needed by ``min_count`` (>= 2)
    with equal link strengths that sum to the requested support. Supports stay
    within ``[0, len(claims)]`` so every individual ``link_strength`` is <= 1
    (its schema bound), and the strengths are chosen so the arithmetic is as
    exact as floats allow.
    """

    evidence: list[FactEvidence] = []
    links: list[OrganEvidenceLink] = []
    for organ, support in organ_support.items():
        claims = claims_for(organ)
        value = float(support)
        if value < 0:
            raise ValueError("organ support must be non-negative")
        claim_count = 2
        while value / claim_count > 1.0 and claim_count < len(claims):
            claim_count += 1
        if value / claim_count > 1.0:
            raise ValueError(
                f"{organ} support {value} exceeds {len(claims)} unit-strength claims"
            )
        share = value / claim_count
        for index in range(claim_count):
            claim = claims[index]
            fact_id = f"fact_{organ}_{index}"
            fact_evidence_id = f"fev_{organ}_{index}"
            evidence.append(
                FactEvidence(
                    fact_evidence_id=fact_evidence_id,
                    assessment_id="asmt_fixture",
                    assessment_revision=1,
                    fact_id=fact_id,
                    claim_code=claim,
                    display_name=f"{claim} display",
                    category="symptom",
                    value={"type": "boolean", "value": True},
                    time_window="recent",
                    direction="supporting",
                    reliability=1.0,
                    source_refs=[
                        {
                            "source_type": "questionnaire",
                            "source_id": f"q_{organ}",
                            "span_ref": None,
                        }
                    ],
                    confirmation_status="confirmed",
                )
            )
            links.append(
                OrganEvidenceLink(
                    organ_evidence_link_id=f"oel_{organ}_{index}",
                    fact_evidence_id=fact_evidence_id,
                    organ=organ,
                    element={
                        "liver": "wood",
                        "heart": "fire",
                        "spleen": "earth",
                        "lung": "metal",
                        "kidney": "water",
                    }[organ],
                    direction="supporting",
                    link_strength=share,
                    mapping_rule_id=f"map_{claim}_{organ}_01",
                    mapping_version="organ_mapping_v3.0",
                    explanation_summary="synthetic Phase 1B fixture",
                )
            )
    return evidence, links


def aggregation_from_organ_support(
    organ_support: Mapping[str, float],
    *,
    mapping: Mapping[str, object] | None = None,
):
    evidence, links = synthetic_evidence(organ_support)
    # Organ qualification/scoring comes from the approved ORGAN mapping; the
    # five-tone mapping is only used for the organ -> tone decision output.
    return build_organ_aggregation_snapshot(
        evidence, links, mapping or organ_mapping()
    )


def decision_from_organ_support(
    organ_support: Mapping[str, float],
    *,
    conflicts: Sequence[Mapping[str, object]] = (),
    fact_claims: Mapping[str, Sequence[str]] | None = None,
    coverage_count: int | None = None,
    upstream_abstain_reason: str | None = None,
    upstream_status: str | None = None,
    assessment_revision: int = 1,
):
    """Run the real dominance service over synthetic organ support."""

    mapping = five_tone_mapping()
    rule = dominance_rule()
    aggregation = aggregation_from_organ_support(organ_support, mapping=organ_mapping())
    assets = verify_mapping_identity(
        rule, organ_mapping=organ_mapping(), five_tone_mapping=mapping
    )
    covered = (
        coverage_count
        if coverage_count is not None
        else max(4, aggregation.effective_evidence_count)
    )
    return resolve_organ_dominance(
        assessment_id="asmt_fixture",
        assessment_revision=assessment_revision,
        input_revision=1,
        aggregation=aggregation,
        conflicts=list(conflicts),
        fact_claims=(
            fact_claims
            if fact_claims is not None
            else aggregation.fact_claims_by_fact_id
        ),
        dominance_rule=rule,
        five_tone_mapping=mapping,
        assets=assets,
        confirmed_user_state_id="cus_fixture",
        confirmed_user_state_revision=1,
        confirmed_fact_count=covered,
        evidence_coverage=round(min(1.0, covered / 8.0), 3),
        upstream_abstain_reason=upstream_abstain_reason,
        upstream_status=upstream_status,
    )


def decision_from_organ_weights(
    organ_weights: Mapping[str, float],
    *,
    minimum_support: float = 0.80,
    maximum_support: float = 2.0,
    conflicts: Sequence[Mapping[str, object]] = (),
    fact_claims: Mapping[str, Sequence[str]] | None = None,
    coverage_count: int | None = None,
    upstream_abstain_reason: str | None = None,
):
    """Scale normalized organ weights into legal raw support, then route.

    Scaling preserves every ratio, so the normalized weights, margin and raw
    ratio the gates see match the caller's ``organ_weights``. The scale is
    capped so each synthetic organ support stays within unit-strength claims;
    an organ whose scaled support misses the approved raw-support threshold is
    simply not a legal candidate (exactly as in the real pipeline).
    """

    positive = {key: float(value) for key, value in organ_weights.items() if value > 0}
    if not positive:
        return decision_from_organ_support(
            {},
            conflicts=conflicts,
            fact_claims=fact_claims,
            coverage_count=coverage_count,
            upstream_abstain_reason=upstream_abstain_reason,
        )
    scale = min(
        minimum_support / min(positive.values()),
        maximum_support / max(positive.values()),
    )
    return decision_from_organ_support(
        {organ: value * scale for organ, value in positive.items()},
        conflicts=conflicts,
        fact_claims=fact_claims,
        coverage_count=coverage_count,
        upstream_abstain_reason=upstream_abstain_reason,
    )


def synthetic_decision(
    *,
    regulation_mode: str = "personalized_five_tone",
    primary_tone: str | None = None,
    dominant_organ: str | None = None,
    reason_code: str | None = None,
    legal_candidate_organs: Iterable[str] | None = None,
    margin: float | None = 0.2,
    raw_ratio: float | None = 1.5,
):
    """An explicitly shaped, valid decision for non-routing tests."""

    mapping = five_tone_mapping()
    rule = dominance_rule()
    organ_tone = {
        "liver": "jiao",
        "heart": "zhi",
        "spleen": "gong",
        "lung": "shang",
        "kidney": "yu",
    }
    if regulation_mode == "personalized_five_tone":
        dominant_organ = dominant_organ or "liver"
        primary_tone = primary_tone or organ_tone[dominant_organ]
        reason_code = reason_code or REASON_PERSONALIZED_DOMINANCE_THRESHOLDS_MET
        candidates = list(legal_candidate_organs or [dominant_organ])
        if dominant_organ not in candidates:
            candidates.insert(0, dominant_organ)
    else:
        dominant_organ = None
        primary_tone = None
        reason_code = reason_code or REASON_BASIC_NO_LEGAL_ORGAN_CANDIDATE
        candidates = list(legal_candidate_organs or [])
    from backend.app.schemas.v3.flow_v31 import (
        OrganDominanceAssetIdentity,
        OrganDominanceConflictAudit,
        OrganDominanceCoverageAudit,
        OrganDominanceDecisionV1,
        OrganDominanceGateAudit,
        OrganDominanceOrganAudit,
    )
    from backend.app.services.v3.organ_dominance_service import (
        decision_snapshot_checksum,
    )

    known_organs = (
        list(_ORGAN_CLAIMS) if _ORGAN_CLAIMS else [claims_for(o) and o for o in
        ("liver", "heart", "spleen", "lung", "kidney")]
    )
    weights = {organ: 0.0 for organ in known_organs}
    if candidates:
        share = round(1.0 / len(candidates), 4)
        for organ in candidates:
            weights[organ] = share
    assets = verify_mapping_identity(
        rule, organ_mapping=organ_mapping(), five_tone_mapping=mapping
    )
    decision = OrganDominanceDecisionV1(
        schema_id="organ_dominance_decision_v1",
        schema_version="1.0",
        assessment_id="asmt_fixture",
        assessment_revision=1,
        input_revision=1,
        confirmed_user_state_id="cus_fixture",
        confirmed_user_state_revision=1,
        coverage=OrganDominanceCoverageAudit(
            confirmed_fact_count=4,
            coverage_denominator=8,
            evidence_coverage=0.5,
            coverage_formula_version="s6_evidence_coverage_v1",
            coverage_gate_passed=True,
        ),
        organ=OrganDominanceOrganAudit(
            raw_organ_support_by_organ={organ: weights[organ] for organ in known_organs},
            effective_evidence_count_by_organ={
                organ: (2 if organ in candidates else 0) for organ in known_organs
            },
            legal_candidate_by_organ={
                organ: organ in candidates for organ in known_organs
            },
            legal_candidate_organs=candidates,
            legal_candidate_count=len(candidates),
            normalized_weights_by_organ=weights,
        ),
        dominance=OrganDominanceGateAudit(
            top1_organ=dominant_organ,
            top2_organ=None,
            normalized_top1_weight=(
                weights[dominant_organ] if dominant_organ is not None else None
            ),
            normalized_top2_weight=None,
            normalized_margin=margin if dominant_organ is not None else None,
            raw_top1_support=(
                weights[dominant_organ] if dominant_organ is not None else None
            ),
            raw_top2_support=None,
            raw_ratio=raw_ratio if dominant_organ is not None else None,
            margin_gate_state=(
                "passed" if dominant_organ is not None else "not_evaluated"
            ),
            ratio_gate_state=(
                "passed" if dominant_organ is not None else "not_evaluated"
            ),
            dominance_gate_passed=dominant_organ is not None,
        ),
        conflict=OrganDominanceConflictAudit(
            unresolved_major_conflict_ids=[],
            dominance_affecting_minor_conflict_ids=[],
            conflict_gate_passed=True,
        ),
        regulation_mode=regulation_mode,
        dominant_organ=dominant_organ,
        primary_tone=primary_tone,
        decision_reason_code=reason_code,
        assets=assets,
        decision_snapshot_checksum="sha256:" + "0" * 64,
    )
    return decision.model_copy(
        update={"decision_snapshot_checksum": decision_snapshot_checksum(decision)}
    )


_TONE_ORGAN = {
    "jiao": "liver",
    "zhi": "heart",
    "gong": "spleen",
    "shang": "lung",
    "yu": "kidney",
}


def synthetic_decision_for_profile(profile) -> object:
    """A valid decision matching an already-built tone profile (non-routing tests)."""

    tone = profile.primary_tone
    tone_code = getattr(tone, "value", tone) if tone is not None else None
    return synthetic_decision(
        regulation_mode=profile.regulation_mode,
        primary_tone=tone_code,
        dominant_organ=(
            _TONE_ORGAN[tone_code] if tone_code is not None else None
        ),
    )


