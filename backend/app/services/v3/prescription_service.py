"""Agent 3 (Prescription) service — non-provider persistence path (Issue #99
step 5).

Creates and reads PrescriptionV3 rows from a confirmed diagnosis, the latest
preference snapshot and the optional user goal. The five-tone / organ mapping
(syndrome → element → tone) is a separate medical rule layer (PR #78/#89); this
service persists a conservative gong-tone wellness GenerationSpec and records
the preference reference so downstream Agent 4 can personalise. It never fakes
a provider result.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from backend.app.models.session import Session as SessionModel
from backend.app.models.v3.diagnosis import DiagnosisRun
from backend.app.models.v3.prescription import PrescriptionV3
from backend.app.schemas.v3.common import AuthPrincipal, ToneCode, UserGoal
from backend.app.schemas.v3.prescription import (
    FallbackToneProfile,
    GenerationFallbackPolicy,
    GenerationSpec,
    GenerationStructure,
    PersonalizationAdjustment,
    PrescriptionPersonalization,
    PrescriptionPresentation,
    PrescriptionV31Request,
    PrescriptionV3 as PrescriptionV3Schema,
    PreferenceProfileRef,
    ToneBasis,
)
from backend.app.services.v3.feedback_service import get_latest_preference_snapshot


# 疗愈诉求 → 保守 BPM / 能量曲线（仅供音乐设计，不进医学证据）。
_USER_GOAL_BPM = {
    "sleep": 60,
    "relaxation": 62,
    "stress_relief": 64,
    "emotion_regulation": 66,
    "focus": 76,
    "energy": 82,
    "other": 68,
}
_USER_GOAL_ENERGY = {
    "sleep": "平稳舒缓",
    "relaxation": "平稳舒缓",
    "stress_relief": "平稳舒缓",
    "emotion_regulation": "平稳舒缓",
    "focus": "平稳专注",
    "energy": "轻快有活力",
    "other": "平稳舒缓",
}


class OwnedResourceNotFound(RuntimeError):
    pass


class DiagnosisNotReady(RuntimeError):
    pass


def _conservative_generation_spec(
    diagnosis_id: str,
    preference,
    user_goal: UserGoal | None,
) -> GenerationSpec:
    tone_profile = FallbackToneProfile(
        schema_version="tone_profile_v3.0",
        weights={
            ToneCode.jiao: 0.1,
            ToneCode.zhi: 0.1,
            ToneCode.gong: 0.6,
            ToneCode.shang: 0.1,
            ToneCode.yu: 0.1,
        },
        dominant_tone=ToneCode.gong,
        score_semantics="relative_tone_distribution",
        mapping_version="tone_mapping_v3.0",
        basis=ToneBasis(diagnosis_id=diagnosis_id, supporting_fact_ids=[]),
        status="fallback",
    )
    # 疗愈诉求先定基调，历史偏好再微调。
    bpm = 62
    energy_curve = "平稳舒缓"
    if user_goal is not None:
        bpm = _USER_GOAL_BPM.get(user_goal.primary_goal.value, 68)
        energy_curve = _USER_GOAL_ENERGY.get(
            user_goal.primary_goal.value, "平稳舒缓"
        )
    instruments = ["guqin"]
    duration = 180
    if preference is not None:
        if preference.preferred_bpm_range is not None:
            bpm = int(
                (preference.preferred_bpm_range.min + preference.preferred_bpm_range.max) / 2
            )
        if preference.preferred_instruments:
            instruments = [
                item.code for item in preference.preferred_instruments[:3]
            ] or instruments
    return GenerationSpec(
        schema_version="generation_spec_v3.0",
        tone_profile=tone_profile,
        bpm=bpm,
        duration_seconds=duration,
        instruments=instruments,
        ambient_sounds=[],
        structure=GenerationStructure(
            intro_seconds=30, main_seconds=120, outro_seconds=30
        ),
        energy_curve=energy_curve,
        forbidden_constraints=[],
        fallback_policy=GenerationFallbackPolicy(allow_local_matching=True),
    )


def _to_schema(row: PrescriptionV3) -> PrescriptionV3Schema:
    spec = GenerationSpec.model_validate(row.generation_spec_json)
    personalization = PrescriptionPersonalization.model_validate(
        row.personalization_json
    )
    presentation = PrescriptionPresentation.model_validate(row.presentation_json)
    return PrescriptionV3Schema(
        schema_version="prescription_v3.0",
        agent_id="prescription_agent",
        prescription_id=row.prescription_id,
        diagnosis_id=row.diagnosis_id,
        status=row.status,
        prescription_mode=row.prescription_mode,
        generation_spec=spec,
        personalization=personalization,
        presentation=presentation,
    )


def _session_user_goal(db: Session, session_row_id: int) -> UserGoal | None:
    session = (
        db.query(SessionModel)
        .filter(SessionModel.id == session_row_id)
        .one_or_none()
    )
    if session is None or session.user_goal_json is None:
        return None
    return UserGoal.model_validate(session.user_goal_json)


def create_prescription(
    db: Session,
    principal: AuthPrincipal,
    request: PrescriptionV31Request,
) -> PrescriptionV3Schema:
    diagnosis = (
        db.query(DiagnosisRun)
        .filter(
            DiagnosisRun.diagnosis_id == request.diagnosis_id,
            DiagnosisRun.internal_user_pk == principal.internal_user_pk,
        )
        .one_or_none()
    )
    if diagnosis is None:
        raise OwnedResourceNotFound
    if diagnosis.status not in {"success", "degraded"}:
        raise DiagnosisNotReady

    user_goal = _session_user_goal(db, diagnosis.session_row_id)
    preference = get_latest_preference_snapshot(db, principal)
    spec = _conservative_generation_spec(request.diagnosis_id, preference, user_goal)

    if preference is not None:
        personalization = PrescriptionPersonalization(
            applied=True,
            profile_ref=PreferenceProfileRef(
                profile_id=preference.profile_id,
                version=preference.version,
            ),
            adjustments=[PersonalizationAdjustment(
                field="bpm", from_="62", to=str(spec.bpm), reason_code="preference"
            )],
        )
        profile_id = preference.profile_id
    else:
        personalization = PrescriptionPersonalization(
            applied=False, profile_ref=None, adjustments=[]
        )
        profile_id = None

    presentation = PrescriptionPresentation(
        title="五音安神音乐处方",
        tone_summary="宫调为主，平稳舒缓。",
        parameter_summaries=[f"{spec.bpm} BPM · 古琴 · {spec.duration_seconds}秒"],
        personalization_summary=(
            "已根据个人偏好微调" if personalization.applied else "未应用个人偏好"
        ),
    )

    row = PrescriptionV3(
        prescription_id=f"rx_{uuid.uuid4().hex}",
        internal_user_pk=principal.internal_user_pk,
        session_row_id=diagnosis.session_row_id,
        diagnosis_id=request.diagnosis_id,
        # Until the real five-tone medical mapping is wired, this is an honest
        # wellness fallback, not a syndrome-based prescription.
        status="degraded",
        prescription_mode="wellness",
        tone_profile_json=spec.tone_profile.model_dump(mode="json"),
        generation_spec_json=spec.model_dump(mode="json"),
        preference_profile_id=profile_id,
        preference_version_id=(
            f"{preference.profile_id}:v{preference.version}"
            if preference is not None
            else None
        ),
        personalization_json=personalization.model_dump(mode="json"),
        presentation_json=presentation.model_dump(mode="json"),
    )
    db.add(row)
    db.commit()
    return _to_schema(row)


def get_prescription(
    db: Session,
    principal: AuthPrincipal,
    prescription_id: str,
) -> PrescriptionV3Schema:
    row = (
        db.query(PrescriptionV3)
        .filter(
            PrescriptionV3.prescription_id == prescription_id,
            PrescriptionV3.internal_user_pk == principal.internal_user_pk,
        )
        .one_or_none()
    )
    if row is None:
        raise OwnedResourceNotFound
    return _to_schema(row)
