"""Loaders for Issue #89 approved medical assets with checksum verification.

All medical content consumed by the AI layer (Agent 1/2) must come from the
approved manifests under ``knowledge/v3/``; the code never hard-codes its own
medical rules. Every asset is validated against its embedded
``content_checksum`` before use.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Mapping

from backend.app.schemas.v3.common import ClaimDictionaryEntry


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


def load_approved_assets() -> tuple[str, Mapping[str, ClaimDictionaryEntry]]:
    """Convenience loader for the Understanding/A1/A2 provider wiring."""
    return load_claim_dictionary()
