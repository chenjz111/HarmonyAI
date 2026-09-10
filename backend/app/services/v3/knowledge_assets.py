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
        if self.explanations is not None and set(self.explanations) != {
            "duration" if field_name == "duration_seconds" else field_name
            for field_name in override_fields
        }:
            raise ValueError("explanations must describe only overridden parameters")
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
