from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .diagnosis_v2 import allows_deterministic_assessment_fallback
from .prompt_engine import PromptEngine
from .real_agents import MVP_SYNDROMES


_DISCLAIMER = "本结果仅用于音乐调养参考，不构成医学诊断。"
_TONE_CONFIG = {
    "jiao": {"tone_name": "角调", "bpm": 68, "instruments": ["古筝", "古琴"]},
    "zhi": {"tone_name": "徵调", "bpm": 70, "instruments": ["琵琶", "古琴"]},
    "gong": {"tone_name": "宫调", "bpm": 62, "instruments": ["编钟", "古琴"]},
    "shang": {"tone_name": "商调", "bpm": 66, "instruments": ["二胡", "洞箫"]},
    "yu": {"tone_name": "羽调", "bpm": 58, "instruments": ["箫", "古琴"]},
}

# 辨证倾向不明确时的「情绪维度 → 五音」兜底映射（与 MVP 证型的五行/五音保持一致）。
# 13 个冻结维度均已在评估快照中归一化为 0-100（分数越高，困扰越明显）。
_DIMENSION_TO_TONE = {
    "tension_worry": "jiao",       # 紧张担忧 -> 肝/木 -> 角调
    "overthinking": "gong",        # 反复思虑 -> 脾/土 -> 宫调
    "irritability_anger": "jiao",  # 烦躁易怒 -> 肝/木 -> 角调
    "fear_unease": "yu",           # 不安恐惧 -> 肾/水 -> 羽调
    "low_mood": "shang",           # 情绪低落 -> 肺/金 -> 商调
    "interest_loss": "gong",       # 兴趣减退 -> 心脾 -> 宫调
    "calm_wellbeing": "jiao",      # 平静不足（反向计分）-> 肝/木 -> 角调
    "emotional_recovery": "gong",  # 情绪恢复缓慢 -> 脾/土 -> 宫调
    "sleep_disturbance": "zhi",    # 睡眠困扰 -> 心/火 -> 徵调
    "unrefreshing_sleep": "yu",    # 睡眠不解乏 -> 肾/水 -> 羽调
    "low_energy": "gong",          # 精力不足 -> 脾/土 -> 宫调
    "appetite_change": "gong",     # 食欲变化 -> 脾/土 -> 宫调
    "daily_impact": "shang",       # 日常受影响 -> 肺/金 -> 商调
}
_DIMENSION_LABELS = {
    "tension_worry": "紧张担忧",
    "overthinking": "反复思虑",
    "irritability_anger": "烦躁易怒",
    "fear_unease": "不安恐惧",
    "low_mood": "情绪低落",
    "interest_loss": "兴趣减退",
    "calm_wellbeing": "平静状态不足",
    "emotional_recovery": "情绪恢复缓慢",
    "sleep_disturbance": "睡眠困扰",
    "unrefreshing_sleep": "睡眠不解乏",
    "low_energy": "精力不足",
    "appetite_change": "食欲变化",
    "daily_impact": "日常受影响",
}
_WELLNESS_TONE_ID = "gong"  # 状态平稳时使用平和安神的宫调。

_PRESCRIPTION_MODES = ("syndrome_based", "candidate_blend", "emotion_based", "wellness")

# 处方「特异性」——处方有多精细（按证型 > 融合 > 情绪 > 平补）。这是分类标签，
# 不是数值置信度，避免制造无数据来源的精确感。
_RX_SPECIFICITY = {
    "syndrome_based": "high",
    "candidate_blend": "medium",
    "emotion_based": "conservative",
    "wellness": "wellness",
}

# 非临床「状态平稳」启发式阈值：仅用于在 Diagnosis 已 abstain 时选择处方特异性
# （wellness vs emotion_based），不是医学判定。分数是问卷归一化的 0-100 维度分
# （raw 0-4 × 25）。
# - 达到 _NON_CLINICAL_STABLE_ELEVATED_SCORE（50 = 中等及以上）即「有明显负向状态」。
# - 达到 _NON_CLINICAL_STABLE_MILD_SCORE（25 = 轻度）但未到中度视为「轻度负向状态」。
_NON_CLINICAL_STABLE_ELEVATED_SCORE = 50.0
_NON_CLINICAL_STABLE_MILD_SCORE = 25.0
# 允许的「轻度负向维度」上限：超过该数量即不再视为「平稳」，改用情绪定向调。
_NON_CLINICAL_STABLE_MAX_MILD_DIMENSIONS = 1


def _recommendation_confidence(
    mode: str,
    evidence_coverage: float | None,
) -> dict[str, object]:
    """Derive recommendation confidence from real evidence coverage.

    This describes how well the prescription *basis* is supported — NOT clinical
    confidence, and NOT "how certain the diagnosis is". ``score`` is the
    assessment's ``evidence_coverage_score`` verbatim (rounded); when no
    assessment is available (legacy V2.0 path) it is ``None`` rather than a
    fabricated number. ``specificity`` is a coarse categorical label for the
    prescription's granularity.
    """
    if evidence_coverage is None:
        return {
            "level": "medium",
            "score": None,
            "basis": "unavailable",
            "specificity": _RX_SPECIFICITY[mode],
        }
    score = round(float(evidence_coverage), 2)
    if score >= 0.8:
        level = "high"
    elif score >= 0.5:
        level = "medium"
    else:
        level = "low"
    return {
        "level": level,
        "score": score,
        "basis": "evidence_coverage",
        "specificity": _RX_SPECIFICITY[mode],
    }


def _coverage_score(assessment: object) -> float | None:
    if not isinstance(assessment, Mapping):
        return None
    coverage = assessment.get("evidence_coverage_score")
    return float(coverage) if isinstance(coverage, (int, float)) else None


def run_prescription_v2(
    diagnosis: Mapping[str, object],
    knowledge_store: object | None = None,
    assessment: Mapping[str, object] | None = None,
) -> dict:
    """Return a music prescription for a safe, supported tendency.

    Two independent paths share one entry point:

    * ``assessment is None`` (legacy V2.0 path) keeps the original contract:
      ``_withheld_reason`` still withholds on degraded/low-confidence/conflict/
      unknown-tendency, and a clear primary tendency maps to one tone.
    * ``assessment`` is provided (V2.1 evidence-first path): the prescription
      internally selects a ``prescription_mode`` among ``syndrome_based`` /
      ``candidate_blend`` / ``emotion_based`` / ``wellness``.  Only safety and
      genuine information insufficiency withhold — a diagnosis abstention that
      is merely "no local multidimensional candidate" no longer blocks music.
    """
    diagnosis_data = dict(diagnosis)
    if assessment is not None:
        return _prescribe_v21(diagnosis_data, dict(assessment), knowledge_store)

    withheld_reason = _withheld_reason(diagnosis_data)
    if withheld_reason is not None:
        return _withheld(withheld_reason)

    primary = diagnosis_data["primary_tendency"]
    assert isinstance(primary, Mapping)
    tendency_id = primary["id"]
    assert isinstance(tendency_id, str)
    syndrome = MVP_SYNDROMES[tendency_id]
    tone_id = str(syndrome["tone_id"])
    return _build_prescription(
        tone_id=tone_id,
        query_text=str(syndrome["name"]),
        first_reason=f"辅助辨证倾向 {tendency_id} 映射为{_TONE_CONFIG[tone_id]['tone_name']}音乐参数。",
        knowledge_store=knowledge_store,
        mode="syndrome_based",
        source_basis="辨证倾向明确，按证型映射五音。",
    )


def select_prescription_mode(
    diagnosis: Mapping[str, object],
    assessment: Mapping[str, object] | None = None,
) -> str:
    """Deterministically pick the prescription granularity for a V2.1 diagnosis.

    Agent② decides whether the syndrome is clear; Agent③ only decides how to turn
    that conclusion into a music prescription.

    * Diagnosis gave an explicit, valid ``primary_tendency`` → ``syndrome_based``.
      A secondary ``candidate_tendencies`` list must NOT downgrade an explicit
      primary: the primary is Agent②'s authoritative conclusion.
    * Diagnosis is not abstained but offers no primary yet multiple valid
      candidates → ``candidate_blend``. This is a defensive compatibility path
      only — the current Diagnosis V2.1 contract never emits "not abstained but
      no primary" (when ``abstained == False``, ``primary_tendency`` is always
      ``candidate_tendencies[0]``).
    * Diagnosis abstained with no candidate but the assessment still carries
      meaningful state data → ``wellness`` (uniformly low) or ``emotion_based``
      (some elevated dimension).

    Safety / true insufficiency are handled by the caller
    (``_v21_withhold_reason``), not by this selector. An empty dimension set
    should already have been withheld by the caller; the ``emotion_based`` branch
    below is only a defensive default for direct callers.
    """
    if not diagnosis.get("abstained"):
        primary = diagnosis.get("primary_tendency")
        if isinstance(primary, Mapping) and primary.get("id") in MVP_SYNDROMES:
            return "syndrome_based"
        if len(_valid_candidates(diagnosis.get("candidate_tendencies"))) >= 2:
            return "candidate_blend"

    dimensions = _dimension_scores(assessment)
    if _is_stable_state(dimensions):
        return "wellness"
    return "emotion_based"


def _prescribe_v21(
    diagnosis: Mapping[str, object],
    assessment: Mapping[str, object],
    knowledge_store: object | None,
) -> dict:
    withhold_reason = _v21_withhold_reason(diagnosis, assessment)
    if withhold_reason is not None:
        return _withheld(withhold_reason)

    evidence_coverage = _coverage_score(assessment)
    mode = select_prescription_mode(diagnosis, assessment)
    if mode == "syndrome_based":
        primary = diagnosis["primary_tendency"]
        assert isinstance(primary, Mapping)
        tendency_id = str(primary["id"])
        syndrome = MVP_SYNDROMES[tendency_id]
        tone_id = str(syndrome["tone_id"])
        return _build_prescription(
            tone_id=tone_id,
            query_text=str(syndrome["name"]),
            first_reason=f"辅助辨证倾向 {tendency_id} 映射为{_TONE_CONFIG[tone_id]['tone_name']}音乐参数。",
            knowledge_store=knowledge_store,
            mode="syndrome_based",
            source_basis="辨证倾向明确，按证型映射五音。",
            evidence_coverage=evidence_coverage,
        )

    if mode == "candidate_blend":
        candidates = _valid_candidates(diagnosis.get("candidate_tendencies"))
        weights = _candidate_tone_weights(candidates)
        if weights:
            top_tone_id = next(iter(weights))
            return _build_prescription(
                tone_id=top_tone_id,
                query_text=_TONE_CONFIG[top_tone_id]["tone_name"],
                first_reason="存在多个相近的辅助辨证倾向，按权重融合五音参数。",
                knowledge_store=knowledge_store,
                mode="candidate_blend",
                source_basis="存在多个相近的辅助辨证倾向，按权重融合五音。",
                evidence_coverage=evidence_coverage,
                extra={"tone_weights": weights},
            )
        # Defensive: empty weights means there were no usable candidates. This
        # must not happen via select_prescription_mode (which requires at least
        # two positive-score candidates), but degrade safely to the same
        # emotion/wellness heuristic rather than crashing on next(iter({})).
        mode = (
            "wellness"
            if _is_stable_state(_dimension_scores(assessment))
            else "emotion_based"
        )

    if mode == "wellness":
        return _build_prescription(
            tone_id=_WELLNESS_TONE_ID,
            query_text=_TONE_CONFIG[_WELLNESS_TONE_ID]["tone_name"],
            first_reason="当前状态整体平稳，选用平和安神的宫调音乐参数。",
            knowledge_store=knowledge_store,
            mode="wellness",
            source_basis="状态整体平稳，选用平和安神的宫调。",
            evidence_coverage=evidence_coverage,
        )

    # emotion_based
    dimensions = _dimension_scores(assessment)
    tone_id, dimension = _dominant_emotion_tone(dimensions)
    tone = _TONE_CONFIG[tone_id]
    label = _DIMENSION_LABELS.get(dimension, "当前状态") if dimension else "当前状态"
    return _build_prescription(
        tone_id=tone_id,
        query_text=tone["tone_name"],
        first_reason=f"辨证倾向尚不明确，按主导情绪维度（{label}）映射为{tone['tone_name']}音乐参数。",
        knowledge_store=knowledge_store,
        mode="emotion_based",
        source_basis="辨证倾向尚不明确，按主导情绪维度映射五音。",
        evidence_coverage=evidence_coverage,
        extra={"dominant_dimension": dimension} if dimension else None,
    )


def _v21_withhold_reason(
    diagnosis: Mapping[str, object],
    assessment: Mapping[str, object],
) -> str | None:
    if (
        diagnosis.get("status") == "blocked_safety"
        or assessment.get("status") == "blocked_safety"
    ):
        return "SAFETY_BLOCKED"
    abstain_reason = diagnosis.get("abstain_reason")
    if abstain_reason == "SAFETY_BLOCKED":
        return "SAFETY_BLOCKED"
    if abstain_reason == "ASSESSMENT_NOT_CONFIRMED":
        return "ASSESSMENT_NOT_CONFIRMED"
    if abstain_reason == "UNRESOLVED_MAJOR_CONFLICT":
        return "UNRESOLVED_MAJOR_CONFLICT"
    if _is_truly_insufficient(assessment):
        return "INSUFFICIENT_EVIDENCE"
    # Abstained with no state data at all → "no data" is not a stable state;
    # treat it as genuine insufficiency rather than fabricating a wellness tone.
    if diagnosis.get("abstained") and not _dimension_scores(assessment):
        return "INSUFFICIENT_EVIDENCE"
    return None


def _is_truly_insufficient(assessment: Mapping[str, object]) -> bool:
    coverage = assessment.get("evidence_coverage_score")
    if isinstance(coverage, (int, float)) and float(coverage) < 0.5:
        return True
    missing = assessment.get("missing_information")
    if isinstance(missing, list):
        return any(
            isinstance(item, Mapping) and item.get("severity") in {"critical", "important"}
            for item in missing
        )
    return False


def _withheld_reason(diagnosis: Mapping[str, object]) -> str | None:
    if diagnosis.get("status") == "blocked_safety":
        return "SAFETY_BLOCKED"
    if diagnosis.get("status") == "degraded":
        return "ASSESSMENT_DEGRADED"
    if (
        diagnosis.get("assessment_status") == "degraded"
        and not allows_deterministic_assessment_fallback(
            diagnosis.get("assessment_degradation")
        )
    ):
        return "ASSESSMENT_DEGRADED"
    confidence = diagnosis.get("confidence")
    if not isinstance(confidence, Mapping) or confidence.get("level") == "low":
        return "LOW_CONFIDENCE"
    score = confidence.get("score")
    if not isinstance(score, (int, float)) or score < 0.4:
        return "LOW_CONFIDENCE"
    conflicts = diagnosis.get("conflicts")
    if isinstance(conflicts, list) and len(conflicts) >= 2:
        return "SEVERE_CONFLICTS"
    primary = diagnosis.get("primary_tendency")
    if not isinstance(primary, Mapping) or primary.get("id") not in MVP_SYNDROMES:
        return "UNKNOWN_TENDENCY"
    return None


def _withheld(reason: str) -> dict:
    return {
        "agent_id": "prescription_agent",
        "status": "blocked_safety" if reason == "SAFETY_BLOCKED" else "degraded",
        "action": "withhold_music_recommendation",
        "generation_mode": "withheld",
        "warnings": ["当前信息不适合输出普通音乐调养建议。"],
        "withheld_reason": reason,
        "disclaimer": _DISCLAIMER,
    }


def _build_prescription(
    *,
    tone_id: str,
    query_text: str,
    first_reason: str,
    knowledge_store: object | None,
    mode: str,
    source_basis: str,
    evidence_coverage: float | None = None,
    extra: dict[str, object] | None = None,
) -> dict:
    tone = _TONE_CONFIG[tone_id]
    prompt = _render_prompt(tone)
    evidence, knowledge_degradation, warnings = _knowledge_evidence(
        knowledge_store,
        query_text,
    )
    result: dict[str, object] = {
        "agent_id": "prescription_agent",
        "status": "success",
        "generation_mode": "matched",
        "prescription_mode": mode,
        "source_basis": source_basis,
        "recommendation_specificity": _RX_SPECIFICITY[mode],
        "recommendation_confidence": _recommendation_confidence(
            mode,
            evidence_coverage,
        ),
        "music_feature": {
            "tone_id": tone_id,
            "tone_name": tone["tone_name"],
            "bpm": tone["bpm"],
            "duration_minutes": 15,
            "instruments": tone["instruments"],
        },
        "prompt_template": {
            "template_id": prompt.template_id,
            "template_version": prompt.template_version,
            "text": prompt.text,
        },
        "recommendation_reasons": [
            first_reason,
            "已结合知识库检索证据。" if evidence else "已使用审核本地规则。",
        ],
        "parameter_sources": {
            "tone_id": "reviewed_local_rule",
            "bpm": "reviewed_local_rule",
            "duration_minutes": "reviewed_local_rule",
            "instruments": "reviewed_local_rule",
            "prompt": "reviewed_local_rule",
        },
        "evidence": evidence,
        "warnings": warnings,
        "knowledge_degradation": knowledge_degradation,
        "disclaimer": _DISCLAIMER,
    }
    if extra:
        result.update(extra)
    return result


def _render_prompt(tone: Mapping[str, object]) -> Any:
    return PromptEngine(Path(__file__).resolve().parents[2] / "prompt" / "v1").render(
        "CN_V1",
        {
            "duration": 15,
            "bpm": tone["bpm"],
            "tone": tone["tone_name"],
            "style": "传统五声音阶疗愈音乐",
        },
    )


def _knowledge_evidence(
    knowledge_store: object | None,
    query_text: str,
) -> tuple[list[dict[str, object]], dict[str, object], list[str]]:
    if knowledge_store is None:
        return (
            [],
            {"active": True, "reason_codes": ["KNOWLEDGE_STORE_NOT_CONFIGURED"]},
            ["知识库未配置，已使用审核本地规则。"],
        )
    try:
        query = getattr(knowledge_store, "query")
        hits = query(query_text, limit=3)
        evidence = [
            {
                "text": hit.text,
                "metadata": dict(hit.metadata),
                "distance": hit.distance,
            }
            for hit in hits
        ]
    except Exception:
        return (
            [],
            {"active": True, "reason_codes": ["KNOWLEDGE_RETRIEVAL_FAILED"]},
            ["知识检索失败，已使用审核本地规则。"],
        )
    return evidence, {"active": False, "reason_codes": []}, []


def _dimension_scores(assessment: object) -> dict[str, float]:
    if not isinstance(assessment, Mapping):
        return {}
    emotion_profile = assessment.get("emotion_profile")
    if not isinstance(emotion_profile, Mapping):
        return {}
    raw = emotion_profile.get("dimension_scores")
    if not isinstance(raw, Mapping):
        return {}
    return {str(key): _score(value) for key, value in raw.items()}


def _is_stable_state(dimensions: Mapping[str, float]) -> bool:
    if not dimensions:
        # "No data" is not a stable state — the caller withholds instead.
        return False
    scores = list(dimensions.values())
    if any(score >= _NON_CLINICAL_STABLE_ELEVATED_SCORE for score in scores):
        return False
    mild_count = sum(
        1
        for score in scores
        if _NON_CLINICAL_STABLE_MILD_SCORE
        <= score
        < _NON_CLINICAL_STABLE_ELEVATED_SCORE
    )
    return mild_count <= _NON_CLINICAL_STABLE_MAX_MILD_DIMENSIONS


def _dominant_emotion_tone(dimensions: Mapping[str, float]) -> tuple[str, str | None]:
    if not dimensions:
        return _WELLNESS_TONE_ID, None
    dimension = max(dimensions, key=lambda key: dimensions[key])
    if dimensions[dimension] <= 0:
        return _WELLNESS_TONE_ID, None
    return _DIMENSION_TO_TONE.get(dimension, _WELLNESS_TONE_ID), dimension


def _candidate_tone_weights(candidates: list[dict[str, object]]) -> dict[str, float]:
    raw: dict[str, float] = {}
    for candidate in candidates[:3]:
        syndrome = MVP_SYNDROMES.get(candidate.get("id"))
        if not isinstance(syndrome, Mapping):
            continue
        tone_id = str(syndrome.get("tone_id", _WELLNESS_TONE_ID))
        raw[tone_id] = raw.get(tone_id, 0.0) + max(0.0, _score(candidate.get("score")))
    total = sum(raw.values())
    if total <= 0:
        # No valid candidate — do NOT fabricate a gong fallback. A candidate_blend
        # with zero valid candidates is an error the caller must not reach.
        return {}
    return {
        tone_id: round(weight / total, 4)
        for tone_id, weight in sorted(raw.items(), key=lambda item: (-item[1], item[0]))
    }


def _valid_candidates(value: object) -> list[dict[str, object]]:
    """Return only candidates that carry a real, usable tendency.

    A candidate is usable for blending only when all of:

    * its ``id`` is a recognised syndrome,
    * its ``score`` is a genuine number (a ``bool`` is not a score),
    * its ``score`` is strictly positive.

    This excludes zero scores, missing/invalid scores, and fabricated candidates.
    It does NOT impose any medical "how high is enough" threshold — that decision
    belongs to Agent②, whose output we reuse as-is (including any
    ``supporting_evidence_ids`` fields, which are preserved untouched and never
    invented here).
    """
    valid: list[dict[str, object]] = []
    for candidate in _mapping_list(value):
        if candidate.get("id") not in MVP_SYNDROMES:
            continue
        score = candidate.get("score")
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            continue
        if float(score) <= 0:
            continue
        valid.append(candidate)
    return valid


def _mapping_list(value: object) -> list[dict[str, object]]:
    return [dict(item) for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []


def _score(value: object) -> float:
    return float(value) if isinstance(value, (int, float)) else 0.0
