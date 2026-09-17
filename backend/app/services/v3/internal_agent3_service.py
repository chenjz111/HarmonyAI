"""Server-owned Agent3 adapter for the V3.1 prescription boundary."""

from __future__ import annotations

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
from backend.app.services.v3 import legacy_mode_compat
from backend.app.services.v3.legacy_mode_compat import LegacyProvenance
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


def _persisted_tone_weights(diagnosis: DiagnosisRun) -> Mapping[str, float] | None:
    """Tone weights from this row's own persisted tone authority, if any."""

    if diagnosis.generation_spec_json is None:
        return None
    try:
        spec, _compatibility = legacy_mode_compat.resolve_generation_spec_payload(
            diagnosis.generation_spec_json,
            LegacyProvenance(
                source="diagnosis",
                diagnosis_status=diagnosis.status,
                abstain_reason=diagnosis.abstain_reason,
            ),
        )
    except (TypeError, ValueError, legacy_mode_compat.LegacyModeUnclassifiedError):
        return None
    return spec.tone_profile.weights


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
    # Canonical sequence: verify the stored payload **as stored** (its own
    # schema form and checksum) before any compatibility augmentation, then
    # parse/resolve. The derived view never rewrites the stored payload.
    if not legacy_mode_compat.stored_checksum_matches(
        diagnosis.five_tone_read_model_json,
        diagnosis.five_tone_read_model_checksum,
    ):
        raise Agent3NotReady(
            "FIVE_TONE_SNAPSHOT_INVALID",
            "五音调适解析数据校验失败。",
        )
    try:
        # Version-aware: a pre-Phase-1A snapshot is resolved by the row-aware
        # compatibility resolver; a personalized legacy read model takes its
        # weights from this row's own persisted tone authority, never a guess.
        read_model, _compatibility = legacy_mode_compat.resolve_read_model_payload(
            diagnosis.five_tone_read_model_json,
            LegacyProvenance(
                source="diagnosis",
                diagnosis_status=diagnosis.status,
                abstain_reason=diagnosis.abstain_reason,
            ),
            tone_weights=_persisted_tone_weights(diagnosis),
        )
    except legacy_mode_compat.LegacyModeUnclassifiedError as error:
        raise Agent3NotReady(
            error.error_code,
            error.safe_message,
        ) from error
    except (TypeError, ValueError) as error:
        raise Agent3NotReady(
            "FIVE_TONE_SNAPSHOT_INVALID",
            "五音调适解析数据无效。",
        ) from error
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
        spec, _compatibility = legacy_mode_compat.resolve_generation_spec_payload(
            diagnosis.generation_spec_json,
            LegacyProvenance(
                source="diagnosis",
                diagnosis_status=diagnosis.status,
                abstain_reason=diagnosis.abstain_reason,
            ),
        )
        return spec
    except legacy_mode_compat.LegacyModeUnclassifiedError as error:
        raise Agent3NotReady(
            error.error_code,
            error.safe_message,
        ) from error
    except (TypeError, ValueError) as error:
        raise Agent3NotReady(
            "GENERATION_SPEC_INVALID",
            "音乐生成参数无效。",
        ) from error


def build_prescription_spec(
    db: Session,
    diagnosis: DiagnosisRun,
    user_goal: UserGoalV31 | None,
    *,
    dominance_decision: object | None = None,
) -> GenerationSpec:
    """Build the transport spec from the persisted authoritative decision.

    Sprint 6 Phase 1B: this adapter is no longer a decision authority. It
    consumes the decision the diagnosis run already persisted
    (``five_tone_analysis_read_model_v3.3`` audit) or an explicitly supplied
    authoritative decision, and fails closed when neither exists — it never
    re-derives a mode from organ weights, a primary tone or an argmax.
    """

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
    if dominance_decision is None:
        session_row = db.get(SessionModel, diagnosis.session_row_id)
        if session_row is None:
            raise Agent3NotReady("ASSESSMENT_NOT_CONFIRMED", "评估结果尚未确认。")
        read_model = load_current_five_tone_read_model(db, diagnosis, session_row)
        dominance_decision = getattr(read_model, "dominance_decision", None)
    if dominance_decision is None:
        raise Agent3NotReady(
            "DOMINANCE_DECISION_NOT_PERSISTED",
            "该记录没有后端权威主导度决策，已停止重新推断音乐模式。",
        )
    mode = getattr(dominance_decision, "regulation_mode", None) or (
        dominance_decision.get("regulation_mode")
        if isinstance(dominance_decision, Mapping)
        else None
    )
    if mode in {"personalized_five_tone", "integrated_regulation"} and (
        organ_profile.get("status") != "available" or not organ_profile.get("weights")
    ):
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
            organ_weights=organ_profile.get("weights") or {},
            supporting_evidence_refs=evidence_refs,
            mapping=mapping,
            dominance_decision=dominance_decision,
        )
        internal = build_generation_spec_v31(
            profile=profile,
            parameter_rules=rules,
            user_goal=user_goal,
        )
    except Agent3Blocked as error:
        code = error.error_code or "AGENT3_NOT_READY"
        raise Agent3NotReady(code, "五音处方规则尚未准备完成。") from error
    return to_transport_spec(internal, tone_profile=profile)
