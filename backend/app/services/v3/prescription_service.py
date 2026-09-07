"""Agent 3 (Prescription) service — receive + persist Agent3 output, or fallback.

The backend receives the real Agent3 ToneProfile/GenerationSpec and persists it;
it never re-derives a fixed gong-tone scheme. A received spec is trusted only
when its ``tone_profile.basis`` is bound to the confirmed diagnosis id and
assessment revision. A conservative wellness fallback is used when the diagnosis
abstains (safe user, no syndrome to base a spec on) or when the caller explicitly
omits ``generation_spec``.

Idempotency is reserved via the shared helper (a duplicate key while another
request is still processing returns an in-progress state instead of running
side effects again). The preference snapshot is server-authoritative: a
mismatching client snapshot is rejected rather than silently ignored.
"""

from __future__ import annotations

from hashlib import sha256
import json
import uuid

from sqlalchemy.orm import Session

from backend.app.models.session import Session as SessionModel
from backend.app.models.v3.diagnosis import DiagnosisRun
from backend.app.models.v3.prescription import PrescriptionV3
from backend.app.schemas.v3.common import AuthPrincipal, ToneCode
from backend.app.schemas.v3.flow_v31 import (
    ToneProfileBasisV31,
    ToneProfileV31,
    UserGoalV31,
)
from backend.app.schemas.v3.prescription import (
    GenerationFallbackPolicy,
    GenerationSpec,
    GenerationStructure,
    PersonalizationAdjustment,
    PrescriptionPersonalization,
    PrescriptionPresentation,
    PrescriptionV31Request,
    PrescriptionV3 as PrescriptionV3Schema,
    PreferenceProfileRef,
    PreferenceSnapshot,
)
from backend.app.services.v3.feedback_service import get_latest_preference_snapshot
from backend.app.services.v3.idempotency import (
    reserve_v3_idempotency,
)


# 疗愈诉求 → 保守 BPM / 能量曲线（仅 fallback 路径使用，不进医学证据）。
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

_OPERATION = "create_v3_prescription"


class OwnedResourceNotFound(RuntimeError):
    pass


class DiagnosisNotReady(RuntimeError):
    pass


class PreferenceSnapshotConflict(RuntimeError):
    pass


class InvalidSpec(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


_TONE_DISPLAY = {
    ToneCode.jiao: "角调",
    ToneCode.zhi: "徵调",
    ToneCode.gong: "宫调",
    ToneCode.shang: "商调",
    ToneCode.yu: "羽调",
}


def _request_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def _conservative_wellness_spec(
    diagnosis_id: str,
    diagnosis_revision: int,
    preference,
    user_goal: UserGoalV31 | None,
) -> GenerationSpec:
    tone_profile = ToneProfileV31(
        schema_version="tone_profile_v3.1",
        weights={
            ToneCode.jiao: 0.1,
            ToneCode.zhi: 0.1,
            ToneCode.gong: 0.6,
            ToneCode.shang: 0.1,
            ToneCode.yu: 0.1,
        },
        primary_tone=ToneCode.gong,
        secondary_tone=None,
        score_semantics="relative_tone_distribution",
        mapping_version="tone_mapping_v3.0",
        basis=ToneProfileBasisV31(
            diagnosis_id=diagnosis_id,
            diagnosis_revision=diagnosis_revision,
            supporting_evidence_refs=[],
        ),
    )
    bpm = 62
    energy_curve = "平稳舒缓"
    if user_goal is not None and user_goal.primary_goal is not None:
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


def _require_spec_binding(
    spec: GenerationSpec,
    diagnosis_id: str,
    assessment_revision: int,
) -> None:
    """Reject an Agent3 spec that is not bound to the confirmed diagnosis.

    A trusted Agent3 output must trace back to the exact diagnosis id and
    assessment revision the prescription is being created for; otherwise a
    stale or fabricated spec could masquerade as this diagnosis's result.
    """
    basis = spec.tone_profile.basis
    if basis.diagnosis_id != diagnosis_id:
        raise InvalidSpec(
            "SPEC_DIAGNOSIS_MISMATCH",
            "generation_spec 的 tone_profile.basis 未绑定到当前诊断。",
        )
    if basis.diagnosis_revision != assessment_revision:
        raise InvalidSpec(
            "SPEC_REVISION_MISMATCH",
            "generation_spec 的 tone_profile.basis 绑定了过期或不一致的诊断 revision。",
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


def _session_user_goal(db: Session, session_row_id: int) -> UserGoalV31 | None:
    session = (
        db.query(SessionModel)
        .filter(SessionModel.id == session_row_id)
        .one_or_none()
    )
    if session is None or session.user_goal_json is None:
        return None
    return UserGoalV31.model_validate(session.user_goal_json)


def _session_user_goal_revision(db: Session, session_row_id: int) -> int | None:
    session = (
        db.query(SessionModel)
        .filter(SessionModel.id == session_row_id)
        .one_or_none()
    )
    if session is None:
        return None
    return session.user_goal_revision


def _resolve_preference(
    db: Session,
    principal: AuthPrincipal,
    request_snapshot: PreferenceSnapshot | None,
):
    server = get_latest_preference_snapshot(db, principal)
    if request_snapshot is None:
        return server
    if server is None:
        raise PreferenceSnapshotConflict
    if (
        request_snapshot.profile_id != server.profile_id
        or request_snapshot.version != server.version
    ):
        raise PreferenceSnapshotConflict
    return server


def create_prescription(
    db: Session,
    principal: AuthPrincipal,
    request: PrescriptionV31Request,
    *,
    idempotency_key: str,
) -> tuple[PrescriptionV3Schema, bool]:
    request_hash = _request_hash(request.model_dump(mode="json"))
    record, replayed = reserve_v3_idempotency(
        db,
        internal_user_pk=principal.internal_user_pk,
        operation=_OPERATION,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
    )
    if replayed:
        return PrescriptionV3Schema.model_validate_json(record.response_json), True

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
    if diagnosis.status in {"withheld", "failed"}:
        raise DiagnosisNotReady

    user_goal = _session_user_goal(db, diagnosis.session_row_id)
    user_goal_revision = _session_user_goal_revision(db, diagnosis.session_row_id)
    preference = _resolve_preference(db, principal, request.preference_snapshot)

    # Receive the real Agent3 GenerationSpec, or fall back explicitly.
    abstained = diagnosis.status == "abstained" or bool(diagnosis.abstained)
    if abstained:
        # Abstained diagnosis (safe user, no syndrome identified): the backend
        # must not fake a syndrome-based spec. Fall back to conservative
        # wellness, and reject any Agent3 spec as untrusted input.
        if request.generation_spec is not None:
            raise InvalidSpec(
                "SPEC_UNEXPECTED_FOR_ABSTAINED",
                "诊断已 abstain，不接受 generation_spec，应回退到保守 wellness 方案。",
            )
        spec = _conservative_wellness_spec(
            request.diagnosis_id,
            diagnosis.assessment_revision,
            preference,
            user_goal,
        )
        status = "degraded"
        mode = "wellness"
    elif request.generation_spec is not None:
        _require_spec_binding(
            request.generation_spec,
            request.diagnosis_id,
            diagnosis.assessment_revision,
        )
        spec = request.generation_spec
        status = "success"
        mode = "syndrome_based"
    else:
        spec = _conservative_wellness_spec(
            request.diagnosis_id,
            diagnosis.assessment_revision,
            preference,
            user_goal,
        )
        status = "degraded"
        mode = "wellness"

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

    primary_tone_display = _TONE_DISPLAY[spec.tone_profile.primary_tone]
    tone_summary = f"{primary_tone_display}为主"
    if spec.tone_profile.secondary_tone is not None:
        tone_summary += f"，{_TONE_DISPLAY[spec.tone_profile.secondary_tone]}为辅"
    tone_summary += f"，{spec.energy_curve}。"
    instruments = "、".join(spec.instruments)

    presentation = PrescriptionPresentation(
        title="五音安神音乐处方",
        tone_summary=tone_summary,
        parameter_summaries=[
            f"{spec.bpm} BPM · {instruments} · {spec.duration_seconds}秒"
        ],
        personalization_summary=(
            "已根据个人偏好微调" if personalization.applied else "未应用个人偏好"
        ),
    )

    row = PrescriptionV3(
        prescription_id=f"rx_{uuid.uuid4().hex}",
        internal_user_pk=principal.internal_user_pk,
        session_row_id=diagnosis.session_row_id,
        diagnosis_id=request.diagnosis_id,
        status=status,
        prescription_mode=mode,
        tone_profile_json=spec.tone_profile.model_dump(mode="json"),
        generation_spec_json=spec.model_dump(mode="json"),
        preference_profile_id=profile_id,
        preference_version_id=(
            f"{preference.profile_id}:v{preference.version}"
            if preference is not None
            else None
        ),
        user_goal_revision=user_goal_revision,
        user_goal_json=(
            user_goal.model_dump(mode="json") if user_goal is not None else None
        ),
        personalization_json=personalization.model_dump(mode="json"),
        presentation_json=presentation.model_dump(mode="json"),
    )
    db.add(row)
    db.flush()

    result = _to_schema(row)
    record.resource_type = "prescription"
    record.resource_id = row.prescription_id
    record.status = "succeeded"
    record.response_code = 201
    record.response_json = result.model_dump_json()
    db.commit()
    return result, False


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
