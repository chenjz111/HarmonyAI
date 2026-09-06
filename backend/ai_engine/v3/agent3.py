"""Deterministic V3.1 Agent3 foundation.

This module creates a bounded tone profile from an approved organ-to-tone
mapping. It does not diagnose, infer a syndrome, or let UserGoal alter the
medical evidence calculation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from backend.app.schemas.v3.flow_v31 import (
    BpmExplanation,
    ConfirmedUserStateRef,
    DurationExplanation,
    FiveToneAnalysisReadModel,
    GenerationReadiness,
    ListParameterExplanation,
    PublicRationale,
    PublicToneExplanation,
    ToneProfileV31,
)

from .safe_expression import validate_public_text


class Agent3Blocked(ValueError):
    """Raised when the deterministic Agent3 gate cannot produce a profile."""


_TONE_CODES = ("jiao", "zhi", "gong", "shang", "yu")


def _as_float(value: Any, *, context: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise Agent3Blocked(f"INVALID_MAPPING:{context}") from exc
    if result < 0:
        raise Agent3Blocked(f"INVALID_MAPPING:{context}")
    return result


def _mapping_version(mapping: Mapping[str, Any]) -> str:
    schema_id = str(mapping.get("schema_id", "five-tone_mapping_v3")).strip()
    schema_version = str(mapping.get("schema_version", "")).strip()
    if not schema_version:
        raise Agent3Blocked("INVALID_MAPPING:missing_schema_version")
    return f"{schema_id}@{schema_version}"


def _primary_rules(mapping: Mapping[str, Any]) -> Mapping[str, Any]:
    rules = mapping.get("organ_tone_weights")
    if not isinstance(rules, Mapping):
        raise Agent3Blocked("INVALID_MAPPING:missing_organ_tone_weights")
    primary = rules.get("primary")
    if not isinstance(primary, Mapping):
        raise Agent3Blocked("INVALID_MAPPING:missing_primary_rules")
    return primary


def _calculate_weights(
    organ_weights: Mapping[Any, Any],
    mapping: Mapping[str, Any],
) -> dict[str, float]:
    scores = {tone: 0.0 for tone in _TONE_CODES}
    rules = _primary_rules(mapping)
    for organ, organ_weight in organ_weights.items():
        organ_code = getattr(organ, "value", organ)
        rule = rules.get(str(organ_code))
        if not isinstance(rule, Mapping):
            raise Agent3Blocked(f"INVALID_MAPPING:missing_rule:{organ_code}")
        contribution = _as_float(organ_weight, context=f"organ_weight:{organ_code}")
        for tone, tone_weight in rule.items():
            if str(tone) not in scores:
                raise Agent3Blocked(f"INVALID_MAPPING:tone:{tone}")
            scores[str(tone)] += contribution * _as_float(
                tone_weight, context=f"tone_weight:{organ_code}:{tone}"
            )
    total = sum(scores.values())
    if total <= 0:
        raise Agent3Blocked("INSUFFICIENT_ORGAN_EVIDENCE")
    return {tone: score / total for tone, score in scores.items()}


def build_tone_profile_v31(
    *,
    diagnosis_id: str,
    organ_weights: Mapping[Any, Any],
    supporting_evidence_refs: Sequence[str],
    mapping: Mapping[str, Any],
    diagnosis_revision: int = 1,
    diagnosis_status: str = "available",
    secondary_threshold: float | None = None,
    user_goal: Any = None,
) -> ToneProfileV31:
    """Build the deterministic V3.1 tone profile from approved evidence.

    ``user_goal`` is intentionally accepted only at this boundary for callers
    migrating from older orchestration code; it is never read or persisted in
    the profile and cannot change any score.
    """

    del user_goal
    if diagnosis_status != "available":
        raise Agent3Blocked("DIAGNOSIS_NOT_AVAILABLE")
    if not diagnosis_id or diagnosis_revision < 1:
        raise Agent3Blocked("INVALID_DIAGNOSIS_REFERENCE")
    evidence_refs = [str(ref).strip() for ref in supporting_evidence_refs]
    if not evidence_refs or any(not ref for ref in evidence_refs):
        raise Agent3Blocked("INSUFFICIENT_EVIDENCE_REFERENCES")
    if secondary_threshold is not None and not 0 < secondary_threshold <= 1:
        raise Agent3Blocked("INVALID_SECONDARY_THRESHOLD")

    weights = _calculate_weights(organ_weights, mapping)
    primary = max(_TONE_CODES, key=lambda tone: (weights[tone], -_TONE_CODES.index(tone)))
    secondary = None
    if secondary_threshold is not None:
        candidates = [tone for tone in _TONE_CODES if tone != primary]
        candidates.sort(key=lambda tone: (-weights[tone], _TONE_CODES.index(tone)))
        if candidates and weights[candidates[0]] >= secondary_threshold:
            secondary = candidates[0]

    return ToneProfileV31(
        schema_version="tone_profile_v3.1",
        weights=weights,
        primary_tone=primary,
        secondary_tone=secondary,
        score_semantics="relative_tone_distribution",
        mapping_version=_mapping_version(mapping),
        basis={
            "diagnosis_id": diagnosis_id,
            "diagnosis_revision": diagnosis_revision,
            "supporting_evidence_refs": evidence_refs,
        },
    )


def _tone_table(mapping: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    table = mapping.get("organ_tone_table")
    if not isinstance(table, Sequence) or isinstance(table, (str, bytes)):
        raise Agent3Blocked("INVALID_MAPPING:missing_organ_tone_table")
    indexed: dict[str, Mapping[str, Any]] = {}
    for row in table:
        if not isinstance(row, Mapping):
            raise Agent3Blocked("INVALID_MAPPING:invalid_organ_tone_table_row")
        tone = str(row.get("tone", ""))
        if tone in _TONE_CODES:
            indexed[tone] = row
    if set(indexed) != set(_TONE_CODES):
        raise Agent3Blocked("INVALID_MAPPING:incomplete_organ_tone_table")
    return indexed


def _required_text(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise Agent3Blocked(f"INVALID_PUBLIC_READ_MODEL:{field}")
    return value.strip()


def _tone_explanation(
    tone: str,
    table: Mapping[str, Mapping[str, Any]],
    *,
    secondary: bool,
) -> PublicToneExplanation:
    row = table[tone]
    display_name = row.get("tone_cn")
    if not isinstance(display_name, str) or not display_name.strip():
        raise Agent3Blocked(f"INVALID_MAPPING:missing_tone_display:{tone}")
    role = "辅助" if secondary else "主要"
    explanation = validate_public_text(
        f"作为本次音乐调适参考的{role}声音方向。"
    )
    return PublicToneExplanation(
        tone=tone,
        display_name=display_name.strip(),
        explanation=explanation,
    )


def build_five_tone_analysis_v31(
    *,
    confirmed_user_state_ref: ConfirmedUserStateRef | Mapping[str, Any],
    confirmed_state: str,
    state_tendency: str,
    profile: ToneProfileV31,
    evidence_refs: Sequence[str],
    mapping: Mapping[str, Any],
    generation_parameters: Mapping[str, Any],
    generation_status: str = "not_ready",
    generation_message: str | None = None,
) -> FiveToneAnalysisReadModel:
    """Assemble the public-only V3.1 Five-Tone Analysis read model.

    Music parameters are supplied by the approved downstream parameter
    selector; this function only validates and presents them. It does not
    infer medical claims, call a provider, or expose provider internals.
    """

    if profile.mapping_version != _mapping_version(mapping):
        raise Agent3Blocked("MAPPING_VERSION_MISMATCH")
    refs = [str(ref).strip() for ref in evidence_refs]
    if not refs or any(not ref for ref in refs):
        raise Agent3Blocked("INVALID_PUBLIC_READ_MODEL:evidence_refs")
    tendency = validate_public_text(_required_text(state_tendency, field="state_tendency"))
    params = generation_parameters
    if not isinstance(params, Mapping):
        raise Agent3Blocked("INVALID_PUBLIC_READ_MODEL:generation_parameters")
    bpm = params.get("bpm")
    instruments = params.get("instruments")
    ambience = params.get("ambience")
    duration_seconds = params.get("duration_seconds")
    if type(bpm) is not int or not 40 <= bpm <= 120:
        raise Agent3Blocked("INVALID_PUBLIC_READ_MODEL:bpm")
    if (
        not isinstance(instruments, Sequence)
        or isinstance(instruments, (str, bytes))
        or not instruments
        or any(not isinstance(item, str) or not item.strip() for item in instruments)
    ):
        raise Agent3Blocked("INVALID_PUBLIC_READ_MODEL:instruments")
    if (
        not isinstance(ambience, Sequence)
        or isinstance(ambience, (str, bytes))
        or not ambience
        or any(not isinstance(item, str) or not item.strip() for item in ambience)
    ):
        raise Agent3Blocked("INVALID_PUBLIC_READ_MODEL:ambience")
    if type(duration_seconds) is not int or duration_seconds <= 0:
        raise Agent3Blocked("INVALID_PUBLIC_READ_MODEL:duration_seconds")
    if generation_status not in {"ready", "not_ready"}:
        raise Agent3Blocked("INVALID_PUBLIC_READ_MODEL:generation_status")

    table = _tone_table(mapping)
    primary = _tone_explanation(profile.primary_tone.value, table, secondary=False)
    secondary = (
        _tone_explanation(profile.secondary_tone.value, table, secondary=True)
        if profile.secondary_tone is not None
        else None
    )
    message = generation_message or (
        "音乐参数已准备，可以进入后续生成流程。"
        if generation_status == "ready"
        else "音乐参数已整理，后续生成能力尚未就绪。"
    )
    return FiveToneAnalysisReadModel(
        schema_version="five_tone_analysis_read_model_v3.1",
        confirmed_user_state_ref=confirmed_user_state_ref,
        confirmed_state=_required_text(confirmed_state, field="confirmed_state"),
        state_tendency=tendency,
        analysis_rationales=[
            PublicRationale(
                summary=validate_public_text("已根据本次确认信息整理音乐调适方向。"),
                evidence_refs=refs,
            )
        ],
        primary_tone=primary,
        secondary_tone=secondary,
        bpm=BpmExplanation(
            value=bpm,
            explanation=validate_public_text("按已确认的音乐参数提供参考。"),
        ),
        instruments=ListParameterExplanation(
            values=[item.strip() for item in instruments],
            explanation=validate_public_text("作为本次音乐调适的配器参考。"),
        ),
        ambience=ListParameterExplanation(
            values=[item.strip() for item in ambience],
            explanation=validate_public_text("作为本次音乐调适的环境参考。"),
        ),
        duration=DurationExplanation(
            seconds=duration_seconds,
            explanation=validate_public_text("按本次音乐调适需求提供参考时长。"),
        ),
        generation=GenerationReadiness(
            status=generation_status,
            message=validate_public_text(message),
        ),
        disclaimer=validate_public_text("仅用于音乐调适参考，不构成医学诊断。"),
    )
