"""Server-owned Agent3 adapter for the V3.1 prescription boundary."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from typing import Mapping

from sqlalchemy.orm import Session

from backend.ai_engine.v3.agent3 import (
    Agent3Blocked,
    GenerationSpecV31,
    build_generation_spec_v31,
    build_tone_profile_v31,
)
from backend.app.models.session import Session as SessionModel
from backend.app.models.v3.assessment import (
    AssessmentRevisionV3,
    AssessmentV3,
    FactEvidence,
)
from backend.app.models.v3.diagnosis import DiagnosisRun
from backend.app.schemas.v3.flow_v31 import FiveToneAnalysisReadModel, UserGoalV31
from backend.app.schemas.v3.prescription import (
    GenerationFallbackPolicy,
    GenerationSpec,
    GenerationStructure,
)
from backend.app.services.v3.knowledge_assets import (
    MusicGenerationRuleAssetNotReady,
    load_five_tone_mapping,
    load_music_generation_rules,
)
from backend.app.services.v3.document_relevance_gate import (
    DocumentRelevanceGateError,
    require_active_document_set_relevance,
)


class Agent3NotReady(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def load_agent3_assets() -> tuple[Mapping[str, object], Mapping[str, object]]:
    """Load only the approved deterministic Agent3 assets.

    This deliberately does not initialize Qwen, embeddings, or Chroma again.
    """
    rules_path = os.getenv("V31_MUSIC_GENERATION_RULES_PATH", "").strip()
    rules_version = os.getenv("V31_MUSIC_GENERATION_RULES_VERSION", "").strip()
    rules_checksum = os.getenv("V31_MUSIC_GENERATION_RULES_CHECKSUM", "").strip()
    if not rules_path or not rules_version or not rules_checksum:
        raise Agent3NotReady(
            "MUSIC_PARAMETER_ASSET_NOT_CONFIGURED",
            "音乐参数规则资产版本或校验和尚未配置。",
        )
    try:
        rules = load_music_generation_rules(
            rules_path,
            expected_version=rules_version,
            expected_checksum=rules_checksum,
        )
        mapping = load_five_tone_mapping()
    except MusicGenerationRuleAssetNotReady as error:
        raise Agent3NotReady(error.error_code, error.safe_message) from None
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError) as error:
        raise Agent3NotReady(
            "MUSIC_PARAMETER_ASSET_INVALID",
            "音乐参数规则资产无效。",
        ) from error
    if not isinstance(rules, Mapping) or not isinstance(mapping, Mapping):
        raise Agent3NotReady(
            "MUSIC_PARAMETER_ASSET_INVALID",
            "音乐参数规则资产无效。",
        )
    return mapping, rules


def to_transport_spec(
    internal: GenerationSpecV31,
    *,
    tone_profile,
) -> GenerationSpec:
    duration = internal.duration_seconds
    intro = min(60, max(1, duration // 6))
    outro = min(60, max(1, duration // 6))
    main = duration - intro - outro
    if main < 0:
        intro = duration // 2
        outro = duration - intro
        main = 0
    if internal.bpm <= 68:
        energy_curve = "平稳舒缓"
    elif internal.bpm <= 78:
        energy_curve = "平稳专注"
    else:
        energy_curve = "轻快有活力"
    return GenerationSpec(
        schema_version="generation_spec_v3.0",
        tone_profile=tone_profile,
        bpm=internal.bpm,
        duration_seconds=duration,
        instruments=internal.instruments,
        ambient_sounds=internal.ambience,
        structure=GenerationStructure(
            intro_seconds=intro,
            main_seconds=main,
            outro_seconds=outro,
        ),
        energy_curve=energy_curve,
        forbidden_constraints=[],
        fallback_policy=GenerationFallbackPolicy(allow_local_matching=True),
    )


def load_current_five_tone_read_model(
    db: Session,
    diagnosis: DiagnosisRun,
    session_row: SessionModel,
) -> FiveToneAnalysisReadModel:
    assessment = (
        db.query(AssessmentV3)
        .filter(
            AssessmentV3.assessment_id == diagnosis.assessment_id,
            AssessmentV3.internal_user_pk == diagnosis.internal_user_pk,
            AssessmentV3.session_row_id == session_row.id,
        )
        .one_or_none()
    )
    revision = (
        db.query(AssessmentRevisionV3)
        .filter(
            AssessmentRevisionV3.assessment_id == diagnosis.assessment_id,
            AssessmentRevisionV3.revision == diagnosis.assessment_revision,
        )
        .one_or_none()
    )
    if (
        diagnosis.session_row_id != session_row.id
        or assessment is None
        or revision is None
        or assessment.current_revision != diagnosis.assessment_revision
        or assessment.status != "confirmed"
        or revision.status != "confirmed"
        or revision.confirmation_status != "confirmed"
    ):
        raise Agent3NotReady(
            "ASSESSMENT_SNAPSHOT_CONFLICT",
            "评估结果已更新，请重新完成状态分析。",
        )
    if (
        assessment.input_revision is not None
        and (
            assessment.input_revision != session_row.input_revision
            or revision.input_revision != session_row.input_revision
        )
    ):
        raise Agent3NotReady(
            "ASSESSMENT_SNAPSHOT_CONFLICT",
            "评估输入已更新，请重新完成状态分析。",
        )
    if (
        assessment.understanding_id is not None
        and (
            assessment.understanding_id != session_row.active_understanding_id
            or assessment.understanding_revision
            != session_row.active_understanding_revision
        )
    ):
        raise Agent3NotReady(
            "ASSESSMENT_SNAPSHOT_CONFLICT",
            "资料摘要已更新，请重新完成状态分析。",
        )
    if (
        assessment.questionnaire_submission_id is not None
        and assessment.questionnaire_submission_id
        != session_row.active_questionnaire_submission_id
    ):
        raise Agent3NotReady(
            "ASSESSMENT_SNAPSHOT_CONFLICT",
            "问卷答案已更新，请重新完成状态分析。",
        )
    if session_row.input_mode == "with_document":
        try:
            require_active_document_set_relevance(db, session_row)
        except DocumentRelevanceGateError as error:
            raise Agent3NotReady(
                "ASSESSMENT_SNAPSHOT_CONFLICT",
                "资料可用性状态已更新，请重新完成状态分析。",
            ) from error
    if (
        diagnosis.five_tone_read_model_json is None
        or diagnosis.five_tone_read_model_checksum is None
    ):
        raise Agent3NotReady(
            "FIVE_TONE_SNAPSHOT_NOT_READY",
            "五音调适解析尚未准备完成。",
        )
    try:
        read_model = FiveToneAnalysisReadModel.model_validate(
            diagnosis.five_tone_read_model_json
        )
        canonical = json.dumps(
            read_model.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as error:
        raise Agent3NotReady(
            "FIVE_TONE_SNAPSHOT_INVALID",
            "五音调适解析数据无效。",
        ) from error
    checksum = f"sha256:{sha256(canonical.encode('utf-8')).hexdigest()}"
    if checksum != diagnosis.five_tone_read_model_checksum:
        raise Agent3NotReady(
            "FIVE_TONE_SNAPSHOT_INVALID",
            "五音调适解析数据校验失败。",
        )
    return read_model


def load_current_generation_spec(
    db: Session,
    diagnosis: DiagnosisRun,
    session_row: SessionModel,
) -> GenerationSpec:
    load_current_five_tone_read_model(db, diagnosis, session_row)
    if diagnosis.generation_spec_json is None:
        raise Agent3NotReady(
            "GENERATION_SPEC_NOT_READY",
            "音乐生成参数尚未准备完成。",
        )
    try:
        return GenerationSpec.model_validate(diagnosis.generation_spec_json)
    except (TypeError, ValueError) as error:
        raise Agent3NotReady(
            "GENERATION_SPEC_INVALID",
            "音乐生成参数无效。",
        ) from error


def build_prescription_spec(
    db: Session,
    diagnosis: DiagnosisRun,
    user_goal: UserGoalV31 | None,
) -> GenerationSpec:
    revision = (
        db.query(AssessmentRevisionV3)
        .filter(
            AssessmentRevisionV3.assessment_id == diagnosis.assessment_id,
            AssessmentRevisionV3.revision == diagnosis.assessment_revision,
            AssessmentRevisionV3.confirmation_status == "confirmed",
        )
        .one_or_none()
    )
    if revision is None:
        raise Agent3NotReady("ASSESSMENT_NOT_CONFIRMED", "评估结果尚未确认。")
    organ_profile = revision.organ_profile_json or {}
    if organ_profile.get("status") != "available" or not organ_profile.get("weights"):
        raise Agent3NotReady(
            "INSUFFICIENT_ORGAN_EVIDENCE",
            "当前证据不足以生成五音处方。",
        )
    evidence_refs = [
        row.fact_evidence_id
        for row in db.query(FactEvidence)
        .filter(
            FactEvidence.assessment_id == diagnosis.assessment_id,
            FactEvidence.assessment_revision == diagnosis.assessment_revision,
            FactEvidence.confirmation_status == "confirmed",
        )
        .order_by(FactEvidence.fact_evidence_id)
        .all()
    ]
    if not evidence_refs:
        evidence_refs = [
            f"assessment:{diagnosis.assessment_id}:r{diagnosis.assessment_revision}"
        ]
    mapping, rules = load_agent3_assets()
    try:
        profile = build_tone_profile_v31(
            diagnosis_id=diagnosis.diagnosis_id,
            diagnosis_revision=diagnosis.assessment_revision,
            diagnosis_status=diagnosis.status,
            organ_weights=organ_profile["weights"],
            supporting_evidence_refs=evidence_refs,
            mapping=mapping,
        )
        internal = build_generation_spec_v31(
            profile=profile,
            parameter_rules=rules,
            user_goal=user_goal,
        )
    except Agent3Blocked as error:
        code = str(error) or "AGENT3_NOT_READY"
        raise Agent3NotReady(code, "五音处方规则尚未准备完成。") from error
    return to_transport_spec(internal, tone_profile=profile)
