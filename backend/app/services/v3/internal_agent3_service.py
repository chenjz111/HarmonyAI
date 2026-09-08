"""Server-owned Agent3 adapter for the V3.1 prescription boundary."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping

from sqlalchemy.orm import Session

from backend.ai_engine.v3.agent3 import (
    Agent3Blocked,
    GenerationSpecV31,
    build_generation_spec_v31,
    build_tone_profile_v31,
)
from backend.app.models.v3.assessment import AssessmentRevisionV3, FactEvidence
from backend.app.models.v3.diagnosis import DiagnosisRun
from backend.app.schemas.v3.flow_v31 import UserGoalV31
from backend.app.schemas.v3.prescription import (
    GenerationFallbackPolicy,
    GenerationSpec,
    GenerationStructure,
)
from backend.app.services.v3.knowledge_assets import load_five_tone_mapping


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
    if not rules_path:
        raise Agent3NotReady(
            "MUSIC_PARAMETER_ASSET_NOT_CONFIGURED",
            "音乐参数规则资产尚未配置。",
        )
    try:
        rules = json.loads(Path(rules_path).read_text(encoding="utf-8"))
        mapping = load_five_tone_mapping()
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


def _transport_spec(
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
    return _transport_spec(internal, tone_profile=profile)
