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
from typing import Mapping

from backend.app.schemas.v3.common import ClaimDictionaryEntry


@dataclass(frozen=True)
class MedicalRuleAsset:
    """Owner-approved Agent 2 rule release loaded from a checked asset."""

    schema_version: str
    medical_rule_version: str
    content_checksum: str
    allowed_syndrome_codes: frozenset[str]


class MedicalRuleAssetNotReady(ValueError):
    """A medical rule asset is absent, unapproved, stale, or tampered."""

    def __init__(self, error_code: str, safe_message: str) -> None:
        self.error_code = error_code
        self.safe_message = safe_message
        super().__init__(f"{error_code}: {safe_message}")


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
    return MedicalRuleAsset(
        schema_version=schema_version,
        medical_rule_version=asset_version,
        content_checksum=actual_checksum,
        allowed_syndrome_codes=frozenset(codes),
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
