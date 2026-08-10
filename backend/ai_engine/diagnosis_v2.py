from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import json
from typing import Any

from .providers import JsonLLMProvider
from .real_agents import MVP_SYNDROMES


_DISCLAIMER = "本结果仅用于音乐调养参考，不构成医学诊断。"
_LOCAL_RULES = {
    "syd_001": ("tension_worry", "irritability_anger"),
    "syd_002": ("tension_worry", "overthinking", "low_mood"),
    "syd_003": ("irritability_anger", "sleep_disturbance"),
    "syd_004": ("overthinking", "low_energy"),
    "syd_005": ("appetite_change", "low_energy"),
    "syd_006": ("low_mood", "daily_impact"),
    "syd_007": ("fear_unease", "low_energy"),
    "syd_008": ("sleep_disturbance", "fear_unease"),
}


def run_diagnosis_v2(
    assessment: Mapping[str, object],
    llm: JsonLLMProvider | None = None,
) -> dict:
    """Map an Assessment V2 envelope to a non-diagnostic assistive tendency."""
    assessment_data = dict(assessment)
    sources = _mapping_list(assessment_data.get("sources_used"))
    conflicts = _mapping_list(assessment_data.get("conflicts"))
    missing = _string_list(assessment_data.get("missing_information"))
    assessment_degradation = _mapping_or_default(
        assessment_data.get("degradation"),
        {"active": False, "reason_codes": []},
    )

    if assessment_data.get("status") == "blocked_safety":
        return _result(
            status="blocked_safety",
            primary_tendency=None,
            secondary_tendencies=[],
            confidence={"level": "low", "score": 0.0},
            evidence_summary=[],
            conflicts=conflicts,
            warnings=["检测到安全风险，已停止普通音乐调养建议。"],
            assessment=assessment_data,
            sources=sources,
            missing=missing,
            assessment_degradation=assessment_degradation,
            degradation={"active": True, "reason_codes": ["SAFETY_BLOCKED"]},
        )

    emotion_profile = _mapping_or_default(
        assessment_data.get("emotion_profile"),
        {},
    )
    dimensions = emotion_profile.get(
        "dimension_scores",
        assessment_data.get("dimensions"),
    )
    candidates = _local_candidates(dimensions)
    primary = candidates[0] if candidates else None
    secondary = candidates[1:]
    if primary is None:
        return _result(
            status="degraded",
            primary_tendency=None,
            secondary_tendencies=[],
            confidence={"level": "low", "score": 0.2},
            evidence_summary=[],
            conflicts=conflicts,
            warnings=["信息不足：至少需要两个独立维度支持辅助辨证倾向。"],
            assessment=assessment_data,
            sources=sources,
            missing=missing,
            assessment_degradation=assessment_degradation,
            degradation={
                "active": True,
                "reason_codes": ["INSUFFICIENT_INDEPENDENT_DIMENSIONS"],
            },
        )

    warnings: list[str] = []
    reason_codes: list[str] = []
    selected = primary
    if llm is not None:
        model_selection, warning, reason_code = _llm_selection(
            llm,
            assessment_data,
        )
        if warning is not None:
            warnings.append(warning)
            reason_codes.append(reason_code)
        elif model_selection is not None:
            model_candidate = _candidate_for_id(model_selection, candidates)
            if model_candidate is None:
                warnings.append(
                    "LLM建议未通过本地多维证据门槛，已保留本地候选。"
                )
                reason_codes.append("LLM_UNSUPPORTED_TENDENCY")
            else:
                selected = model_candidate
                primary = selected
                secondary = [
                    candidate
                    for candidate in candidates
                    if candidate["id"] != selected["id"]
                ]

    if assessment_data.get("status") == "degraded":
        reason_codes.append("ASSESSMENT_DEGRADED")
    if conflicts:
        reason_codes.append("SOURCE_CONFLICT")
    reason_codes = _unique(reason_codes)
    status = "degraded" if reason_codes else "success"
    confidence = (
        {"level": "low", "score": 0.3}
        if status == "degraded"
        else {"level": "high", "score": 0.85}
    )
    evidence_summary = [
        _evidence_summary(selected),
        *[_evidence_summary(candidate) for candidate in secondary],
    ]
    return _result(
        status=status,
        primary_tendency=selected,
        secondary_tendencies=secondary,
        confidence=confidence,
        evidence_summary=evidence_summary,
        conflicts=conflicts,
        warnings=warnings,
        assessment=assessment_data,
        sources=sources,
        missing=missing,
        assessment_degradation=assessment_degradation,
        degradation={"active": bool(reason_codes), "reason_codes": reason_codes},
    )


def _local_candidates(value: object) -> list[dict[str, object]]:
    dimensions = value if isinstance(value, Mapping) else {}
    candidates = []
    for tendency_id, rule_dimensions in _LOCAL_RULES.items():
        supported = [
            dimension
            for dimension in rule_dimensions
            if _score(dimensions.get(dimension)) > 0
        ]
        if len(supported) < 2:
            continue
        score = sum(_score(dimensions.get(dimension)) for dimension in supported) / len(
            supported
        )
        candidates.append(_tendency(tendency_id, score, supported))
    return sorted(candidates, key=lambda item: (-float(item["score"]), str(item["id"])))


def _tendency(
    tendency_id: str,
    score: float,
    supporting_dimensions: list[str],
) -> dict[str, object]:
    syndrome = MVP_SYNDROMES[tendency_id]
    return {
        "id": tendency_id,
        "label": syndrome["name"],
        "score": score,
        "element": syndrome["element"],
        "organs": str(syndrome["organ"]).split("、"),
        "supporting_dimensions": supporting_dimensions,
    }


def _candidate_for_id(
    tendency_id: str,
    candidates: list[dict[str, object]],
) -> dict[str, object] | None:
    return next(
        (candidate for candidate in candidates if candidate["id"] == tendency_id),
        None,
    )


def _llm_selection(
    llm: JsonLLMProvider,
    assessment: Mapping[str, object],
) -> tuple[str | None, str | None, str]:
    emotion_profile = _mapping_or_default(
        assessment.get("emotion_profile"),
        {},
    )
    dimensions = _mapping_or_default(
        emotion_profile.get("dimension_scores"),
        assessment.get("dimensions", {}),
    )
    try:
        response = llm.complete_json(
            "你是辅助辨证倾向建议助手。只返回JSON对象，必须且只能包含tendency_id和confidence；"
            "tendency_id只能从给定白名单选择，不得输出医学诊断或治疗结论。",
            json.dumps(
                {
                    "dimensions": dimensions,
                    "allowed_tendency_ids": list(MVP_SYNDROMES),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        )
    except json.JSONDecodeError:
        return None, "LLM返回无效JSON，已使用本地规则。", "LLM_INVALID_JSON"
    except Exception:
        return None, "LLM不可用，已使用本地规则。", "LLM_UNAVAILABLE"

    if not isinstance(response, Mapping):
        return None, "LLM返回无效结构，已使用本地规则。", "LLM_INVALID_JSON"
    if set(response) != {"tendency_id", "confidence"}:
        return None, "LLM缺少必填字段，已使用本地规则。", "LLM_MISSING_FIELDS"
    tendency_id = response.get("tendency_id")
    confidence = response.get("confidence")
    if not isinstance(tendency_id, str) or not isinstance(confidence, (int, float)):
        return None, "LLM缺少必填字段，已使用本地规则。", "LLM_MISSING_FIELDS"
    if tendency_id not in MVP_SYNDROMES:
        return None, "LLM建议了未授权倾向，已使用本地规则。", "LLM_UNKNOWN_TENDENCY"
    return tendency_id, None, ""


def _result(
    *,
    status: str,
    primary_tendency: dict[str, object] | None,
    secondary_tendencies: list[dict[str, object]],
    confidence: dict[str, object],
    evidence_summary: list[dict[str, object]],
    conflicts: list[dict[str, object]],
    warnings: list[str],
    assessment: Mapping[str, object],
    sources: list[dict[str, object]],
    missing: list[str],
    assessment_degradation: dict[str, object],
    degradation: dict[str, object],
) -> dict:
    return {
        "status": status,
        "presentation": {"title": "辅助辨证倾向"},
        "primary_tendency": deepcopy(primary_tendency),
        "secondary_tendencies": deepcopy(secondary_tendencies),
        "confidence": confidence,
        "evidence_summary": evidence_summary,
        "conflicts": deepcopy(conflicts),
        "warnings": list(warnings),
        "information_completeness": {
            "level": "complete" if not missing else "partial",
            "missing": list(missing),
        },
        "assessment_status": assessment.get("status"),
        "assessment_degradation": deepcopy(assessment_degradation),
        "assessment_sources": deepcopy(sources),
        "degradation": deepcopy(degradation),
        "disclaimer": _DISCLAIMER,
    }


def _evidence_summary(tendency: Mapping[str, object]) -> dict[str, object]:
    dimensions = list(tendency["supporting_dimensions"])
    return {
        "tendency_id": tendency["id"],
        "dimensions": dimensions,
        "sources": [
            {
                "tension_worry": "questionnaire:q02",
                "overthinking": "questionnaire:q03",
                "irritability_anger": "questionnaire:q04",
                "low_mood": "questionnaire:q05",
                "interest_loss": "questionnaire:q06",
                "fear_unease": "questionnaire:q07",
                "sleep_disturbance": "questionnaire:q08",
                "low_energy": "questionnaire:q09",
                "appetite_change": "questionnaire:q10",
                "daily_impact": "questionnaire:q11",
            }[dimension]
            for dimension in dimensions
        ],
    }


def _score(value: object) -> float:
    return float(value) if isinstance(value, (int, float)) else 0.0


def _mapping_list(value: object) -> list[dict[str, object]]:
    return [dict(item) for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []


def _string_list(value: object) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _mapping_or_default(value: object, default: dict[str, object]) -> dict[str, object]:
    return dict(value) if isinstance(value, Mapping) else default


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def run_diagnosis_v21(
    assessment: Mapping[str, object],
    *,
    provider: JsonLLMProvider | None = None,
) -> dict[str, object]:
    """Produce evidence-grounded, non-diagnostic candidates for Assessment V2.1."""
    del provider
    assessment_data = dict(assessment)
    if assessment_data.get("status") == "blocked_safety":
        return _v21_diagnosis_result(
            assessment_data,
            status="blocked_safety",
            candidates=[],
            abstained=True,
            abstain_reason="SAFETY_BLOCKED",
            reason_codes=["SAFETY_BLOCKED"],
        )
    if assessment_data.get("requires_user_confirmation") is not False:
        return _v21_diagnosis_result(
            assessment_data,
            status="degraded",
            candidates=[],
            abstained=True,
            abstain_reason="ASSESSMENT_NOT_CONFIRMED",
            reason_codes=["ASSESSMENT_NOT_CONFIRMED"],
        )

    conflicts = _mapping_list(assessment_data.get("conflicts"))
    if any(
        conflict.get("severity") == "major"
        and conflict.get("resolution") != "resolved_by_user"
        for conflict in conflicts
    ):
        return _v21_diagnosis_result(
            assessment_data,
            status="degraded",
            candidates=[],
            abstained=True,
            abstain_reason="UNRESOLVED_MAJOR_CONFLICT",
            reason_codes=["UNRESOLVED_MAJOR_CONFLICT"],
        )

    emotion_profile = _mapping_or_default(assessment_data.get("emotion_profile"), {})
    dimensions = _mapping_or_default(emotion_profile.get("dimension_scores"), {})
    evidence_items = _mapping_list(assessment_data.get("evidence_items"))
    candidates: list[dict[str, object]] = []
    for tendency_id, rule_dimensions in _LOCAL_RULES.items():
        supported_dimensions = [
            dimension
            for dimension in rule_dimensions
            if _score(dimensions.get(dimension)) > 0
        ]
        if len(supported_dimensions) < 2:
            continue
        base = _tendency(
            tendency_id,
            sum(_score(dimensions.get(dimension)) for dimension in supported_dimensions)
            / len(supported_dimensions),
            supported_dimensions,
        )
        supporting_ids = [
            str(item["evidence_id"])
            for item in evidence_items
            if item.get("label") in supported_dimensions
            and _score(item.get("value")) > 0
            and isinstance(item.get("evidence_id"), str)
        ]
        contradicting_ids = [
            str(item["evidence_id"])
            for item in evidence_items
            if item.get("label") in rule_dimensions
            and (
                _score(item.get("value")) == 0
                or item.get("polarity") == "absent"
                or item.get("negated") is True
            )
            and isinstance(item.get("evidence_id"), str)
        ]
        candidates.append(
            {
                **base,
                "supporting_evidence_ids": _unique(supporting_ids),
                "contradicting_evidence_ids": _unique(contradicting_ids),
                "reasoning_summary": "由多个独立维度和可定位证据共同支持。",
            }
        )

    candidates.sort(key=lambda item: (-float(item["score"]), str(item["id"])))
    if not candidates:
        return _v21_diagnosis_result(
            assessment_data,
            status="degraded",
            candidates=[],
            abstained=True,
            abstain_reason="INSUFFICIENT_EVIDENCE",
            reason_codes=["INSUFFICIENT_EVIDENCE"],
        )
    return _v21_diagnosis_result(
        assessment_data,
        status="success",
        candidates=candidates,
        abstained=False,
        abstain_reason=None,
        reason_codes=[],
    )


def _v21_diagnosis_result(
    assessment: Mapping[str, object],
    *,
    status: str,
    candidates: list[dict[str, object]],
    abstained: bool,
    abstain_reason: str | None,
    reason_codes: list[str],
) -> dict[str, object]:
    primary = candidates[0] if candidates else None
    secondary = candidates[1:] if candidates else []
    confidence_score = 0.0 if abstained else min(1.0, float(primary["score"]) / 100.0)
    return {
        "status": status,
        "presentation": {"title": "辅助辨证倾向"},
        "abstained": abstained,
        "abstain_reason": abstain_reason,
        "candidate_tendencies": deepcopy(candidates),
        "primary_tendency": deepcopy(primary),
        "secondary_tendencies": deepcopy(secondary),
        "confidence": {
            "level": "low" if abstained else "medium",
            "score": confidence_score,
        },
        "supporting_evidence_ids": (
            list(primary.get("supporting_evidence_ids", [])) if primary else []
        ),
        "contradicting_evidence_ids": (
            list(primary.get("contradicting_evidence_ids", [])) if primary else []
        ),
        "conflicts": deepcopy(_mapping_list(assessment.get("conflicts"))),
        "warnings": [],
        "assessment_status": assessment.get("status"),
        "assessment_revision": assessment.get("revision", 1),
        "degradation": {
            "active": bool(reason_codes),
            "reason_codes": _unique(reason_codes),
        },
        "disclaimer": _DISCLAIMER,
    }
