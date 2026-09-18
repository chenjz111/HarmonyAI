"""Loaders for Issue #89 approved medical assets with checksum verification.

All medical content consumed by the AI layer (Agent 1/2) must come from the
approved manifests under ``knowledge/v3/``; the code never hard-codes its own
medical rules. Every asset is validated against its embedded
``content_checksum`` before use.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Literal, Mapping

from pydantic import Field, ValidationError, model_validator

from backend.app.schemas.v3.common import (
    ClaimDictionaryEntry,
    NonEmptyString,
    UserGoalCode,
    V3BaseModel,
)


@dataclass(frozen=True)
class MedicalRuleAsset:
    """Owner-approved Agent 2 rule release loaded from a checked asset."""

    schema_version: str
    medical_rule_version: str
    content_checksum: str
    allowed_syndrome_codes: frozenset[str]
    syndrome_aliases: Mapping[str, str]


FORMAL_MEDICAL_RULE_VERSION = "medical-rules-v3.1-r1"
FORMAL_V31_ALLOWED_SYNDROME_CODES = frozenset(
    f"syd_{index:03d}" for index in range(1, 9)
)
FORMAL_V31_SYNDROME_ALIASES: Mapping[str, str] = {
    "syd_001": "liver_stagnation_heat",
    "syd_002": "liver_qi_stagnation",
    "syd_003": "heart_fire_flare",
    "syd_004": "heart_spleen_deficiency",
    "syd_005": "spleen_deficiency_dampness",
    "syd_006": "lung_qi_deficiency",
    "syd_007": "kidney_yin_deficiency",
    "syd_008": "heart_kidney_discordance",
}
# Filled with the canonical checksum of knowledge/v3/medical-rules-v3.1.json.
APPROVED_MEDICAL_RULE_CHECKSUMS: Mapping[str, str] = {
    FORMAL_MEDICAL_RULE_VERSION: "sha256:0dd929cb7d2b7b8a11c9c1ad0fb5e4adb8f4807123263af7e2a7c1767b401a3f",
}


class MedicalRuleAssetNotReady(ValueError):
    """A medical rule asset is absent, unapproved, stale, or tampered."""

    def __init__(self, error_code: str, safe_message: str) -> None:
        self.error_code = error_code
        self.safe_message = safe_message
        super().__init__(f"{error_code}: {safe_message}")


class MusicGenerationRuleAssetNotReady(ValueError):
    """A deterministic Agent3 music-rule asset is absent or not approved."""

    def __init__(self, error_code: str, safe_message: str) -> None:
        self.error_code = error_code
        self.safe_message = safe_message
        super().__init__(f"{error_code}: {safe_message}")


class MusicGenerationRuleRow(V3BaseModel):
    """A complete default or bounded UserGoal music parameter row."""

    bpm: int = Field(ge=40, le=120)
    instruments: list[NonEmptyString] = Field(min_length=1)
    ambience: list[NonEmptyString] = Field(min_length=1)
    duration_seconds: int = Field(gt=0, le=300)
    explanations: dict[NonEmptyString, NonEmptyString]

    @model_validator(mode="after")
    def require_unique_parameters(self) -> "MusicGenerationRuleRow":
        if len(self.instruments) != len(set(self.instruments)):
            raise ValueError("instruments must be unique")
        if len(self.ambience) != len(set(self.ambience)):
            raise ValueError("ambience must be unique")
        if set(self.explanations) != {"bpm", "instruments", "ambience", "duration"}:
            raise ValueError("explanations must describe all deterministic parameters")
        return self


class MusicGenerationRuleOverride(V3BaseModel):
    """A partial deterministic override selected by an approved goal code."""

    bpm: int | None = Field(default=None, ge=40, le=120)
    instruments: list[NonEmptyString] | None = Field(default=None, min_length=1)
    ambience: list[NonEmptyString] | None = Field(default=None, min_length=1)
    duration_seconds: int | None = Field(default=None, gt=0, le=300)
    explanations: dict[NonEmptyString, NonEmptyString] | None = None

    @model_validator(mode="after")
    def require_unique_parameters(self) -> "MusicGenerationRuleOverride":
        if self.instruments is not None and len(self.instruments) != len(set(self.instruments)):
            raise ValueError("instruments must be unique")
        if self.ambience is not None and len(self.ambience) != len(set(self.ambience)):
            raise ValueError("ambience must be unique")
        override_fields = {
            field_name
            for field_name in ("bpm", "instruments", "ambience", "duration_seconds")
            if getattr(self, field_name) is not None
        }
        expected_explanation_keys = {
            "duration" if field_name == "duration_seconds" else field_name
            for field_name in override_fields
        }
        if override_fields and (
            self.explanations is None
            or set(self.explanations) != expected_explanation_keys
        ):
            raise ValueError("explanations must describe only overridden parameters")
        if not override_fields and self.explanations:
            raise ValueError("empty overrides cannot declare parameter explanations")
        return self


class MusicGenerationRulesAsset(V3BaseModel):
    """Schema for the reviewed deterministic Agent3 music rules."""

    schema_id: Literal["music_generation_rules_v3.1"]
    schema_version: NonEmptyString
    asset_version: NonEmptyString
    review_status: Literal["approved"]
    secondary_goal_merge_policy: Literal["primary_over_secondary_fill_missing"]
    default: MusicGenerationRuleRow
    goals: dict[UserGoalCode, MusicGenerationRuleOverride]
    content_checksum: NonEmptyString

    @model_validator(mode="after")
    def require_complete_formal_goal_set(self) -> "MusicGenerationRulesAsset":
        goal_codes = {code.value for code in self.goals}
        expected_codes = {code.value for code in UserGoalCode}
        if goal_codes != expected_codes:
            raise ValueError("goals must contain exactly the seven formal UserGoal codes")
        return self


def load_music_generation_rules(
    path: str | Path,
    *,
    expected_version: str,
    expected_checksum: str,
) -> dict[str, object]:
    """Load only an approved, checksum-bound deterministic Agent3 asset."""

    if not expected_version.strip() or not expected_checksum.startswith("sha256:"):
        raise MusicGenerationRuleAssetNotReady(
            "MUSIC_PARAMETER_ASSET_NOT_CONFIGURED",
            "音乐参数规则资产版本或校验和尚未配置。",
        )
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise MusicGenerationRuleAssetNotReady(
            "MUSIC_PARAMETER_ASSET_NOT_CONFIGURED",
            "音乐参数规则资产无法读取。",
        ) from error
    if not isinstance(payload, Mapping):
        raise MusicGenerationRuleAssetNotReady(
            "MUSIC_PARAMETER_ASSET_INVALID",
            "音乐参数规则资产格式无效。",
        )
    declared_checksum = payload.get("content_checksum")
    actual_checksum = _canonical_asset_checksum(payload)
    if (
        not isinstance(declared_checksum, str)
        or declared_checksum != actual_checksum
        or expected_checksum != actual_checksum
    ):
        raise MusicGenerationRuleAssetNotReady(
            "MUSIC_PARAMETER_ASSET_CHECKSUM_MISMATCH",
            "音乐参数规则资产校验和不匹配。",
        )
    if payload.get("schema_id") != "music_generation_rules_v3.1":
        raise MusicGenerationRuleAssetNotReady(
            "MUSIC_PARAMETER_ASSET_SCHEMA_INVALID",
            "音乐参数规则资产标识无效。",
        )
    if payload.get("review_status") != "approved":
        raise MusicGenerationRuleAssetNotReady(
            "MUSIC_PARAMETER_ASSET_NOT_APPROVED",
            "音乐参数规则资产尚未获得生产批准。",
        )
    try:
        asset = MusicGenerationRulesAsset.model_validate(payload)
    except ValidationError as error:
        raise MusicGenerationRuleAssetNotReady(
            "MUSIC_PARAMETER_ASSET_INVALID",
            "音乐参数规则资产格式无效。",
        ) from error
    if asset.asset_version != expected_version:
        raise MusicGenerationRuleAssetNotReady(
            "MUSIC_PARAMETER_ASSET_VERSION_MISMATCH",
            "音乐参数规则资产版本与配置不一致。",
        )
    return asset.model_dump(mode="json", exclude_none=True)


class DominanceRuleAssetNotReady(ValueError):
    """A Sprint 6 Phase 1B dominance rule asset is absent, unapproved, or tampered."""

    def __init__(self, error_code: str, safe_message: str) -> None:
        self.error_code = error_code
        self.safe_message = safe_message
        super().__init__(f"{error_code}: {safe_message}")


DOMINANCE_RULE_SCHEMA_ID = "dominance_rule_contract"
DOMINANCE_RULE_ASSET_VERSION = "dominance-rule-v1.0-r1"
# Canonical checksum of knowledge/v3/dominance-rule-v1.json (same
# "configured approved release" convention as APPROVED_MEDICAL_RULE_CHECKSUMS).
APPROVED_DOMINANCE_RULE_CHECKSUM = (
    "sha256:7be01a93cd55118d496c08d234302b2d7cc8d601aa0152c62789a2ed31d9e019"
)

# Approved deterministic non-tone music parameter release. Used by paths that
# must assemble a basic_wellness read model without the full provider/RAG
# dependency factory (the legal-abstain path), and overridable by the same
# environment configuration the pipeline uses.
FORMAL_MUSIC_GENERATION_RULE_VERSION = "music-generation-rules-v3.1-r1"
APPROVED_MUSIC_GENERATION_RULE_CHECKSUM = (
    "sha256:c97acc241abe611b91d71c205cb021afaa47cfffd1c7bfe8d447e402d74f0ae0"
)
DEFAULT_MUSIC_GENERATION_RULES_FILENAME = "music-generation-rules-v3.1.json"

# Frozen Phase 1B numbers. The rule asset must restate these exactly; they are
# never re-declared as a competing authority inside routing code.
DOMINANCE_EVIDENCE_DENOMINATOR = 8
DOMINANCE_MINIMUM_COVERAGE = 0.50
DOMINANCE_NORMALIZED_PRECISION = 4
DOMINANCE_MARGIN_THRESHOLD = 0.08
DOMINANCE_RAW_RATIO_THRESHOLD = 1.20

DOMINANCE_REASON_CODES = (
    "BASIC_ELEMENT_EVIDENCE_INSUFFICIENT",
    "BASIC_RAG_EMPTY",
    "BASIC_EVIDENCE_COVERAGE_BELOW_THRESHOLD",
    "BASIC_NO_LEGAL_ORGAN_CANDIDATE",
    "BASIC_UNRESOLVED_MAJOR_CONFLICT",
    "PERSONALIZED_SINGLE_LEGAL_CANDIDATE",
    "PERSONALIZED_DOMINANCE_THRESHOLDS_MET",
    "INTEGRATED_EXACT_TOP_TIE",
    "INTEGRATED_DOMINANCE_CONFLICT",
    "INTEGRATED_MARGIN_BELOW_THRESHOLD",
    "INTEGRATED_RATIO_BELOW_THRESHOLD",
)


class DominanceReferenceIdentity(V3BaseModel):
    """Identity of an approved upstream mapping this asset references."""

    schema_id: NonEmptyString
    schema_version: NonEmptyString
    content_checksum: NonEmptyString


class DominanceAbstainMapping(V3BaseModel):
    upstream_reason_code: NonEmptyString
    reason_code: NonEmptyString


class DominanceEvidenceGate(V3BaseModel):
    coverage_formula_version: NonEmptyString
    coverage_formula: NonEmptyString
    denominator: int
    minimum_coverage: float
    comparison: Literal[">="]
    effective_evidence_population: NonEmptyString
    counted_directions: list[Literal["supporting", "contradicting"]]
    upstream_abstain_mappings: list[DominanceAbstainMapping]

    @model_validator(mode="after")
    def require_frozen_evidence_gate(self) -> "DominanceEvidenceGate":
        if self.denominator != DOMINANCE_EVIDENCE_DENOMINATOR:
            raise ValueError("evidence denominator must be 8")
        if abs(self.minimum_coverage - DOMINANCE_MINIMUM_COVERAGE) > 1e-9:
            raise ValueError("minimum evidence coverage must be 0.50")
        if set(self.counted_directions) != {"supporting", "contradicting"}:
            raise ValueError("coverage counts supporting and contradicting facts")
        return self


class DominanceLegalCandidateGate(V3BaseModel):
    authority: Literal["approved_organ_mapping"]
    reference: NonEmptyString
    minimum_effective_evidence_count: int
    minimum_raw_support: float
    comparison: Literal[">="]
    note: NonEmptyString

    @model_validator(mode="after")
    def require_frozen_legal_candidate_gate(self) -> "DominanceLegalCandidateGate":
        if self.minimum_effective_evidence_count != 2:
            raise ValueError("legal candidate evidence count must be 2")
        if abs(self.minimum_raw_support - 0.75) > 1e-9:
            raise ValueError("legal candidate raw support must be 0.75")
        return self


class DominanceGate(V3BaseModel):
    comparison_population: Literal["legal_candidates_only"]
    top_ordering_authority: Literal["canonical_raw_support"]
    normalized_precision: int
    normalized_margin_threshold: float
    normalized_margin_comparison: Literal[">="]
    raw_ratio_threshold: float
    raw_ratio_comparison: Literal[">="]
    exact_tie_basis: Literal["canonical_raw_support_equality"]
    top1_hard_gate: None = None
    epsilon: None = None
    entropy_or_spread_gate: None = None

    @model_validator(mode="after")
    def require_frozen_dominance_gate(self) -> "DominanceGate":
        if self.normalized_precision != DOMINANCE_NORMALIZED_PRECISION:
            raise ValueError("normalized precision must be 4")
        if abs(self.normalized_margin_threshold - DOMINANCE_MARGIN_THRESHOLD) > 1e-9:
            raise ValueError("normalized margin threshold must be 0.08")
        if abs(self.raw_ratio_threshold - DOMINANCE_RAW_RATIO_THRESHOLD) > 1e-9:
            raise ValueError("raw ratio threshold must be 1.20")
        return self


class DominanceRuleAsset(V3BaseModel):
    """Schema for the reviewed Phase 1B dominance/ambiguity rule contract."""

    schema_id: Literal["dominance_rule_contract"]
    schema_version: NonEmptyString
    asset_version: NonEmptyString
    review_status: Literal["approved"]
    medical_review: Mapping[str, object]
    owner_approval: Mapping[str, object]
    scope: NonEmptyString
    evidence_gate: DominanceEvidenceGate
    legal_candidate_gate: DominanceLegalCandidateGate
    dominance_gate: DominanceGate
    candidate_policies: Mapping[str, object]
    conflict_policy: Mapping[str, object]
    failure_policy: Mapping[str, object]
    reason_precedence: Mapping[str, object]
    reason_codes: Mapping[str, NonEmptyString]
    decision_snapshot_schema_id: Literal["organ_dominance_decision_v1"]
    read_model_schema_version: Literal["five_tone_analysis_read_model_v3.3"]
    references: Mapping[str, DominanceReferenceIdentity]
    content_checksum: NonEmptyString

    @model_validator(mode="after")
    def require_frozen_vocabulary_and_references(self) -> "DominanceRuleAsset":
        if set(self.reason_codes) != set(DOMINANCE_REASON_CODES):
            raise ValueError("dominance asset must declare the frozen reason vocabulary")
        if set(self.references) != {"organ_mapping", "five_tone_mapping"}:
            raise ValueError("dominance asset must reference both approved mappings")
        if self.medical_review.get("status") != "approved":
            raise ValueError("medical review must be approved")
        if self.owner_approval.get("status") != "approved":
            raise ValueError("owner approval must be approved")
        return self


def load_dominance_rule_asset(
    path: str | Path,
    *,
    expected_version: str,
    expected_checksum: str,
) -> dict[str, object]:
    """Load only the approved, checksum-bound Phase 1B dominance rule asset."""

    if not expected_version.strip() or not expected_checksum.startswith("sha256:"):
        raise DominanceRuleAssetNotReady(
            "DOMINANCE_RULE_ASSET_NOT_CONFIGURED",
            "主导度规则资产版本或校验和尚未配置。",
        )
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DominanceRuleAssetNotReady(
            "DOMINANCE_RULE_ASSET_NOT_CONFIGURED",
            "主导度规则资产无法读取。",
        ) from error
    if not isinstance(payload, Mapping):
        raise DominanceRuleAssetNotReady(
            "DOMINANCE_RULE_ASSET_INVALID",
            "主导度规则资产格式无效。",
        )
    declared_checksum = payload.get("content_checksum")
    actual_checksum = _canonical_asset_checksum(payload)
    if (
        not isinstance(declared_checksum, str)
        or declared_checksum != actual_checksum
        or expected_checksum != actual_checksum
    ):
        raise DominanceRuleAssetNotReady(
            "DOMINANCE_RULE_ASSET_CHECKSUM_MISMATCH",
            "主导度规则资产校验和不匹配。",
        )
    if payload.get("schema_id") != DOMINANCE_RULE_SCHEMA_ID:
        raise DominanceRuleAssetNotReady(
            "DOMINANCE_RULE_ASSET_SCHEMA_INVALID",
            "主导度规则资产标识无效。",
        )
    if payload.get("review_status") != "approved":
        raise DominanceRuleAssetNotReady(
            "DOMINANCE_RULE_ASSET_NOT_APPROVED",
            "主导度规则资产尚未获得生产批准。",
        )
    try:
        asset = DominanceRuleAsset.model_validate(payload)
    except ValidationError as error:
        raise DominanceRuleAssetNotReady(
            "DOMINANCE_RULE_ASSET_INVALID",
            "主导度规则资产格式无效。",
        ) from error
    if asset.asset_version != expected_version:
        raise DominanceRuleAssetNotReady(
            "DOMINANCE_RULE_ASSET_VERSION_MISMATCH",
            "主导度规则资产版本与配置不一致。",
        )
    return asset.model_dump(mode="json", exclude_none=True)


def canonical_asset_checksum(payload: Mapping[str, object]) -> str:
    """Public canonical asset checksum (top-level ``content_checksum`` removed)."""

    return _canonical_asset_checksum(payload)


def load_configured_music_generation_rules() -> dict[str, object]:
    """Load the approved non-tone music parameter release.

    The configured release (``V31_MUSIC_GENERATION_RULES_PATH`` /
    ``_VERSION`` / ``_CHECKSUM``) wins when fully provided; otherwise the
    repository's approved release is used. Either way the asset is verified
    against its embedded and approved checksum, version, schema and approval
    status — an unapproved or tampered asset is a readiness failure, never a
    music mode.
    """

    path = os.getenv("V31_MUSIC_GENERATION_RULES_PATH", "").strip()
    version = os.getenv("V31_MUSIC_GENERATION_RULES_VERSION", "").strip()
    checksum = os.getenv("V31_MUSIC_GENERATION_RULES_CHECKSUM", "").strip()
    if not (path and version and checksum):
        path = str(_asset_root() / DEFAULT_MUSIC_GENERATION_RULES_FILENAME)
        version = FORMAL_MUSIC_GENERATION_RULE_VERSION
        checksum = APPROVED_MUSIC_GENERATION_RULE_CHECKSUM
    return load_music_generation_rules(
        Path(path), expected_version=version, expected_checksum=checksum
    )


def _asset_root() -> Path:
    return Path(__file__).resolve().parents[4] / "knowledge" / "v3"


def _load_checked(filename: str) -> dict:
    path = _asset_root() / filename
    payload = json.loads(path.read_text(encoding="utf-8"))
    declared = payload.get("content_checksum", "")
    if not declared.startswith("sha256:"):
        raise ValueError(f"{filename}: missing sha256 content_checksum")
    # Canonical hash rule (PR #89, repository-wide): remove the top-level
    # content_checksum, then sha256 of the compact sorted JSON.
    data = {key: value for key, value in payload.items() if key != "content_checksum"}
    serialized = json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    actual = f"sha256:{sha256(serialized.encode('utf-8')).hexdigest()}"
    if actual != declared:
        raise ValueError(
            f"{filename}: checksum mismatch declared={declared} actual={actual}"
        )
    return payload


_claim_dictionary: dict[str, ClaimDictionaryEntry] | None = None
_claim_dictionary_version: str | None = None


def load_claim_dictionary() -> tuple[str, dict[str, ClaimDictionaryEntry]]:
    """Load the approved claim dictionary once; returns (version, entries)."""
    global _claim_dictionary, _claim_dictionary_version
    if _claim_dictionary is not None:
        assert _claim_dictionary_version is not None
        return _claim_dictionary_version, _claim_dictionary
    payload = _load_checked("claim-dictionary-v3.0.json")
    entries: dict[str, ClaimDictionaryEntry] = {}
    for item in payload["entries"]:
        entry = ClaimDictionaryEntry.model_validate(item)
        entries[entry.claim_code] = entry
    _claim_dictionary = entries
    _claim_dictionary_version = payload.get("schema_version", "3.0.0")
    return _claim_dictionary_version, entries


def load_organ_mapping() -> dict:
    """Load the approved organ mapping (single + combination rules)."""
    return _load_checked("organ-mapping-v3.0.json")


def load_five_tone_mapping() -> dict:
    """Load the approved organ-to-five-tone mapping for Agent3."""
    return _load_checked("five-tone-mapping-v3.0.json")


_APPROVED_SYNDROME_DISPLAY_NAMES: Mapping[str, str] | None = None


def load_approved_syndrome_display_names() -> Mapping[str, str]:
    """Load the review-gated canonical Chinese syndrome labels.

    ``knowledge/v3/agent2-syndrome-whitelist-v3.1.json`` is the medically
    approved source of the 证型倾向 wording.  The provider only ever returns a
    controlled ``syndrome_code``; the user-facing Chinese name is resolved from
    this asset instead of from the provider's prose, so the public read model
    cannot leak English labels into the Chinese UI.

    The loader never raises: a missing, unreadable, unapproved, or malformed
    asset yields an empty mapping so callers fall back to their existing value.
    """

    global _APPROVED_SYNDROME_DISPLAY_NAMES
    if _APPROVED_SYNDROME_DISPLAY_NAMES is not None:
        return _APPROVED_SYNDROME_DISPLAY_NAMES
    names: dict[str, str] = {}
    try:
        payload = json.loads(
            (_asset_root() / "agent2-syndrome-whitelist-v3.1.json").read_text(
                encoding="utf-8"
            )
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        _APPROVED_SYNDROME_DISPLAY_NAMES = names
        return names
    if isinstance(payload, Mapping) and payload.get("review_status") == (
        "MEDICALLY_APPROVED"
    ):
        entries = payload.get("allowed_syndromes")
        if isinstance(entries, list):
            for entry in entries:
                if not isinstance(entry, Mapping):
                    continue
                code = entry.get("stable_code")
                display_name = entry.get("display_name")
                if (
                    isinstance(code, str)
                    and code.strip()
                    and isinstance(display_name, str)
                    and display_name.strip()
                ):
                    names[code] = display_name
    _APPROVED_SYNDROME_DISPLAY_NAMES = names
    return names


def load_medical_rule_asset(
    path: str | Path,
    *,
    expected_version: str,
    expected_checksum: str,
) -> MedicalRuleAsset:
    """Load the explicit Owner-approved Agent 2 rule release.

    The file is intentionally supplied by deployment configuration rather
    than invented in code.  Its embedded checksum and the separately
    configured approved checksum must both match the canonical payload.  The
    caller may select a version, but cannot provide the syndrome allowlist.
    """

    if not expected_version.strip() or not expected_checksum.startswith("sha256:"):
        raise MedicalRuleAssetNotReady(
            "MEDICAL_RULE_ASSET_NOT_CONFIGURED",
            "医学规则资产版本或校验和尚未配置。",
        )
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise MedicalRuleAssetNotReady(
            "MEDICAL_RULE_ASSET_NOT_CONFIGURED",
            "医学规则资产无法读取。",
        ) from error
    if not isinstance(payload, Mapping):
        raise MedicalRuleAssetNotReady(
            "MEDICAL_RULE_ASSET_INVALID",
            "医学规则资产格式无效。",
        )

    declared_checksum = payload.get("content_checksum")
    actual_checksum = _canonical_asset_checksum(payload)
    if (
        not isinstance(declared_checksum, str)
        or declared_checksum != actual_checksum
        or expected_checksum != actual_checksum
    ):
        raise MedicalRuleAssetNotReady(
            "MEDICAL_RULE_ASSET_CHECKSUM_MISMATCH",
            "医学规则资产校验和不匹配。",
        )
    if payload.get("schema_id") != "medical_rules_v3.1":
        raise MedicalRuleAssetNotReady(
            "MEDICAL_RULE_ASSET_INVALID",
            "医学规则资产标识无效。",
        )
    if payload.get("review_status") != "approved":
        raise MedicalRuleAssetNotReady(
            "MEDICAL_RULE_ASSET_NOT_APPROVED",
            "医学规则资产尚未获得生产批准。",
        )
    asset_version = payload.get("medical_rule_version")
    if not isinstance(asset_version, str) or asset_version != expected_version:
        raise MedicalRuleAssetNotReady(
            "MEDICAL_RULE_VERSION_MISMATCH",
            "医学规则资产版本与配置不一致。",
        )
    if expected_version not in APPROVED_MEDICAL_RULE_CHECKSUMS:
        raise MedicalRuleAssetNotReady(
            "MEDICAL_RULE_VERSION_NOT_APPROVED",
            "医学规则资产版本尚未获得生产批准。",
        )
    schema_version = payload.get("schema_version")
    codes = payload.get("allowed_syndrome_codes")
    if (
        not isinstance(schema_version, str)
        or not schema_version.strip()
        or not isinstance(codes, list)
        or not codes
        or len(codes) != len(set(codes))
        or any(
            not isinstance(code, str)
            or re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,63}", code) is None
            for code in codes
        )
    ):
        raise MedicalRuleAssetNotReady(
            "MEDICAL_RULE_CODES_INVALID",
            "医学规则资产中的证型代码无效。",
        )
    if (
        set(codes) != FORMAL_V31_ALLOWED_SYNDROME_CODES
        or codes != sorted(FORMAL_V31_ALLOWED_SYNDROME_CODES)
    ):
        raise MedicalRuleAssetNotReady(
            "MEDICAL_RULE_CODES_NOT_APPROVED",
            "医学规则资产中的证型代码不是已批准白名单。",
        )
    aliases = payload.get("syndrome_aliases")
    if (
        not isinstance(aliases, Mapping)
        or dict(aliases) != dict(FORMAL_V31_SYNDROME_ALIASES)
        or any(
            not isinstance(alias, str)
            or re.fullmatch(r"[a-z][a-z0-9_]{0,63}", alias) is None
            for alias in aliases.values()
        )
    ):
        raise MedicalRuleAssetNotReady(
            "MEDICAL_RULE_CODES_NOT_APPROVED",
            "医学规则资产中的证型别名不是已批准语义别名。",
        )
    approved_checksum = APPROVED_MEDICAL_RULE_CHECKSUMS[expected_version]
    if approved_checksum and actual_checksum != approved_checksum:
        raise MedicalRuleAssetNotReady(
            "MEDICAL_RULE_CHECKSUM_NOT_APPROVED",
            "医学规则资产校验和不是已批准发布版本。",
        )
    return MedicalRuleAsset(
        schema_version=schema_version,
        medical_rule_version=asset_version,
        content_checksum=actual_checksum,
        allowed_syndrome_codes=frozenset(codes),
        syndrome_aliases=dict(aliases),
    )


def _canonical_asset_checksum(payload: Mapping[str, object]) -> str:
    canonical = {
        key: value for key, value in payload.items() if key != "content_checksum"
    }
    serialized = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"sha256:{sha256(serialized.encode('utf-8')).hexdigest()}"


def load_approved_assets() -> tuple[str, Mapping[str, ClaimDictionaryEntry]]:
    """Convenience loader for the Understanding/A1/A2 provider wiring."""
    return load_claim_dictionary()
