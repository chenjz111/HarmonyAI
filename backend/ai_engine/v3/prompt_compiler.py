"""Sprint 6 Phase 5 — Prompt Compiler V2 (music-generation prompt only).

The compiler turns an already-authoritative ``GenerationSpec`` into a
deterministic, provider-safe music prompt:

    authoritative GenerationSpec
        -> CanonicalMusicPrompt (typed fragments, each with its source field)
        -> provider dialect renderer
        -> CompiledPrompt (text + checksums + compiler identity)

Guarantees (frozen Phase 5 decisions P5-D1..P5-D5):

* pure, deterministic, side-effect free, I/O free: the same spec + dialect +
  compiler version always produce the same canonical model, text and checksum;
* it may translate/normalize/serialize the spec but never invent or alter a
  music decision (tone, weights, bpm, duration target, instruments, ambience,
  structure, energy);
* raw internal tone enum values (``jiao``/``zhi``/``gong``/``shang``/``yu``) are
  never interpolated into the final prompt; a versioned descriptor table owns
  the tone vocabulary for all dialects;
* authoritative tone weights are rendered as emphasis text and are never
  renormalized, re-ranked or invented;
* approved instrument names/aliases normalize to canonical tokens and unknown
  values fail closed before any network call;
* a "no extra ambient sound" value never becomes an ambience fragment;
* the compiler introduces no diagnosis/syndrome/disease/severity/treatment
  wording, and it never consumes narrative, OCR, provider prose or candidate
  text — only the authoritative generation spec.

No LLM/provider/embedding call happens here, and no full prompt text is
persisted by this module: callers persist the identity from
``CompiledPrompt.audit_identity()`` only.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
import re
from typing import Any, Mapping

from backend.ai_engine.v3.music_provider import (
    MusicProviderFailureV3,
    ambient_prompt_parts,
    normalize_instruments,
)

#: Frozen compiler version; part of the persisted audit identity.
PROMPT_COMPILER_VERSION = "prompt-compiler-v2.0-r1"

#: Version of the canonical intermediate model (persisted as the audit row's
#: request/schema identity alongside the compiler version).
CANONICAL_MUSIC_PROMPT_VERSION = "canonical_music_prompt_v1"

#: Version of the canonical tone descriptor table (P5-D2).
TONE_DESCRIPTOR_VERSION = "tone-prompt-descriptors-v1"


class PromptDialect(str, Enum):
    """The three migrated provider prompt dialects (no registry in Phase 5)."""

    TOKENHUB_MINIMAX = "tokenhub"
    MINIMAX = "minimax"
    STABILITY = "stability"


#: Per-dialect prompt length caps. These preserve the existing provider
#: contracts exactly (TokenHub 2000, MiniMax 2000, Stability 10000).
PROMPT_MAX_LENGTH: Mapping[PromptDialect, int] = {
    PromptDialect.TOKENHUB_MINIMAX: 2000,
    PromptDialect.MINIMAX: 2000,
    PromptDialect.STABILITY: 10000,
}

#: Canonical tone vocabulary (P5-D2). Pure musical language: no organ names, no
#: disease/syndrome terms, no diagnosis/severity wording, and no raw enum value.
TONE_PROMPT_DESCRIPTORS: Mapping[str, str] = {
    "jiao": "bright, gently rising melodic contour",
    "zhi": "warm, lively melodic contour",
    "gong": "grounded, steady melodic contour",
    "shang": "clear, resonant melodic contour",
    "yu": "deep, flowing melodic contour",
}

_BASE_FRAGMENT = "Traditional Chinese instrumental healing music"
_NO_TONE_FALLBACK = "warm acoustic textures"

_LENGTH_SAFE_MESSAGE = "音乐生成提示词过长，无法提交生成服务。"
_CONTRACT_SAFE_MESSAGE = "音乐生成参数不完整，无法提交生成服务。"

#: Compiler-owned medical-neutrality guard (allow-by-construction plus a fixed
#: lexical guard over the fragments the compiler itself renders). This is a
#: literal deny-list, deliberately not an NLP classifier and not a second model.
_FORBIDDEN_MEDICAL_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bdiagnos\w*",
        r"\bsyndrom\w*",
        r"\bdisease\w*",
        r"\bdisorder\w*",
        r"\bseverit\w*",
        r"\btreat\w*",
        r"\bmedicat\w*",
        r"\bmedicin\w*",
        r"\bprescri\w*",
        r"\bpatient\w*",
        r"诊断|辨证|证型|确诊|疾病|病症|症状|严重程度|治疗|用药|药物|处方|患者",
    )
)


class PromptCompilerContractError(RuntimeError):
    """Internal marker for an unsatisfiable authoritative input.

    Providers wrap it into the long-standing ``GENERATION_PROVIDER_REJECTED``
    contract so no new public error code is introduced; the marker stays on the
    failure's ``cause`` for diagnosis/audit.
    """

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


@dataclass(frozen=True)
class PromptFragment:
    """One rendered prompt fragment plus the authoritative field it came from."""

    source_field: str
    text: str


@dataclass(frozen=True)
class CanonicalMusicPrompt:
    """Deterministic intermediate model, built from the generation spec only."""

    dialect: PromptDialect
    fragments: tuple[PromptFragment, ...]

    def render(self) -> str:
        """Render the final prompt text (single deterministic joining rule)."""

        return " ".join(fragment.text for fragment in self.fragments) + "."

    def payload(self) -> dict[str, Any]:
        """JSON-ready view for tests/debugging (fragments + source identity)."""

        return {
            "model_version": CANONICAL_MUSIC_PROMPT_VERSION,
            "dialect_id": self.dialect.value,
            "fragments": [
                {"source_field": item.source_field, "text": item.text}
                for item in self.fragments
            ],
        }


@dataclass(frozen=True)
class CompiledPrompt:
    """Final prompt text plus the identity persisted in the generation audit."""

    text: str
    checksum: str
    compiler_version: str
    dialect_id: str
    input_spec_checksum: str

    def audit_identity(self) -> dict[str, str]:
        """The prompt identity persisted by default (never the prompt text)."""

        return {
            "compiler_version": self.compiler_version,
            "dialect_id": self.dialect_id,
            "prompt_checksum": self.checksum,
            "input_spec_checksum": self.input_spec_checksum,
        }


def _value(item: Any) -> Any:
    """Unwrap str-Enum values (e.g. ``ToneCode.jiao`` -> ``"jiao"``)."""

    return getattr(item, "value", item)


def _get(source: Any, name: str, default: Any = None) -> Any:
    if isinstance(source, Mapping):
        return source.get(name, default)
    return getattr(source, name, default)


def _tone_code(value: Any) -> str | None:
    unwrapped = _value(value)
    if not isinstance(unwrapped, str) or not unwrapped.strip():
        return None
    return unwrapped.strip()


def _tone_descriptor(tone: str) -> str:
    descriptor = TONE_PROMPT_DESCRIPTORS.get(tone)
    if descriptor is None:
        raise PromptCompilerContractError("PROMPT_COMPILER_TONE_UNKNOWN")
    return descriptor


def _format_weight(value: Any) -> str:
    try:
        return f"{float(value):g}"
    except (TypeError, ValueError):
        raise PromptCompilerContractError("PROMPT_COMPILER_TONE_WEIGHT_INVALID") from None


def _tone_weights(tone_profile: Any) -> Mapping[str, Any] | None:
    weights = _get(tone_profile, "weights")
    if not isinstance(weights, Mapping):
        return None
    return {str(_value(key)): value for key, value in weights.items()}


def _structure_fragment(structure: Any) -> str:
    intro = _get(structure, "intro_seconds", 0)
    main = _get(structure, "main_seconds", 0)
    outro = _get(structure, "outro_seconds", 0)
    return f"Structure: intro {intro}s, main {main}s, outro {outro}s"


def _tone_fragment(tone_profile: Any) -> PromptFragment | None:
    """Tone/weight fragment. Never renders a raw enum; never invents a tone."""

    if tone_profile is None:
        return None
    mode = _value(_get(tone_profile, "regulation_mode"))
    primary = _tone_code(_get(tone_profile, "primary_tone"))
    secondary = _tone_code(_get(tone_profile, "secondary_tone"))
    weights = _tone_weights(tone_profile)

    if primary is not None:
        if weights is None or primary not in weights:
            # P5-D3: authoritative weights must exist; never invent or renormalize.
            raise PromptCompilerContractError("PROMPT_COMPILER_TONE_WEIGHT_MISSING")
        clause = (
            f"in a {_tone_descriptor(primary)} mode "
            f"(primary tone emphasis {_format_weight(weights[primary])}"
        )
        if secondary is not None:
            if secondary not in weights:
                raise PromptCompilerContractError(
                    "PROMPT_COMPILER_TONE_WEIGHT_MISSING"
                )
            clause += (
                f"; secondary {_tone_descriptor(secondary)} emphasis "
                f"{_format_weight(weights[secondary])}"
            )
        clause += ")"
        return PromptFragment(source_field="tone_profile.primary_tone", text=clause)

    if mode == "integrated_regulation":
        return PromptFragment(
            source_field="tone_profile.regulation_mode",
            text="balanced five-tone blend without a dominant tone",
        )
    if mode == "basic_wellness":
        return PromptFragment(
            source_field="tone_profile.regulation_mode",
            text="neutral, gentle soundscape without a tone conclusion",
        )
    # No primary tone and no recognised mode: make no tone claim at all.
    return None


def _distribution_fragment(tone_profile: Any) -> PromptFragment | None:
    """State that an authoritative neutral distribution was retained.

    The five-tone distribution is authoritative input; a neutral mode therefore
    keeps it visible without enumerating raw tone enums or inventing a ranking.
    """

    if tone_profile is None:
        return None
    weights = _tone_weights(tone_profile)
    if not weights:
        return None
    if _tone_code(_get(tone_profile, "primary_tone")) is not None:
        return None
    return PromptFragment(
        source_field="tone_profile.weights",
        text="neutral five-tone distribution retained",
    )


def _duration_fragment(dialect: PromptDialect, seconds: Any) -> str:
    if dialect is PromptDialect.TOKENHUB_MINIMAX:
        # TokenHub/MiniMax music has no duration parameter: this is a target.
        return f"target length about {seconds} seconds"
    return f"total duration {seconds} seconds"


def build_canonical_prompt(spec: Any, dialect: PromptDialect) -> CanonicalMusicPrompt:
    """Build the deterministic canonical model from the authoritative spec."""

    tone_profile = _get(spec, "tone_profile")
    fragments: list[PromptFragment] = [
        PromptFragment(source_field="generation_spec.kind", text=_BASE_FRAGMENT)
    ]

    tone_fragment = _tone_fragment(tone_profile)
    if tone_fragment is not None:
        fragments.append(tone_fragment)
    distribution_fragment = _distribution_fragment(tone_profile)
    if distribution_fragment is not None:
        fragments.append(distribution_fragment)

    fragments.append(
        PromptFragment(source_field="generation_spec.bpm", text=f"bpm {_get(spec, 'bpm')}")
    )
    fragments.append(
        PromptFragment(
            source_field="generation_spec.duration_seconds",
            text=_duration_fragment(dialect, _get(spec, "duration_seconds")),
        )
    )

    instruments = normalize_instruments(list(_get(spec, "instruments") or ()))
    rendered_instruments = ", ".join(instruments) or _NO_TONE_FALLBACK
    fragments.append(
        PromptFragment(
            source_field="generation_spec.instruments",
            text=f"Instruments: {rendered_instruments}",
        )
    )

    fragments.append(
        PromptFragment(
            source_field="generation_spec.structure",
            text=_structure_fragment(_get(spec, "structure")),
        )
    )
    fragments.append(
        PromptFragment(
            source_field="generation_spec.energy_curve",
            text=f"Energy: {_get(spec, 'energy_curve')}",
        )
    )

    ambient_parts = ambient_prompt_parts(list(_get(spec, "ambient_sounds") or ()))
    if ambient_parts:
        fragments.append(
            PromptFragment(
                source_field="generation_spec.ambient_sounds",
                text="Atmosphere: " + ", ".join(ambient_parts) + ".",
            )
        )

    constraints = [
        str(item)
        for item in (_get(spec, "forbidden_constraints") or ())
        if str(item).strip()
    ]
    if constraints:
        fragments.append(
            PromptFragment(
                source_field="generation_spec.forbidden_constraints",
                text="Avoid: " + ", ".join(constraints) + ".",
            )
        )

    return CanonicalMusicPrompt(dialect=dialect, fragments=tuple(fragments))


def _sha256(value: str) -> str:
    return f"sha256:{sha256(value.encode('utf-8')).hexdigest()}"


def input_spec_checksum(spec: Any) -> str:
    """Stable digest of the prompt-relevant authoritative spec fields only.

    No timestamp, request id, retrieval id or other per-run value is included.
    """

    tone_profile = _get(spec, "tone_profile")
    weights = _tone_weights(tone_profile)
    payload: dict[str, Any] = {
        "bpm": _get(spec, "bpm"),
        "duration_seconds": _get(spec, "duration_seconds"),
        "instruments": list(normalize_instruments(list(_get(spec, "instruments") or ()))),
        "ambient_sounds": [
            str(item).strip() for item in (_get(spec, "ambient_sounds") or ())
        ],
        "structure": {
            "intro_seconds": _get(_get(spec, "structure"), "intro_seconds", 0),
            "main_seconds": _get(_get(spec, "structure"), "main_seconds", 0),
            "outro_seconds": _get(_get(spec, "structure"), "outro_seconds", 0),
        },
        "energy_curve": _get(spec, "energy_curve"),
        "forbidden_constraints": [
            str(item) for item in (_get(spec, "forbidden_constraints") or ())
        ],
        "regulation_mode": _value(_get(tone_profile, "regulation_mode")),
        "primary_tone": _tone_code(_get(tone_profile, "primary_tone")),
        "secondary_tone": _tone_code(_get(tone_profile, "secondary_tone")),
        "tone_weights": (
            None
            if weights is None
            else {tone: weights[tone] for tone in sorted(weights)}
        ),
    }
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return _sha256(encoded)


def _assert_medical_neutral(text: str) -> None:
    for pattern in _FORBIDDEN_MEDICAL_PATTERNS:
        if pattern.search(text):
            raise PromptCompilerContractError("PROMPT_COMPILER_MEDICAL_LANGUAGE")


def compile_music_prompt(spec: Any, dialect: PromptDialect) -> CompiledPrompt:
    """Compile the authoritative generation spec into a provider-safe prompt.

    Deterministic and pure: same spec + dialect + compiler version yields the
    same canonical model, text and checksums. Fails closed (before any network
    call) on unsupported instruments, missing authoritative weights, medical
    vocabulary and prompt-length overflow.
    """

    try:
        if not isinstance(dialect, PromptDialect):
            raise PromptCompilerContractError("PROMPT_COMPILER_DIALECT_UNKNOWN")
        canonical = build_canonical_prompt(spec, dialect)
        text = canonical.render()
        _assert_medical_neutral(text)
        max_length = PROMPT_MAX_LENGTH[dialect]
        if len(text) > max_length:
            raise MusicProviderFailureV3(
                "GENERATION_PROVIDER_REJECTED",
                retryable=False,
                safe_message=_LENGTH_SAFE_MESSAGE,
            )
        return CompiledPrompt(
            text=text,
            checksum=_sha256(text),
            compiler_version=PROMPT_COMPILER_VERSION,
            dialect_id=dialect.value,
            input_spec_checksum=input_spec_checksum(spec),
        )
    except PromptCompilerContractError as error:
        raise MusicProviderFailureV3(
            "GENERATION_PROVIDER_REJECTED",
            retryable=False,
            safe_message=_CONTRACT_SAFE_MESSAGE,
            cause=error,
        ) from error
