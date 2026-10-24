"""Deterministic, non-medical preference policy for canonical Agent3 output."""

from __future__ import annotations

from typing import Any

from backend.app.schemas.v3.common import V3BaseModel
from backend.app.schemas.v3.flow_v31 import FiveToneAnalysisReadModel
from backend.app.schemas.v3.prescription import PreferenceSnapshot
from backend.app.schemas.v3.prescription import GenerationSpec, GenerationStructure


class PreferenceApplication(V3BaseModel):
    field: str
    before: Any
    after: Any
    applied: bool
    reason_code: str


def _ranked_codes(items) -> list[str]:
    return [item.code for item in sorted(items, key=lambda item: (-item.weight, item.code))]


def apply_preference_policy(
    read_model: FiveToneAnalysisReadModel,
    preference: PreferenceSnapshot,
) -> tuple[FiveToneAnalysisReadModel, list[PreferenceApplication]]:
    """Apply only approved music-design preferences and report exact effects.

    Medical evidence, tone selection, rationale and readiness are immutable at
    this boundary. Equal or unusable preferences are recorded as no-ops.
    """

    updates: dict[str, object] = {}
    events: list[PreferenceApplication] = []

    if preference.preferred_bpm_range is not None:
        before = read_model.bpm.value
        low = max(40, preference.preferred_bpm_range.min)
        high = min(120, preference.preferred_bpm_range.max)
        target = max(low, min(high, round((low + high) / 2)))
        applied = target != before
        if applied:
            updates["bpm"] = read_model.bpm.model_copy(update={"value": target})
        events.append(
            PreferenceApplication(
                field="bpm",
                before=before,
                after=target if applied else before,
                applied=applied,
                reason_code="preference_applied" if applied else "no_change",
            )
        )

    disliked = set(_ranked_codes(preference.disliked_instruments))
    preferred_instruments = [
        code for code in _ranked_codes(preference.preferred_instruments)
        if code not in disliked
    ][:3]
    if preference.preferred_instruments or preference.disliked_instruments:
        before = list(read_model.instruments.values)
        target = preferred_instruments or [code for code in before if code not in disliked]
        usable = bool(target)
        applied = usable and target != before
        if applied:
            updates["instruments"] = read_model.instruments.model_copy(
                update={"values": target}
            )
        events.append(
            PreferenceApplication(
                field="instruments",
                before=before,
                after=target if applied else before,
                applied=applied,
                reason_code=(
                    "preference_applied" if applied
                    else "no_usable_value" if not usable
                    else "no_change"
                ),
            )
        )

    if preference.preferred_ambient:
        before = list(read_model.ambience.values)
        target = _ranked_codes(preference.preferred_ambient)[:3]
        applied = target != before
        if applied:
            updates["ambience"] = read_model.ambience.model_copy(
                update={"values": target}
            )
        events.append(
            PreferenceApplication(
                field="ambient_sounds",
                before=before,
                after=target if applied else before,
                applied=applied,
                reason_code="preference_applied" if applied else "no_change",
            )
        )

    if preference.preferred_duration_seconds is not None:
        before = read_model.duration.seconds
        target = preference.preferred_duration_seconds.value
        applied = target != before
        if applied:
            updates["duration"] = read_model.duration.model_copy(
                update={"seconds": target}
            )
        events.append(
            PreferenceApplication(
                field="duration_seconds",
                before=before,
                after=target if applied else before,
                applied=applied,
                reason_code="preference_applied" if applied else "no_change",
            )
        )

    return read_model.model_copy(update=updates), events


def synchronize_generation_spec(
    spec: GenerationSpec,
    read_model: FiveToneAnalysisReadModel,
) -> GenerationSpec:
    """Copy approved public music parameters into the provider-facing spec."""

    duration = read_model.duration.seconds
    intro = min(60, max(1, duration // 6))
    outro = min(60, max(1, duration // 6))
    main = duration - intro - outro
    if main < 0:
        intro = duration // 2
        outro = duration - intro
        main = 0
    return spec.model_copy(
        update={
            "bpm": read_model.bpm.value,
            "duration_seconds": duration,
            "instruments": list(read_model.instruments.values),
            "ambient_sounds": list(read_model.ambience.values),
            "structure": GenerationStructure(
                intro_seconds=intro,
                main_seconds=main,
                outro_seconds=outro,
            ),
        }
    )
