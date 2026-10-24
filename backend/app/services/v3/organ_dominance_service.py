"""Sprint 6 Phase 1B — authoritative organ dominance & ambiguity routing.

This module owns the **only** normal-path authority for the music-design
decision:

```text
regulation_mode / dominant_organ / primary_tone / decision_reason_code
```

Frozen pipeline (Sprint 6 Phase 1B):

```text
Failure Boundary (upstream, unchanged)
→ Evidence Gate          (canonical effective coverage + upstream legal abstain)
→ Legal Candidate Gate   (approved organ-mapping qualification)
→ Dominance Gate         (legal candidates only: exact raw tie, margin, ratio)
→ Conflict Gate          (dominance-affecting unresolved conflicts)
→ OrganDominanceDecisionV1
```

Design rules enforced here:

* one scoring pass produces :class:`OrganAggregationSnapshot`; nothing
  downstream recomputes raw support or re-qualifies candidates;
* the frozen numbers (denominator 8, coverage 0.50, margin 0.08, raw ratio
  1.20, precision 4dp, ``>=``) come from the approved dominance rule asset,
  never from a hard-coded copy;
* organ qualification thresholds come from the approved organ mapping; the
  dominance asset only references that identity (mismatch = readiness failure,
  never a music mode);
* technical failures are *not* modes and never reach this module;
* no provider, RAG, DB or frontend access; the service is pure and repeatable.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
import os
from hashlib import sha256
from pathlib import Path

from backend.app.schemas.v3.assessment import FactEvidence, OrganEvidenceLink
from backend.app.schemas.v3.common import Conflict, OrganCode, ToneCode
from backend.app.schemas.v3.flow_v31 import (
    FIVE_TONE_ANALYSIS_SCHEMA_VERSION_V33,
    ORGAN_DOMINANCE_DECISION_SCHEMA_ID,
    ORGAN_DOMINANCE_DECISION_SCHEMA_VERSION,
    OrganDominanceAssetIdentity,
    OrganDominanceConflictAudit,
    OrganDominanceCoverageAudit,
    OrganDominanceDecisionV1,
    OrganDominanceGateAudit,
    OrganDominanceOrganAudit,
)
from backend.app.services.v3.knowledge_assets import (
    APPROVED_DOMINANCE_RULE_CHECKSUM,
    DOMINANCE_RULE_ASSET_VERSION,
    DominanceRuleAssetNotReady,
    load_dominance_rule_asset,
)

# --------------------------------------------------------------------------- #
# reason vocabulary (frozen; mirrored by the rule asset)
# --------------------------------------------------------------------------- #

REASON_BASIC_ELEMENT_EVIDENCE_INSUFFICIENT = "BASIC_ELEMENT_EVIDENCE_INSUFFICIENT"
REASON_BASIC_RAG_EMPTY = "BASIC_RAG_EMPTY"
REASON_BASIC_EVIDENCE_COVERAGE_BELOW_THRESHOLD = "BASIC_EVIDENCE_COVERAGE_BELOW_THRESHOLD"
REASON_BASIC_NO_LEGAL_ORGAN_CANDIDATE = "BASIC_NO_LEGAL_ORGAN_CANDIDATE"
REASON_BASIC_UNRESOLVED_MAJOR_CONFLICT = "BASIC_UNRESOLVED_MAJOR_CONFLICT"
REASON_PERSONALIZED_SINGLE_LEGAL_CANDIDATE = "PERSONALIZED_SINGLE_LEGAL_CANDIDATE"
REASON_PERSONALIZED_DOMINANCE_THRESHOLDS_MET = "PERSONALIZED_DOMINANCE_THRESHOLDS_MET"
REASON_INTEGRATED_EXACT_TOP_TIE = "INTEGRATED_EXACT_TOP_TIE"
REASON_INTEGRATED_DOMINANCE_CONFLICT = "INTEGRATED_DOMINANCE_CONFLICT"
REASON_INTEGRATED_MARGIN_BELOW_THRESHOLD = "INTEGRATED_MARGIN_BELOW_THRESHOLD"
REASON_INTEGRATED_RATIO_BELOW_THRESHOLD = "INTEGRATED_RATIO_BELOW_THRESHOLD"

# --------------------------------------------------------------------------- #
# Abstain-reason vocabulary (CLOSED). Classification is by exact recognized
# code (case-insensitive, whitespace-trimmed) — never by substring markers, and
# never by an open-ended default.
#
#   legal business abstain      -> basic_wellness (the only tolerated class)
#   safety/authority/readiness/ -> non-mode (readiness failure; withheld by the
#   technical codes                frozen contract, never a music mode)
#   anything else               -> explicit fail-closed readiness failure
# --------------------------------------------------------------------------- #

# The only classes that may become ``basic_wellness`` through normalization.
LEGAL_ABSTAIN_REASON_ALIASES: Mapping[str, str] = {
    "ELEMENT_EVIDENCE_INSUFFICIENT": REASON_BASIC_ELEMENT_EVIDENCE_INSUFFICIENT,
    "INSUFFICIENT_EVIDENCE": REASON_BASIC_ELEMENT_EVIDENCE_INSUFFICIENT,
    "EVIDENCE_INSUFFICIENT": REASON_BASIC_ELEMENT_EVIDENCE_INSUFFICIENT,
    "evidence_insufficient": REASON_BASIC_ELEMENT_EVIDENCE_INSUFFICIENT,
    "RAG_EMPTY": REASON_BASIC_RAG_EMPTY,
    "UNRESOLVED_MAJOR_CONFLICT": REASON_BASIC_UNRESOLVED_MAJOR_CONFLICT,
}

# Safety / authority: withheld or authoritative-state non-mode handling.
_NON_MODE_SAFETY_AUTHORITY: frozenset[str] = frozenset(
    {
        "SAFETY_BLOCKED",
        "ASSESSMENT_NOT_CONFIRMED",
        "ASSESSMENT_SNAPSHOT_CONFLICT",
        "ASSESSMENT_SNAPSHOT_INVALID",
        "ASSESSMENT_AGGREGATION_NOT_READY",
        "CONFIRMED_USER_STATE_INVALID",
        "CONFIRMED_USER_STATE_NOT_CONFIRMED",
        "CONFIRMED_USER_STATE_NOT_CURRENT",
        "CONFIRMED_USER_STATE_NOT_OWNED",
        "DOMINANCE_ABSTAIN_REASON_MISSING",
        "DOMINANCE_ABSTAIN_REASON_NOT_A_MODE",
        "DOMINANCE_ABSTAIN_REASON_UNCLASSIFIED",
        "DOMINANCE_CANDIDATE_POLICY_MISMATCH",
        "DOMINANCE_DECISION_CONFLICT",
        "DOMINANCE_DECISION_NOT_PERSISTED",
        "DOMINANCE_DECISION_REQUIRED",
        "DOMINANCE_DECISION_TONE_MISMATCH",
        "DOMINANCE_MAPPING_IDENTITY_MISMATCH",
        "DOMINANCE_TONE_MAPPING_INVALID",
        "DOMINANCE_TONE_MAPPING_MISMATCH",
        "DOMINANCE_UPSTREAM_FAILED",
        "AGENT3_NOT_READY",
    }
)

# Readiness: approved-asset / manifest / ingestion / configuration problems.
_NON_MODE_READINESS: frozenset[str] = frozenset(
    {
        "RAG_UNAVAILABLE",
        "RAG_NOT_READY",
        "RAG_MANIFEST_NOT_READY",
        "RAG_MANIFEST_MISMATCH",
        "RAG_MANIFEST_ID_MISMATCH",
        "RAG_INDEX_UNAVAILABLE",
        "RAG_INDEX_COUNT_MISMATCH",
        "RAG_DISTANCE_METRIC_MISMATCH",
        "RAG_DISTANCE_METRIC_NOT_APPROVED",
        "RAG_KNOWLEDGE_VERSION_MISMATCH",
        "RAG_INVALID_RESULT",
        "RAG_INGESTION_NOT_APPROVED",
        "RAG_QUERY_MAPPING_NOT_APPROVED",
        "RAG_UNAPPROVED_CHUNK",
        "CORPUS_CHUNK_COUNT_MISMATCH",
        "MEDICAL_RULE_ASSET_NOT_READY",
        "MEDICAL_RULE_ASSET_NOT_CONFIGURED",
        "MEDICAL_RULE_ASSET_INVALID",
        "MEDICAL_RULE_ASSET_NOT_APPROVED",
        "MEDICAL_RULE_ASSET_CHECKSUM_MISMATCH",
        "MEDICAL_RULE_CHECKSUM_NOT_APPROVED",
        "MEDICAL_RULE_CODES_INVALID",
        "MEDICAL_RULE_CODES_NOT_APPROVED",
        "MEDICAL_RULE_VERSION_MISMATCH",
        "MEDICAL_RULE_VERSION_NOT_APPROVED",
        "MEDICAL_ASSET_UNAVAILABLE",
        "ORGAN_MAPPING_ASSET_NOT_READY",
        "MUSIC_PARAMETER_ASSET_NOT_READY",
        "MUSIC_PARAMETER_ASSET_NOT_CONFIGURED",
        "MUSIC_PARAMETER_ASSET_INVALID",
        "MUSIC_PARAMETER_ASSET_NOT_APPROVED",
        "MUSIC_PARAMETER_ASSET_CHECKSUM_MISMATCH",
        "MUSIC_PARAMETER_ASSET_SCHEMA_INVALID",
        "MUSIC_PARAMETER_ASSET_VERSION_MISMATCH",
        "MUSIC_PARAMETER_ASSET_UNAVAILABLE",
        "DOMINANCE_RULE_ASSET_NOT_READY",
        "DOMINANCE_RULE_ASSET_NOT_CONFIGURED",
        "DOMINANCE_RULE_ASSET_INVALID",
        "DOMINANCE_RULE_ASSET_NOT_APPROVED",
        "DOMINANCE_RULE_ASSET_CHECKSUM_MISMATCH",
        "DOMINANCE_RULE_ASSET_SCHEMA_INVALID",
        "DOMINANCE_RULE_ASSET_VERSION_MISMATCH",
        "FIVE_TONE_SNAPSHOT_INVALID",
        "FIVE_TONE_SNAPSHOT_NOT_READY",
        "GENERATION_SPEC_INVALID",
        "GENERATION_SPEC_NOT_READY",
        "GENERATION_SPEC_TONE_MISMATCH",
        "V31_PROVIDER_CHAIN_NOT_READY",
        "V31_PIPELINE_FAILED",
        "DIAGNOSIS_NOT_AVAILABLE",
        "DIAGNOSIS_REQUEST_INVALID",
        "DIAGNOSIS_RESPONSE_INVALID",
        "INVALID_DIAGNOSIS_REFERENCE",
        "INVALID_DOMINANCE_DECISION",
        "INVALID_GENERATION_SPEC",
        "INVALID_SECONDARY_THRESHOLD",
        "INSUFFICIENT_ORGAN_EVIDENCE",
        "INSUFFICIENT_EVIDENCE_REFERENCES",
        "MAPPING_VERSION_MISMATCH",
        "USER_GOAL_INVALID",
        "USER_GOAL_RULE_NOT_APPROVED",
    }
)

# Technical: provider / transport / schema / reference integrity failures.
_NON_MODE_TECHNICAL: frozenset[str] = frozenset(
    {
        "MODEL_SCHEMA_INVALID",
        "DIAGNOSIS_FAILED",
        "DIAGNOSIS_SCHEMA_INVALID",
        "DIAGNOSIS_PROVIDER_NOT_CONFIGURED",
        "DIAGNOSIS_PROVIDER_TIMEOUT",
        "DIAGNOSIS_PROVIDER_RATE_LIMITED",
        "DIAGNOSIS_PROVIDER_UNAVAILABLE",
        "CONNECTION_TIMEOUT",
        "READ_TIMEOUT",
        "RATE_LIMITED",
        "EMPTY_RESPONSE",
        "INVALID_JSON",
        "JSON_REPAIR_FAILED",
        "SCHEMA_VIOLATION",
        "CHUNK_REFERENCE_INVALID",
        "FACT_REFERENCE_INVALID",
        "DUPLICATE_EVIDENCE_REFERENCE",
        "EVIDENCE_DIRECTION_MISMATCH",
        "SYNDROME_NOT_APPROVED",
    }
)

NON_MODE_ABSTAIN_REASONS: Mapping[str, str] = {
    **{code: "safety_or_authority" for code in _NON_MODE_SAFETY_AUTHORITY},
    **{code: "readiness" for code in _NON_MODE_READINESS},
    **{code: "technical" for code in _NON_MODE_TECHNICAL},
}

_LEGAL_ABSTAIN_LOOKUP: Mapping[str, str] = {
    key.casefold(): value for key, value in LEGAL_ABSTAIN_REASON_ALIASES.items()
}
_NON_MODE_LOOKUP: Mapping[str, str] = {
    key.casefold(): value for key, value in NON_MODE_ABSTAIN_REASONS.items()
}

ABSTAIN_REASON_CLASS_LEGAL = "legal"
ABSTAIN_REASON_CLASS_NON_MODE = "non_mode"
ABSTAIN_REASON_CLASS_UNCLASSIFIED = "unclassified"
ABSTAIN_REASON_CLASS_MISSING = "missing"


def classify_abstain_reason(reason: str | None) -> str:
    """The single classification seam: exact code, closed vocabulary."""

    text = str(reason or "").strip()
    if not text:
        return ABSTAIN_REASON_CLASS_MISSING
    folded = text.casefold()
    if folded in _LEGAL_ABSTAIN_LOOKUP:
        return ABSTAIN_REASON_CLASS_LEGAL
    if folded in _NON_MODE_LOOKUP:
        return ABSTAIN_REASON_CLASS_NON_MODE
    return ABSTAIN_REASON_CLASS_UNCLASSIFIED


def is_non_mode_abstain_reason(reason: str) -> bool:
    """True for the recognized safety/authority/readiness/technical codes."""

    return str(reason or "").strip().casefold() in _NON_MODE_LOOKUP


def normalize_legal_abstain_reason(reason: str) -> str:
    """Map an upstream legal-abstain reason to its frozen basic reason.

    Closed vocabulary: only the recognized legal aliases become
    ``basic_wellness``. Recognized non-mode codes raise
    ``DOMINANCE_ABSTAIN_REASON_NOT_A_MODE``; an empty reason raises
    ``DOMINANCE_ABSTAIN_REASON_MISSING``; **anything else fails closed** with
    ``DOMINANCE_ABSTAIN_REASON_UNCLASSIFIED`` — an unknown or future
    technical/readiness code can never be converted into a business mode.
    """

    text = str(reason or "").strip()
    if not text:
        raise DominanceReadinessError(
            "DOMINANCE_ABSTAIN_REASON_MISSING",
            "上游中止结果缺少可判定的原因，已停止推断音乐模式。",
        )
    folded = text.casefold()
    mapped = _LEGAL_ABSTAIN_LOOKUP.get(folded)
    if mapped is not None:
        return mapped
    if folded in _NON_MODE_LOOKUP:
        raise DominanceReadinessError(
            "DOMINANCE_ABSTAIN_REASON_NOT_A_MODE",
            "技术、就绪、安全或权威类原因不得转为音乐模式。",
        )
    raise DominanceReadinessError(
        "DOMINANCE_ABSTAIN_REASON_UNCLASSIFIED",
        "上游中止原因不在已批准词表内，已按未分类状态停止推断音乐模式。",
    )


# Fixed organ order for deterministic *audit display* only. It never breaks a
# medical tie: the frozen tie rule is canonical raw support equality.
AUDIT_ORGAN_ORDER: tuple[str, ...] = tuple(organ.value for organ in OrganCode)

DEFAULT_DOMINANCE_RULE_FILENAME = "dominance-rule-v1.json"


class DominanceReadinessError(RuntimeError):
    """A Phase 1B readiness failure — never a music mode."""

    def __init__(self, error_code: str, safe_message: str) -> None:
        self.error_code = error_code
        self.safe_message = safe_message
        super().__init__(f"{error_code}: {safe_message}")


# --------------------------------------------------------------------------- #
# Step 3 — canonical effective evidence population & coverage
# --------------------------------------------------------------------------- #


def conflict_rules_of(mapping: Mapping[str, object]) -> set[str]:
    """``conflict_rules`` rule names declared by the approved organ mapping."""

    raw = mapping.get("conflict_rules")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return set()
    return {
        str(item["rule"])
        for item in raw
        if isinstance(item, Mapping) and item.get("rule")
    }


def is_questionnaire_evidence(item: FactEvidence) -> bool:
    return any(ref.source_type == "questionnaire" for ref in item.source_refs)


def shares_source(left: FactEvidence, right: FactEvidence) -> bool:
    left_sources = {(ref.source_type, ref.source_id) for ref in left.source_refs}
    right_sources = {(ref.source_type, ref.source_id) for ref in right.source_refs}
    return bool(left_sources & right_sources)


def select_effective_evidence(
    evidence: Sequence[FactEvidence],
    mapping: Mapping[str, object],
) -> list[FactEvidence]:
    """One effective ``FactEvidence`` per claim_code (approved source priority).

    ``conflict_rules.questionnaire_priority``: the questionnaire's deterministic
    score wins and is never overridden by provider-extracted facts — without
    this selection a multi-organ claim present from both the questionnaire and a
    document would be scored twice (once per source). Within one priority class
    the highest-reliability item wins; ties are broken deterministically by
    fact_id.
    """

    if "questionnaire_priority" not in conflict_rules_of(mapping):
        return list(evidence)
    by_claim: dict[str, list[FactEvidence]] = {}
    for item in evidence:
        by_claim.setdefault(item.claim_code, []).append(item)
    return [
        max(
            items,
            key=lambda item: (
                is_questionnaire_evidence(item),
                item.reliability,
                item.fact_id,
            ),
        )
        for items in by_claim.values()
    ]


def confirmed_evidence(evidence: Sequence[FactEvidence]) -> list[FactEvidence]:
    """Only confirmed facts count: unconfirmed/rejected facts never do."""

    return [item for item in evidence if item.confirmation_status == "confirmed"]


def canonical_effective_evidence(
    evidence: Sequence[FactEvidence],
    mapping: Mapping[str, object],
) -> list[FactEvidence]:
    """The authoritative Phase 1B evidence population (confirmed + deduped)."""

    return select_effective_evidence(confirmed_evidence(evidence), mapping)


def canonical_evidence_coverage(
    evidence: Sequence[FactEvidence],
    mapping: Mapping[str, object],
    *,
    denominator: int = 8,
) -> tuple[int, float]:
    """``(effective_confirmed_fact_count, evidence_coverage)``.

    ``evidence_coverage = min(1.0, effective_confirmed_fact_count / 8)`` over the
    *effective* (post source-priority dedupe) confirmed population: supporting
    and contradicting facts both count because coverage measures confirmed
    information quantity. This is the Phase 1B correction — the legacy public
    assessment field keeps its own frozen ``confirmed_available_source_coverage``
    semantics and is not reused here.
    """

    count = len(canonical_effective_evidence(evidence, mapping))
    denominator = int(denominator) or 1
    return count, round(min(1.0, count / denominator), 3)


# --------------------------------------------------------------------------- #
# Step 4 — canonical organ aggregation snapshot (one scoring pass)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class OrganAggregationSnapshot:
    """Authoritative result of the single organ scoring pass.

    Raw support, effective evidence counts, legal-candidate qualification and
    normalized weights are produced together so no downstream consumer has to
    recompute or re-qualify anything.
    """

    is_available: bool
    effective_evidence_count: int
    raw_support_by_organ: dict[str, float]
    effective_evidence_count_by_organ: dict[str, int]
    legal_candidate_by_organ: dict[str, bool]
    legal_candidate_organs: tuple[str, ...]
    normalized_weights_by_organ: dict[str, float]
    contributing_claims_by_organ: dict[str, tuple[str, ...]]
    fact_claims_by_fact_id: dict[str, tuple[str, ...]]
    minimum_raw_support: float
    minimum_effective_evidence_count: int

    @property
    def legal_candidate_count(self) -> int:
        return len(self.legal_candidate_organs)

    def normalized(self, organ: str) -> float:
        return float(self.normalized_weights_by_organ.get(organ, 0.0))


def build_organ_aggregation_snapshot(
    evidence: Sequence[FactEvidence],
    links: Sequence[OrganEvidenceLink],
    mapping: Mapping[str, object],
) -> OrganAggregationSnapshot:
    """One scoring pass over the approved single/combination/multi-organ rules.

    Behaviour is the frozen Phase 1A/0 scoring (bit-identical weights) extended
    with the raw support, effective evidence count, legal-candidate and
    contributing-claim bookkeeping Phase 1B needs for the dominance and conflict
    gates.
    """

    population = canonical_effective_evidence(evidence, mapping)
    # Conflict linkage provenance: indexed over the whole population handed to
    # the scoring pass (conflicts reference the facts they were built from).
    fact_claims = fact_claim_index(evidence)
    effective_ids = {item.fact_evidence_id for item in population}
    scoped_links = [link for link in links if link.fact_evidence_id in effective_ids]
    links_by_evidence: dict[str, list[OrganEvidenceLink]] = {}
    for link in scoped_links:
        links_by_evidence.setdefault(link.fact_evidence_id, []).append(link)
    reliability_by_evidence = {ev.fact_evidence_id: ev.reliability for ev in population}

    thresholds = mapping.get("thresholds")
    thresholds = thresholds if isinstance(thresholds, Mapping) else {}
    minimum_total_support = float(thresholds.get("minimum_total_support", 0.0))
    minimum_evidence_count = int(
        thresholds.get("minimum_evidence_count", 2)
    )

    support: dict[str, float] = {organ.value: 0.0 for organ in OrganCode}
    observed_count: dict[str, int] = {organ.value: 0 for organ in OrganCode}
    observed_support: dict[str, float] = {organ.value: 0.0 for organ in OrganCode}
    contributing: dict[str, tuple[str, ...]] = {
        organ.value: () for organ in OrganCode
    }
    qualified: dict[str, bool] = {organ.value: False for organ in OrganCode}
    base_link_keys: set[tuple[str, str]] = set()
    rules = conflict_rules_of(mapping)

    for rule in mapping.get("combination_rules", []) or []:
        if not isinstance(rule, Mapping):
            continue
        organ = OrganCode(rule["organ"]).value
        claims = set(rule.get("claims") or [])
        present_by_claim: dict[str, tuple[FactEvidence, OrganEvidenceLink]] = {}
        for ev in population:
            if ev.claim_code not in claims:
                continue
            if (
                "worry_control_vs_overthinking" in rules
                and ev.claim_code == "worry_control"
                and any(
                    other.claim_code == "overthinking_tendency"
                    and shares_source(ev, other)
                    for other in population
                )
            ):
                continue
            organ_links = [
                link
                for link in links_by_evidence.get(ev.fact_evidence_id, [])
                if link.organ.value == organ
            ]
            if not organ_links:
                continue
            link = max(organ_links, key=lambda item: item.link_strength)
            current = present_by_claim.get(ev.claim_code)
            ev_priority = (is_questionnaire_evidence(ev), ev.reliability)
            current_priority = (
                (
                    is_questionnaire_evidence(current[0]),
                    current[0].reliability,
                )
                if current is not None
                else None
            )
            if current is None or ev_priority > current_priority:
                present_by_claim[ev.claim_code] = (ev, link)
        observed_count[organ] = len(present_by_claim)
        minimum_count = int(rule.get("min_count", minimum_evidence_count))
        signed = 0.0
        for ev, link in present_by_claim.values():
            base_link_keys.add((ev.fact_evidence_id, organ))
            direction_signed = 1.0 if link.direction == "supporting" else -1.0
            signed += (
                float(link.link_strength)
                * reliability_by_evidence[ev.fact_evidence_id]
                * direction_signed
            )
        observed_support[organ] = signed
        if len(present_by_claim) < minimum_count:
            continue
        if signed >= minimum_total_support:
            support[organ] = signed
            qualified[organ] = True
            contributing[organ] = tuple(sorted(present_by_claim))

    available = {organ: value for organ, value in support.items() if value > 0}
    if not available:
        return _snapshot(
            is_available=False,
            population=population,
            raw_support=observed_support,
            observed_count=observed_count,
            qualified=qualified,
            contributing=contributing,
            fact_claims=fact_claims,
            normalized={organ.value: 0.0 for organ in OrganCode},
            available_organs=(),
            minimum_total_support=minimum_total_support,
            minimum_evidence_count=minimum_evidence_count,
        )

    multi_rule_ids = {
        link["mapping_rule_id"]
        for rule in mapping.get("multi_organ_rules", []) or []
        if isinstance(rule, Mapping)
        for link in (rule.get("links") or [])
        if isinstance(link, Mapping)
    }
    sleep_claims = {"sleep_disturbance", "unrefreshing_sleep"}
    sleep_max: dict[tuple[str, str], float] = {}
    additional_multi: dict[str, float] = {organ: 0.0 for organ in available}
    for ev in population:
        for link in links_by_evidence.get(ev.fact_evidence_id, []):
            organ = link.organ.value
            if (
                link.mapping_rule_id not in multi_rule_ids
                or organ not in available
                or (ev.fact_evidence_id, organ) in base_link_keys
            ):
                continue
            signed = (
                float(link.link_strength)
                * ev.reliability
                * (1.0 if link.direction == "supporting" else -1.0)
            )
            if (
                "sleep_multi_organ_no_double_count" in rules
                and ev.claim_code in sleep_claims
            ):
                for source in ev.source_refs:
                    key = (source.source_id, organ)
                    sleep_max[key] = max(sleep_max.get(key, 0.0), signed)
            else:
                additional_multi[organ] += signed
    for (_source_id, organ), value in sleep_max.items():
        additional_multi[organ] += value

    raw_support = dict(observed_support)
    for organ, value in available.items():
        raw_support[organ] = value + additional_multi.get(organ, 0.0)
    available = {
        organ: value for organ, value in available.items() if raw_support[organ] > 0
    }
    total = sum(raw_support[organ] for organ in available)
    normalized = {organ.value: 0.0 for organ in OrganCode}
    for organ in available:
        normalized[organ] = round(raw_support[organ] / total, 4)

    return _snapshot(
        is_available=True,
        population=population,
        raw_support=raw_support,
        observed_count=observed_count,
        qualified=qualified,
        contributing=contributing,
        fact_claims=fact_claims,
        normalized=normalized,
        available_organs=tuple(available),
        minimum_total_support=minimum_total_support,
        minimum_evidence_count=minimum_evidence_count,
    )


def _snapshot(
    *,
    is_available: bool,
    population: Sequence[FactEvidence],
    raw_support: Mapping[str, float],
    observed_count: Mapping[str, int],
    qualified: Mapping[str, bool],
    contributing: Mapping[str, tuple[str, ...]],
    fact_claims: Mapping[str, tuple[str, ...]],
    normalized: Mapping[str, float],
    available_organs: Sequence[str],
    minimum_total_support: float,
    minimum_evidence_count: int,
) -> OrganAggregationSnapshot:
    legal = tuple(
        organ
        for organ in AUDIT_ORGAN_ORDER
        if qualified.get(organ) and organ in available_organs
    )
    return OrganAggregationSnapshot(
        is_available=is_available,
        effective_evidence_count=len(population),
        raw_support_by_organ={organ: raw_support.get(organ, 0.0) for organ in AUDIT_ORGAN_ORDER},
        effective_evidence_count_by_organ={
            organ: int(observed_count.get(organ, 0)) for organ in AUDIT_ORGAN_ORDER
        },
        legal_candidate_by_organ={
            organ: bool(qualified.get(organ) and organ in available_organs)
            for organ in AUDIT_ORGAN_ORDER
        },
        legal_candidate_organs=legal,
        normalized_weights_by_organ={
            organ: float(normalized.get(organ, 0.0)) for organ in AUDIT_ORGAN_ORDER
        },
        contributing_claims_by_organ={
            organ: tuple(contributing.get(organ, ())) for organ in AUDIT_ORGAN_ORDER
        },
        fact_claims_by_fact_id={
            str(key): tuple(value) for key, value in fact_claims.items()
        },
        minimum_raw_support=minimum_total_support,
        minimum_effective_evidence_count=minimum_evidence_count,
    )


# --------------------------------------------------------------------------- #
# Step 5 — OrganDominanceDecisionV1 + pure dominance service
# --------------------------------------------------------------------------- #


def load_configured_dominance_rule() -> dict[str, object]:
    """Load the approved dominance rule asset from configuration.

    Mirrors the approved-asset convention: path/version/checksum are
    configurable, and a missing/unapproved/tampered asset is a readiness
    failure (never a music mode).
    """

    default_path = (
        Path(__file__).resolve().parents[4]
        / "knowledge"
        / "v3"
        / DEFAULT_DOMINANCE_RULE_FILENAME
    )
    path = os.getenv("V31_DOMINANCE_RULE_PATH", "").strip() or str(default_path)
    version = (
        os.getenv("V31_DOMINANCE_RULE_VERSION", "").strip()
        or DOMINANCE_RULE_ASSET_VERSION
    )
    checksum = (
        os.getenv("V31_DOMINANCE_RULE_CHECKSUM", "").strip()
        or APPROVED_DOMINANCE_RULE_CHECKSUM
    )
    return load_dominance_rule_asset(
        path, expected_version=version, expected_checksum=checksum
    )


def organ_tone_map(mapping: Mapping[str, object]) -> dict[str, str]:
    """Approved organ→tone mapping read from the five-tone mapping asset."""

    table = mapping.get("organ_tone_table")
    if not isinstance(table, Sequence) or isinstance(table, (str, bytes)):
        raise DominanceReadinessError(
            "DOMINANCE_TONE_MAPPING_INVALID",
            "五音映射资产缺少 organ_tone_table。",
        )
    resolved: dict[str, str] = {}
    for row in table:
        if not isinstance(row, Mapping):
            continue
        organ = str(row.get("organ", "")).strip()
        tone = str(row.get("tone", "")).strip()
        if organ in AUDIT_ORGAN_ORDER and tone in {item.value for item in ToneCode}:
            resolved[organ] = tone
    if set(resolved) != set(AUDIT_ORGAN_ORDER):
        raise DominanceReadinessError(
            "DOMINANCE_TONE_MAPPING_INVALID",
            "五音映射资产的脏腑—音对应不完整。",
        )
    return resolved


def verify_mapping_identity(
    rule: Mapping[str, object],
    *,
    organ_mapping: Mapping[str, object],
    five_tone_mapping: Mapping[str, object],
) -> OrganDominanceAssetIdentity:
    """Mapping identity mismatch is a readiness failure, never ``basic_wellness``."""

    references = rule.get("references")
    if not isinstance(references, Mapping):  # pragma: no cover - asset validated
        raise DominanceReadinessError(
            "DOMINANCE_RULE_ASSET_INVALID",
            "主导度规则资产缺少映射引用。",
        )

    def _identity(key: str, asset: Mapping[str, object], label: str) -> tuple[str, str]:
        expected = references.get(key)
        if not isinstance(expected, Mapping):  # pragma: no cover
            raise DominanceReadinessError(
                "DOMINANCE_RULE_ASSET_INVALID",
                "主导度规则资产缺少映射引用。",
            )
        version = f"{asset.get('schema_id')}@{asset.get('schema_version')}"
        checksum = str(asset.get("content_checksum", ""))
        expected_version = (
            f"{expected.get('schema_id')}@{expected.get('schema_version')}"
        )
        if version != expected_version or checksum != expected.get("content_checksum"):
            raise DominanceReadinessError(
                "DOMINANCE_MAPPING_IDENTITY_MISMATCH",
                f"{label}资产身份与主导度规则引用不一致。",
            )
        return version, checksum

    organ_version, organ_checksum = _identity("organ_mapping", organ_mapping, "脏腑映射")
    tone_version, tone_checksum = _identity("five_tone_mapping", five_tone_mapping, "五音映射")
    return OrganDominanceAssetIdentity(
        organ_mapping_version=organ_version,
        organ_mapping_checksum=organ_checksum,
        five_tone_mapping_version=tone_version,
        five_tone_mapping_checksum=tone_checksum,
        dominance_rule_version=str(rule.get("asset_version", "")),
        dominance_rule_checksum=str(rule.get("content_checksum", "")),
    )


def verify_candidate_policy_consistency(
    rule: Mapping[str, object],
    *,
    organ_mapping: Mapping[str, object],
) -> None:
    """Readiness check: the approved organ mapping stays the candidate authority.

    The dominance asset only *documents* the candidate policy; the mapping is
    what routing reads. A drift between the two would silently change which
    organs qualify, so any mismatch is a readiness failure.
    """

    gate = rule.get("legal_candidate_gate")
    gate = gate if isinstance(gate, Mapping) else {}
    thresholds = organ_mapping.get("thresholds")
    thresholds = thresholds if isinstance(thresholds, Mapping) else {}
    expected_count = gate.get("minimum_effective_evidence_count")
    expected_support = gate.get("minimum_raw_support")
    actual_count = thresholds.get("minimum_evidence_count")
    actual_support = thresholds.get("minimum_total_support")
    per_rule_counts = {
        int(item.get("min_count"))
        for item in (organ_mapping.get("combination_rules") or [])
        if isinstance(item, Mapping) and item.get("min_count") is not None
    }
    if (
        expected_count is None
        or expected_support is None
        or actual_count != expected_count
        or per_rule_counts != {int(expected_count)}
        or actual_support is None
        or abs(float(actual_support) - float(expected_support)) > 1e-9
    ):
        raise DominanceReadinessError(
            "DOMINANCE_CANDIDATE_POLICY_MISMATCH",
            "主导度规则与已批准脏腑映射的候选阈值不一致。",
        )


def fact_claim_index(
    evidence: Sequence[FactEvidence],
) -> dict[str, tuple[str, ...]]:
    """``fact_id -> claim_codes`` index used by the conflict linkage."""

    index: dict[str, set[str]] = {}
    for item in evidence:
        index.setdefault(item.fact_id, set()).add(item.claim_code)
    return {key: tuple(sorted(value)) for key, value in index.items()}


def _is_unresolved(item: Mapping[str, object]) -> bool:
    return str(item.get("resolution_status", "")) == "unresolved"


def _conflict_id(item: Mapping[str, object]) -> str:
    return str(item.get("conflict_id", ""))


def _conflict_fact_ids(item: Mapping[str, object]) -> tuple[str, ...]:
    raw = item.get("fact_ids")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return ()
    return tuple(str(value) for value in raw)


def dominance_affecting_minor_conflict_ids(
    *,
    conflicts: Sequence[Mapping[str, object] | Conflict],
    fact_claims: Mapping[str, Sequence[str]],
    target_organs: Sequence[str],
    contributing_claims_by_organ: Mapping[str, Sequence[str]],
) -> list[str]:
    """Unresolved minor conflicts touching the only/top1/top2 candidate evidence.

    Frozen linkage (all persisted fields; no invented relation):

    ``conflict.fact_ids`` → persisted evidence ``fact_id`` → ``claim_code`` →
    contributing claims recorded by the canonical aggregation snapshot for the
    only legal candidate (single-candidate case) or the top1/top2 legal
    candidates.
    """

    relevant: set[str] = set()
    for organ in target_organs:
        relevant.update(contributing_claims_by_organ.get(organ, ()))
    if not relevant:
        return []
    affected: list[str] = []
    for raw in conflicts:
        item = raw if isinstance(raw, Mapping) else raw.model_dump(mode="json")
        if str(item.get("severity")) != "minor" or not _is_unresolved(item):
            continue
        claims: set[str] = set()
        for fact_id in _conflict_fact_ids(item):
            claims.update(fact_claims.get(fact_id, ()))
        if claims & relevant:
            affected.append(_conflict_id(item))
    return sorted(set(affected))


def unresolved_major_conflict_ids(
    conflicts: Sequence[Mapping[str, object] | Conflict],
) -> list[str]:
    ids: list[str] = []
    for raw in conflicts:
        item = raw if isinstance(raw, Mapping) else raw.model_dump(mode="json")
        if str(item.get("severity")) == "major" and _is_unresolved(item):
            ids.append(_conflict_id(item))
    return sorted(set(ids))


def _rank_legal_candidates(
    aggregation: OrganAggregationSnapshot,
) -> list[tuple[str, float]]:
    """Legal candidates ranked by canonical raw support (audit order breaks display only)."""

    ranked = [
        (organ, float(aggregation.raw_support_by_organ.get(organ, 0.0)))
        for organ in aggregation.legal_candidate_organs
    ]
    ranked.sort(key=lambda item: (-item[1], AUDIT_ORGAN_ORDER.index(item[0])))
    return ranked


def resolve_organ_dominance(
    *,
    assessment_id: str,
    assessment_revision: int,
    input_revision: int,
    aggregation: OrganAggregationSnapshot,
    conflicts: Sequence[Mapping[str, object] | Conflict],
    fact_claims: Mapping[str, Sequence[str]],
    dominance_rule: Mapping[str, object],
    five_tone_mapping: Mapping[str, object],
    assets: OrganDominanceAssetIdentity,
    confirmed_user_state_id: str | None = None,
    confirmed_user_state_revision: int | None = None,
    evidence_coverage: float | None = None,
    confirmed_fact_count: int | None = None,
    upstream_abstain_reason: str | None = None,
    upstream_status: str | None = None,
) -> OrganDominanceDecisionV1:
    """Resolve the authoritative Phase 1B music-design decision (pure).

    Frozen reason precedence (Sprint 6 Phase 1B rule asset):

    1. upstream legal abstain mapping (``ELEMENT_EVIDENCE_INSUFFICIENT`` /
       ``RAG_EMPTY``) and the unresolved major-conflict / coverage /
       zero-candidate evidence gates → ``basic_wellness``;
    2. one legal candidate → ``personalized_five_tone`` unless a
       dominance-affecting unresolved minor conflict touches it;
    3. two or more legal candidates, legal candidates only: exact canonical raw
       tie → ``integrated_regulation``; dominance-affecting minor conflict →
       ``integrated_regulation``; normalized margin < 0.08 → integrated; raw
       ratio < 1.20 → integrated; otherwise ``personalized_five_tone``.

    Gate states record what was actually evaluated: ``not_evaluated`` when an
    earlier gate stopped routing, ``not_applicable_single_candidate`` for the
    single-candidate policy (whose margin/ratio values are null, never 0 or
    Infinity).
    """

    evidence_gate = dominance_rule.get("evidence_gate")
    evidence_gate = evidence_gate if isinstance(evidence_gate, Mapping) else {}
    dominance_gate = dominance_rule.get("dominance_gate")
    dominance_gate = dominance_gate if isinstance(dominance_gate, Mapping) else {}
    denominator = int(evidence_gate.get("denominator", 8))
    minimum_coverage = float(evidence_gate.get("minimum_coverage", 0.50))
    margin_threshold = float(dominance_gate.get("normalized_margin_threshold", 0.08))
    ratio_threshold = float(dominance_gate.get("raw_ratio_threshold", 1.20))
    coverage_formula_version = str(
        evidence_gate.get("coverage_formula_version", "s6_evidence_coverage_v1")
    )

    count = (
        int(confirmed_fact_count)
        if confirmed_fact_count is not None
        else aggregation.effective_evidence_count
    )
    coverage = (
        float(evidence_coverage)
        if evidence_coverage is not None
        else round(min(1.0, count / denominator), 3)
    )
    coverage_passed = coverage >= minimum_coverage

    ranked = _rank_legal_candidates(aggregation)
    single_candidate = len(ranked) == 1
    two_or_more = len(ranked) >= 2
    top1 = ranked[0] if ranked else None
    top2 = ranked[1] if two_or_more else None
    normalized_margin: float | None = None
    raw_ratio: float | None = None
    raw_margin = 0.0
    if two_or_more:
        raw_margin = top1[1] - top2[1]
        normalized_margin = round(
            aggregation.normalized(top1[0]) - aggregation.normalized(top2[0]), 4
        )
        raw_ratio = round(top1[1] / top2[1], 6) if top2[1] != 0 else None
    margin_ok = normalized_margin is not None and normalized_margin >= margin_threshold
    ratio_ok = raw_ratio is not None and raw_ratio >= ratio_threshold

    major_ids = unresolved_major_conflict_ids(conflicts)
    minor_ids = dominance_affecting_minor_conflict_ids(
        conflicts=conflicts,
        fact_claims=fact_claims,
        target_organs=[organ for organ, _value in ranked[:2]],
        contributing_claims_by_organ=aggregation.contributing_claims_by_organ,
    )

    mode: str
    reason: str
    dominant_organ: str | None = None
    primary_tone: str | None = None
    dominance_passed = False
    branch = "evidence"
    if upstream_status == "failed":
        # A technical failure is never a mode (defence in depth: the pipeline
        # raises before this point).
        raise DominanceReadinessError(
            "DOMINANCE_UPSTREAM_FAILED",
            "上游技术失败不得转为音乐模式。",
        )
    # An *explicitly provided* reason (even an empty/whitespace one) counts as an
    # abstain signal; ``None`` means "not an abstain". Nothing relies on an
    # empty string meaning "no abstain", and treating it as one would let an
    # empty reason fall through to the evidence gates.
    abstained = upstream_status == "abstained" or (
        upstream_status is None and upstream_abstain_reason is not None
    )
    upstream_reason = (
        normalize_legal_abstain_reason(upstream_abstain_reason or "")
        if abstained
        else None
    )

    if upstream_reason is not None:
        mode, reason = "basic_wellness", upstream_reason
    elif not coverage_passed:
        mode, reason = "basic_wellness", REASON_BASIC_EVIDENCE_COVERAGE_BELOW_THRESHOLD
    elif aggregation.legal_candidate_count == 0:
        mode, reason = "basic_wellness", REASON_BASIC_NO_LEGAL_ORGAN_CANDIDATE
    elif major_ids:
        mode, reason = "basic_wellness", REASON_BASIC_UNRESOLVED_MAJOR_CONFLICT
    elif single_candidate:
        branch = "single"
        if minor_ids:
            mode, reason = "integrated_regulation", REASON_INTEGRATED_DOMINANCE_CONFLICT
        else:
            mode, reason = (
                "personalized_five_tone",
                REASON_PERSONALIZED_SINGLE_LEGAL_CANDIDATE,
            )
            dominant_organ = top1[0]
            dominance_passed = True
    else:
        branch = "dominance"
        if raw_margin == 0:
            mode, reason = "integrated_regulation", REASON_INTEGRATED_EXACT_TOP_TIE
        elif minor_ids:
            mode, reason = "integrated_regulation", REASON_INTEGRATED_DOMINANCE_CONFLICT
        elif not margin_ok:
            mode, reason = (
                "integrated_regulation",
                REASON_INTEGRATED_MARGIN_BELOW_THRESHOLD,
            )
        elif not ratio_ok:
            mode, reason = (
                "integrated_regulation",
                REASON_INTEGRATED_RATIO_BELOW_THRESHOLD,
            )
        else:
            mode, reason = (
                "personalized_five_tone",
                REASON_PERSONALIZED_DOMINANCE_THRESHOLDS_MET,
            )
            dominant_organ = top1[0]
            dominance_passed = True

    if branch == "dominance":
        margin_gate_state = "passed" if margin_ok else "failed"
        ratio_gate_state = "passed" if ratio_ok else "failed"
    elif branch == "single":
        margin_gate_state = "not_applicable_single_candidate"
        ratio_gate_state = "not_applicable_single_candidate"
    else:
        margin_gate_state = "not_evaluated"
        ratio_gate_state = "not_evaluated"

    if dominant_organ is not None:
        primary_tone = organ_tone_map(five_tone_mapping)[dominant_organ]

    decision = OrganDominanceDecisionV1(
        schema_id=ORGAN_DOMINANCE_DECISION_SCHEMA_ID,
        schema_version=ORGAN_DOMINANCE_DECISION_SCHEMA_VERSION,
        assessment_id=assessment_id,
        assessment_revision=assessment_revision,
        input_revision=input_revision,
        confirmed_user_state_id=confirmed_user_state_id,
        confirmed_user_state_revision=confirmed_user_state_revision,
        coverage=OrganDominanceCoverageAudit(
            confirmed_fact_count=count,
            coverage_denominator=denominator,
            evidence_coverage=coverage,
            coverage_formula_version=coverage_formula_version,
            coverage_gate_passed=coverage_passed,
        ),
        organ=OrganDominanceOrganAudit(
            raw_organ_support_by_organ=dict(aggregation.raw_support_by_organ),
            effective_evidence_count_by_organ=dict(
                aggregation.effective_evidence_count_by_organ
            ),
            legal_candidate_by_organ=dict(aggregation.legal_candidate_by_organ),
            legal_candidate_organs=list(aggregation.legal_candidate_organs),
            legal_candidate_count=aggregation.legal_candidate_count,
            normalized_weights_by_organ=dict(aggregation.normalized_weights_by_organ),
        ),
        dominance=OrganDominanceGateAudit(
            top1_organ=top1[0] if top1 else None,
            top2_organ=top2[0] if top2 else None,
            normalized_top1_weight=(
                aggregation.normalized(top1[0]) if top1 else None
            ),
            normalized_top2_weight=(
                aggregation.normalized(top2[0]) if top2 else None
            ),
            normalized_margin=normalized_margin,
            raw_top1_support=top1[1] if top1 else None,
            raw_top2_support=top2[1] if top2 else None,
            raw_ratio=raw_ratio,
            margin_gate_state=margin_gate_state,
            ratio_gate_state=ratio_gate_state,
            dominance_gate_passed=dominance_passed,
        ),
        conflict=OrganDominanceConflictAudit(
            unresolved_major_conflict_ids=major_ids,
            dominance_affecting_minor_conflict_ids=minor_ids,
            conflict_gate_passed=not major_ids and not minor_ids,
        ),
        regulation_mode=mode,
        dominant_organ=dominant_organ,
        primary_tone=primary_tone,
        decision_reason_code=reason,
        assets=assets,
        decision_snapshot_checksum="sha256:" + "0" * 64,
    )
    return decision.model_copy(
        update={"decision_snapshot_checksum": decision_snapshot_checksum(decision)}
    )


def decision_snapshot_checksum(decision: OrganDominanceDecisionV1) -> str:
    """Canonical checksum of the decision payload (own checksum removed)."""

    payload = decision.model_dump(mode="json")
    payload.pop("decision_snapshot_checksum", None)
    serialized = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return f"sha256:{sha256(serialized.encode('utf-8')).hexdigest()}"


__all__ = [
    "DominanceReadinessError",
    "OrganAggregationSnapshot",
    "build_organ_aggregation_snapshot",
    "canonical_effective_evidence",
    "canonical_evidence_coverage",
    "confirmed_evidence",
    "conflict_rules_of",
    "decision_snapshot_checksum",
    "dominance_affecting_minor_conflict_ids",
    "fact_claim_index",
    "is_questionnaire_evidence",
    "ABSTAIN_REASON_CLASS_LEGAL",
    "ABSTAIN_REASON_CLASS_MISSING",
    "ABSTAIN_REASON_CLASS_NON_MODE",
    "ABSTAIN_REASON_CLASS_UNCLASSIFIED",
    "classify_abstain_reason",
    "is_non_mode_abstain_reason",
    "NON_MODE_ABSTAIN_REASONS",
    "load_configured_dominance_rule",
    "normalize_legal_abstain_reason",
    "organ_tone_map",
    "verify_candidate_policy_consistency",
    "resolve_organ_dominance",
    "select_effective_evidence",
    "shares_source",
    "unresolved_major_conflict_ids",
    "verify_mapping_identity",
    "FIVE_TONE_ANALYSIS_SCHEMA_VERSION_V33",
]
