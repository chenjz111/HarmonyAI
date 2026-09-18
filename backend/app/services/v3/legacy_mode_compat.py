"""Sprint 6 Phase 1A — row-aware legacy mode compatibility.

Phase 1A changed the mode-bearing payload shape: ``regulation_mode`` is now the
authority, ``primary_tone``/``weights`` are mode-scoped, and new payloads carry
``tone_profile_v3.2`` / ``five_tone_analysis_read_model_v3.2``. This module owns
the **only** place where a pre-Phase-1A row may be turned into a modern view.

Frozen owner policy (Sprint 6 Phase 1A fix):

* a non-null ``primary_tone`` is **never** evidence of ``personalized_five_tone``;
* known legacy ``wellness`` / abstained / fabricated-Gong rows resolve to
  ``basic_wellness`` compatibility (no tone claim);
* a legacy successful, non-abstained syndrome-based row may resolve to
  ``personalized_five_tone`` only when reliable persisted evidence supports it
  (non-abstained success/degraded diagnosis + real persisted tone authority +
  non-empty persisted evidence references);
* ``integrated_regulation`` is **never** derived for Sprint 5 data — that mode
  did not exist then;
* anything else is an explicit ``legacy_unclassified`` compatibility state and
  fails closed; it is not a fourth public regulation mode.

Legacy checksum integrity: the stored payload is verified **in its stored
schema form** (see :func:`stored_checksum_matches`) before any compatibility
projection. A derived view never overwrites the stored payload or its checksum.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from typing import Annotated, Literal

from pydantic import Field, model_validator

from backend.app.schemas.v3.common import NonEmptyString, Score01, ToneCode, V3BaseModel
from backend.app.schemas.v3.flow_v31 import (
    FIVE_TONE_ANALYSIS_SCHEMA_VERSION,
    FIVE_TONE_ANALYSIS_SCHEMA_VERSION_V33,
    LEGACY_FIVE_TONE_ANALYSIS_SCHEMA_VERSION,
    LEGACY_TONE_PROFILE_SCHEMA_VERSION,
    TONE_PROFILE_SCHEMA_VERSION,
    BpmExplanation,
    ConfirmedUserStateRef,
    DurationExplanation,
    FiveToneAnalysisReadModel,
    FiveToneAnalysisReadModelV33,
    GenerationReadiness,
    ListParameterExplanation,
    PublicRationale,
    PublicText,
    PublicToneExplanation,
    RegulationMode,
    ToneProfileBasisV31,
    ToneProfileV31,
)
from backend.app.schemas.v3.prescription import GenerationSpec

# --------------------------------------------------------------------------- #
# legacy payload shapes (pre-Phase-1A, kept faithful so old rows stay parseable)
# --------------------------------------------------------------------------- #


class LegacyToneProfileV31(V3BaseModel):
    """Pre-Phase-1A tone profile: always a single tone plus full weights."""

    schema_version: Literal["tone_profile_v3.1"]
    weights: dict[ToneCode, Score01]
    primary_tone: ToneCode
    secondary_tone: ToneCode | None = None
    score_semantics: Literal["relative_tone_distribution"]
    mapping_version: NonEmptyString
    basis: ToneProfileBasisV31

    @model_validator(mode="after")
    def validate_legacy_shape(self) -> "LegacyToneProfileV31":
        """Faithful pre-1A validation (the old model enforced both rules)."""

        if set(self.weights) != set(ToneCode):
            raise ValueError("legacy tone profile requires all five tone weights")
        if abs(sum(self.weights.values()) - 1.0) > 0.001:
            raise ValueError("legacy tone weights must sum to 1 ± 0.001")
        maximum = max(self.weights.values())
        if abs(self.weights[self.primary_tone] - maximum) > 0.001:
            raise ValueError("legacy primary_tone must have a maximum weight")
        return self


class LegacyFiveToneAnalysisReadModelV31(V3BaseModel):
    """Pre-Phase-1A public read model (no ``regulation_mode``/``tone_weights``)."""

    schema_version: Literal["five_tone_analysis_read_model_v3.1"]
    confirmed_user_state_ref: ConfirmedUserStateRef
    confirmed_state: PublicText
    state_tendency: PublicText
    analysis_rationales: Annotated[list[PublicRationale], Field(min_length=1)]
    primary_tone: PublicToneExplanation
    secondary_tone: PublicToneExplanation | None = None
    bpm: BpmExplanation
    instruments: ListParameterExplanation
    ambience: ListParameterExplanation
    duration: DurationExplanation
    generation: GenerationReadiness
    disclaimer: PublicText


# --------------------------------------------------------------------------- #
# classification
# --------------------------------------------------------------------------- #

LegacySource = Literal["diagnosis", "prescription", "asset", "unknown"]
LegacyCompatibilityState = Literal["legacy_derived", "legacy_unclassified"]

LEGACY_REASON_ABSTAINED = "LEGACY_ABSTAINED_DIAGNOSIS"
LEGACY_REASON_WELLNESS_PRESCRIPTION = "LEGACY_WELLNESS_PRESCRIPTION"
LEGACY_REASON_FABRICATED_FALLBACK = "LEGACY_FABRICATED_FALLBACK"
LEGACY_REASON_GENUINE_PERSONALIZED = "LEGACY_GENUINE_PERSONALIZED"
LEGACY_REASON_UNCLASSIFIED = "LEGACY_UNCLASSIFIED"
LEGACY_MISSING_TONE_AUTHORITY = "LEGACY_MISSING_TONE_AUTHORITY"

# The Sprint 5 ``_conservative_wellness_spec`` signature. Rows produced by that
# path are known fabricated fallbacks and must never read back as personalized.
LEGACY_FABRICATED_FALLBACK_WEIGHTS = {
    "jiao": 0.1,
    "zhi": 0.1,
    "gong": 0.6,
    "shang": 0.1,
    "yu": 0.1,
}

UNSUPPORTED_SCHEMA_VERSION = "UNSUPPORTED_SCHEMA_VERSION"
LEGACY_UNCLASSIFIED_CODE = "LEGACY_MODE_UNCLASSIFIED"


class LegacyModeUnclassifiedError(RuntimeError):
    """Explicit fail-closed state for a row whose provenance cannot be resolved."""

    def __init__(self, reason_code: str = LEGACY_UNCLASSIFIED_CODE) -> None:
        self.error_code = reason_code
        self.safe_message = "历史数据来源无法可靠判定，已按未分类状态停止推断音乐模式。"
        super().__init__(f"{reason_code}: {self.safe_message}")


@dataclass(frozen=True)
class LegacyProvenance:
    """Persisted row context available to the resolver (never the payload tone)."""

    source: LegacySource = "unknown"
    diagnosis_status: str | None = None
    abstain_reason: str | None = None
    prescription_mode: str | None = None


@dataclass(frozen=True)
class LegacyModeCompatibility:
    """Outcome of a legacy compatibility resolution.

    ``regulation_mode`` is ``None`` for the ``legacy_unclassified`` state, which
    is a compatibility state rather than a public regulation mode.
    """

    compatibility_state: LegacyCompatibilityState
    reason_code: str
    regulation_mode: RegulationMode | None = None
    derived: bool = True

    @property
    def is_unclassified(self) -> bool:
        return self.compatibility_state == "legacy_unclassified"


def is_legacy_tone_profile_payload(payload: object) -> bool:
    return (
        isinstance(payload, Mapping)
        and payload.get("schema_version") == LEGACY_TONE_PROFILE_SCHEMA_VERSION
    )


def is_legacy_read_model_payload(payload: object) -> bool:
    return (
        isinstance(payload, Mapping)
        and payload.get("schema_version") == LEGACY_FIVE_TONE_ANALYSIS_SCHEMA_VERSION
    )


def is_known_fabricated_fallback(weights: Mapping[object, object] | None) -> bool:
    """True when the persisted weights match the Sprint 5 fabricated fallback."""

    if not isinstance(weights, Mapping):
        return False
    normalised = {
        str(getattr(key, "value", key)): float(value) for key, value in weights.items()
    }
    if set(normalised) != set(LEGACY_FABRICATED_FALLBACK_WEIGHTS):
        return False
    return all(
        abs(normalised[tone] - value) < 1e-9
        for tone, value in LEGACY_FABRICATED_FALLBACK_WEIGHTS.items()
    )


def classify_legacy_mode(
    *,
    weights: Mapping[object, object] | None,
    evidence_refs: Sequence[str],
    provenance: LegacyProvenance,
) -> LegacyModeCompatibility:
    """Row-aware legacy classification (see the module decision matrix).

    Order matters and is deliberate — the *reliable* signals are evaluated
    before any tone-shaped heuristic:

    1. legal abstain (diagnosis abstained / abstain reason) → ``basic_wellness``;
    2. known ``wellness`` prescription mode → ``basic_wellness``;
    3. known Sprint 5 fabricated-Gong fallback signature → ``basic_wellness``;
    4. reliable persisted real tone authority (non-empty persisted evidence
       references on a non-wellness row) → ``personalized_five_tone``;
    5. anything else → ``legacy_unclassified`` (fail closed, never guessed).
    """

    if provenance.abstain_reason or provenance.diagnosis_status == "abstained":
        return LegacyModeCompatibility(
            compatibility_state="legacy_derived",
            reason_code=LEGACY_REASON_ABSTAINED,
            regulation_mode="basic_wellness",
        )
    if provenance.prescription_mode == "wellness":
        return LegacyModeCompatibility(
            compatibility_state="legacy_derived",
            reason_code=LEGACY_REASON_WELLNESS_PRESCRIPTION,
            regulation_mode="basic_wellness",
        )
    if is_known_fabricated_fallback(weights):
        return LegacyModeCompatibility(
            compatibility_state="legacy_derived",
            reason_code=LEGACY_REASON_FABRICATED_FALLBACK,
            regulation_mode="basic_wellness",
        )
    mode = provenance.prescription_mode
    has_evidence = bool([ref for ref in evidence_refs if str(ref).strip()])
    reliable_tone_authority = (
        has_evidence
        and mode not in {"wellness"}
        and provenance.diagnosis_status not in {"abstained", "withheld", "failed"}
    )
    if reliable_tone_authority:
        return LegacyModeCompatibility(
            compatibility_state="legacy_derived",
            reason_code=LEGACY_REASON_GENUINE_PERSONALIZED,
            regulation_mode="personalized_five_tone",
        )
    return LegacyModeCompatibility(
        compatibility_state="legacy_unclassified",
        reason_code=LEGACY_REASON_UNCLASSIFIED,
        regulation_mode=None,
    )


# --------------------------------------------------------------------------- #
# checksum: verify the stored payload in its stored schema form
# --------------------------------------------------------------------------- #


def canonical_payload_json(payload: object) -> str:
    """The repository canonical serialisation used for persisted checksums."""

    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def payload_checksum(payload: object) -> str:
    return f"sha256:{sha256(canonical_payload_json(payload).encode('utf-8')).hexdigest()}"


def stored_checksum_matches(stored_payload: object, stored_checksum: str | None) -> bool:
    """Verify a stored payload **without** augmenting it first.

    Legacy rows are validated against the representation that was actually
    persisted, so a compatibility projection can never invalidate an old
    checksum.
    """

    if not stored_checksum:
        return False
    return payload_checksum(stored_payload) == stored_checksum


# --------------------------------------------------------------------------- #
# resolution
# --------------------------------------------------------------------------- #


def _tone_profile_evidence_refs(profile: LegacyToneProfileV31 | ToneProfileV31) -> list[str]:
    return [str(ref) for ref in profile.basis.supporting_evidence_refs]


def _read_model_evidence_refs(read_model: LegacyFiveToneAnalysisReadModelV31) -> list[str]:
    refs: list[str] = []
    for rationale in read_model.analysis_rationales:
        refs.extend(str(ref) for ref in rationale.evidence_refs)
    return refs


def _require_resolved(compat: LegacyModeCompatibility) -> RegulationMode:
    if compat.regulation_mode is None:
        raise LegacyModeUnclassifiedError()
    return compat.regulation_mode


def resolve_tone_profile_payload(
    payload: object,
    provenance: LegacyProvenance,
) -> tuple[ToneProfileV31, LegacyModeCompatibility | None]:
    """Modern tone profile + compatibility metadata (``None`` for modern rows)."""

    if not isinstance(payload, Mapping):
        raise ValueError(f"{UNSUPPORTED_SCHEMA_VERSION}:tone_profile")
    if payload.get("schema_version") == TONE_PROFILE_SCHEMA_VERSION:
        return ToneProfileV31.model_validate(payload), None
    if not is_legacy_tone_profile_payload(payload):
        raise ValueError(f"{UNSUPPORTED_SCHEMA_VERSION}:tone_profile")

    legacy = LegacyToneProfileV31.model_validate(payload)
    compat = classify_legacy_mode(
        weights=legacy.weights,
        evidence_refs=_tone_profile_evidence_refs(legacy),
        provenance=provenance,
    )
    mode = _require_resolved(compat)
    if mode == "personalized_five_tone":
        resolved = ToneProfileV31(
            schema_version=TONE_PROFILE_SCHEMA_VERSION,
            regulation_mode=mode,
            weights=dict(legacy.weights),
            primary_tone=legacy.primary_tone,
            secondary_tone=legacy.secondary_tone,
            score_semantics=legacy.score_semantics,
            mapping_version=legacy.mapping_version,
            basis=legacy.basis,
        )
    else:
        # basic_wellness compatibility: the legacy tone claim is dropped, never
        # re-presented, and no fabricated weights are carried over.
        resolved = ToneProfileV31(
            schema_version=TONE_PROFILE_SCHEMA_VERSION,
            regulation_mode=mode,
            weights=None,
            primary_tone=None,
            secondary_tone=None,
            score_semantics=legacy.score_semantics,
            mapping_version=legacy.mapping_version,
            basis=legacy.basis,
        )
    return resolved, compat


def resolve_read_model_payload(
    payload: object,
    provenance: LegacyProvenance,
    *,
    tone_weights: Mapping[object, object] | None = None,
) -> tuple[FiveToneAnalysisReadModel | FiveToneAnalysisReadModelV33, LegacyModeCompatibility | None]:
    """Modern read model + compatibility metadata (``None`` for modern rows).

    Sprint 6 Phase 1B: ``five_tone_analysis_read_model_v3.3`` rows carry the
    full authoritative dominance audit and are returned as-is. Phase 1A
    ``v3.2`` rows are still returned as ``v3.2`` (they have no Phase 1B audit
    and none is synthesized from ``primary_tone``/``tone_weights``/argmax).

    A pre-Phase-1A read model never persisted tone weights (the field did not
    exist), so a ``personalized_five_tone`` projection can only be produced when
    the row's own persisted tone authority supplies them (``tone_weights``).
    Without that authority the row fails closed instead of inventing weights.
    """

    if not isinstance(payload, Mapping):
        raise ValueError(f"{UNSUPPORTED_SCHEMA_VERSION}:read_model")
    if payload.get("schema_version") == FIVE_TONE_ANALYSIS_SCHEMA_VERSION_V33:
        return FiveToneAnalysisReadModelV33.model_validate(payload), None
    if payload.get("schema_version") == FIVE_TONE_ANALYSIS_SCHEMA_VERSION:
        return FiveToneAnalysisReadModel.model_validate(payload), None
    if not is_legacy_read_model_payload(payload):
        raise ValueError(f"{UNSUPPORTED_SCHEMA_VERSION}:read_model")

    legacy = LegacyFiveToneAnalysisReadModelV31.model_validate(payload)
    compat = classify_legacy_mode(
        weights=None,
        evidence_refs=_read_model_evidence_refs(legacy),
        provenance=provenance,
    )
    mode = _require_resolved(compat)
    personalized = mode == "personalized_five_tone"
    if personalized and not tone_weights:
        raise LegacyModeUnclassifiedError(LEGACY_MISSING_TONE_AUTHORITY)
    resolved = FiveToneAnalysisReadModel(
        schema_version=FIVE_TONE_ANALYSIS_SCHEMA_VERSION,
        confirmed_user_state_ref=legacy.confirmed_user_state_ref,
        confirmed_state=legacy.confirmed_state,
        state_tendency=legacy.state_tendency,
        analysis_rationales=list(legacy.analysis_rationales),
        regulation_mode=mode,
        tone_weights=(
            {ToneCode(str(getattr(k, "value", k))): float(v) for k, v in tone_weights.items()}
            if (personalized and tone_weights)
            else None
        ),
        primary_tone=legacy.primary_tone if personalized else None,
        secondary_tone=legacy.secondary_tone if personalized else None,
        bpm=legacy.bpm,
        instruments=legacy.instruments,
        ambience=legacy.ambience,
        duration=legacy.duration,
        generation=legacy.generation,
        disclaimer=legacy.disclaimer,
    )
    return resolved, compat


def resolve_generation_spec_payload(
    payload: object,
    provenance: LegacyProvenance,
) -> tuple[GenerationSpec, LegacyModeCompatibility | None]:
    """Transport generation spec, resolving a legacy embedded tone profile."""

    if not isinstance(payload, Mapping):
        raise ValueError(f"{UNSUPPORTED_SCHEMA_VERSION}:generation_spec")
    tone_profile = payload.get("tone_profile")
    if not is_legacy_tone_profile_payload(tone_profile):
        return GenerationSpec.model_validate(payload), None
    resolved_profile, compat = resolve_tone_profile_payload(tone_profile, provenance)
    prepared = dict(payload)
    prepared["tone_profile"] = resolved_profile
    return GenerationSpec.model_validate(prepared), compat
