"""Deterministic V3.1 Agent3 foundation.

This module creates a bounded tone profile from an approved organ-to-tone
mapping. It does not diagnose, infer a syndrome, or let UserGoal alter the
medical evidence calculation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal

from backend.app.schemas.v3.common import NonEmptyString, Score01, ToneCode, V3BaseModel
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


class GenerationSpecV31(V3BaseModel):
    """Internal deterministic GenerationSpec for the V3.1 Agent 3 boundary.

    This is intentionally separate from the existing V3.0 music transport
    schema.  The V3.1 public page consumes the frozen read model; this object
    is produced from approved rule data and is never chosen by an LLM.
    """

    schema_version: Literal["generation_spec_v3.1"]
    primary_tone: ToneCode
    secondary_tone: ToneCode | None
    tone_weights: dict[ToneCode, Score01]
    bpm: int
    instruments: list[NonEmptyString]
    ambience: list[NonEmptyString]
    duration_seconds: int
    explanations: dict[NonEmptyString, NonEmptyString]
    readiness: Literal["ready", "not_ready"]
    blocking_reasons: list[NonEmptyString]
    secondary_tone_blocked: bool


def build_generation_spec_v31(
    *,
    profile: ToneProfileV31,
    parameter_rules: Mapping[str, Any] | None,
    user_goal: Mapping[str, Any] | Any | None = None,
    secondary_threshold: float | None = None,
) -> GenerationSpecV31:
    """Build music parameters from a reviewed, versioned deterministic rule asset.

    UserGoal is only a selector for an explicitly named rule row.  It never
    changes the medical tone profile, and the goal payload is not copied into
    the GenerationSpec.  A custom-only goal has no approved rule selector and
    therefore safely uses the default rule row.  Missing or unapproved music
    rules are an explicit readiness block rather than an invented default.
    """

    if not isinstance(parameter_rules, Mapping):
        raise Agent3Blocked("MUSIC_PARAMETER_ASSET_UNAVAILABLE")
    if (
        parameter_rules.get("schema_id") != "music_generation_rules_v3.1"
        or parameter_rules.get("review_status") != "approved"
    ):
        raise Agent3Blocked("MUSIC_PARAMETER_ASSET_UNAVAILABLE")
    default = parameter_rules.get("default")
    if not isinstance(default, Mapping):
        raise Agent3Blocked("MUSIC_PARAMETER_ASSET_INVALID")

    selected = dict(default)
    goal_code = _goal_code(user_goal)
    if goal_code is not None:
        goals = parameter_rules.get("goals")
        goal_rules = goals.get(goal_code) if isinstance(goals, Mapping) else None
        if not isinstance(goal_rules, Mapping):
            raise Agent3Blocked("USER_GOAL_RULE_NOT_APPROVED")
        selected.update(goal_rules)

    bpm = selected.get("bpm")
    instruments = selected.get("instruments")
    ambience = selected.get("ambience")
    duration = selected.get("duration_seconds")
    if type(bpm) is not int or not 40 <= bpm <= 120:
        raise Agent3Blocked("MUSIC_PARAMETER_ASSET_INVALID")
    if not _string_list(instruments) or not _string_list(ambience):
        raise Agent3Blocked("MUSIC_PARAMETER_ASSET_INVALID")
    if type(duration) is not int or duration <= 0:
        raise Agent3Blocked("MUSIC_PARAMETER_ASSET_INVALID")

    explanations = selected.get("explanations") or default.get("explanations")
    if not isinstance(explanations, Mapping):
        raise Agent3Blocked("MUSIC_PARAMETER_ASSET_INVALID")
    explanation_keys = {"bpm", "instruments", "ambience", "duration"}
    if set(explanations) != explanation_keys or any(
        not isinstance(value, str) or not value.strip()
        for value in explanations.values()
    ):
        raise Agent3Blocked("MUSIC_PARAMETER_ASSET_INVALID")

    # Secondary tone is optional in the frozen flow. Keep its absence
    # observable, but do not block the approved primary tone and parameters.
    blocking_reasons: list[str] = []
    spec = GenerationSpecV31(
        schema_version="generation_spec_v3.1",
        primary_tone=profile.primary_tone,
        secondary_tone=profile.secondary_tone,
        tone_weights=profile.weights,
        bpm=bpm,
        instruments=_string_list(instruments),
        ambience=_string_list(ambience),
        duration_seconds=duration,
        explanations={
            key: validate_public_text(str(explanations[key]))
            for key in sorted(explanation_keys)
        },
        readiness="ready",
        blocking_reasons=blocking_reasons,
        secondary_tone_blocked=secondary_threshold is None,
    )
    return spec


def _goal_code(user_goal: Mapping[str, Any] | Any | None) -> str | None:
    if user_goal is None:
        return None
    from backend.app.schemas.v3.flow_v31 import UserGoalV31

    try:
        parsed = UserGoalV31.model_validate(user_goal)
    except (TypeError, ValueError) as error:
        raise Agent3Blocked("USER_GOAL_INVALID") from error
    if (
        parsed.primary_goal is None
        and parsed.secondary_goal is None
        and parsed.custom_goal_text is None
    ):
        return None
    # Custom text is a bounded preference only. Without an approved goal code,
    # it must not block generation or be interpreted as a medical instruction.
    return parsed.primary_goal.value if parsed.primary_goal is not None else None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    values = [item.strip() for item in value if isinstance(item, str) and item.strip()]
    return values if len(values) == len(value) else []


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
    if diagnosis_status not in {"available", "success", "degraded"}:
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
    generation_spec: GenerationSpecV31 | Mapping[str, Any],
) -> FiveToneAnalysisReadModel:
    """Assemble the public-only V3.1 Five-Tone Analysis read model.

    Music parameters are supplied by ``build_generation_spec_v31`` from an
    approved deterministic rule asset. This function only presents that
    object and never accepts caller-selected raw parameters.
    """

    if profile.mapping_version != _mapping_version(mapping):
        raise Agent3Blocked("MAPPING_VERSION_MISMATCH")
    refs = [str(ref).strip() for ref in evidence_refs]
    if not refs or any(not ref for ref in refs):
        raise Agent3Blocked("INVALID_PUBLIC_READ_MODEL:evidence_refs")
    tendency = validate_public_text(_required_text(state_tendency, field="state_tendency"))
    try:
        spec = GenerationSpecV31.model_validate(generation_spec)
    except (TypeError, ValueError) as error:
        raise Agent3Blocked("INVALID_GENERATION_SPEC") from error
    if spec.primary_tone != profile.primary_tone or spec.tone_weights != profile.weights:
        raise Agent3Blocked("GENERATION_SPEC_TONE_MISMATCH")

    table = _tone_table(mapping)
    primary = _tone_explanation(spec.primary_tone.value, table, secondary=False)
    secondary = (
        _tone_explanation(spec.secondary_tone.value, table, secondary=True)
        if spec.secondary_tone is not None
        else None
    )
    if spec.readiness == "ready" and spec.secondary_tone_blocked:
        message = "音乐参数已准备；次要音调规则尚未获批准，当前使用主要音调参考。"
    elif spec.readiness == "ready":
        message = "音乐参数已准备，可以进入后续生成流程。"
    else:
        message = "音乐参数已整理，后续生成能力尚未就绪。"
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
            value=spec.bpm,
            explanation=spec.explanations["bpm"],
        ),
        instruments=ListParameterExplanation(
            values=spec.instruments,
            explanation=spec.explanations["instruments"],
        ),
        ambience=ListParameterExplanation(
            values=spec.ambience,
            explanation=spec.explanations["ambience"],
        ),
        duration=DurationExplanation(
            seconds=spec.duration_seconds,
            explanation=spec.explanations["duration"],
        ),
        generation=GenerationReadiness(
            status=spec.readiness,
            message=validate_public_text(message),
        ),
        disclaimer=validate_public_text("仅用于音乐调适参考，不构成医学诊断。"),
    )
