from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import datetime, timezone
import json
import re
from typing import Any, TypedDict
import unicodedata
from uuid import uuid4

from .providers import (
    JsonLLMProvider,
    LLMProviderError,
    qwen_provider_from_env,
)
from .narrative_schema import extract_narrative
from .questionnaire_v2 import (
    QuestionnaireValidationError,
    score_questionnaire,
    score_questionnaire_v21,
)
from .sprint4_contracts import EvidenceItem, NarrativeExtractionResult
from .safety_rules import evaluate_safety


_DISCLAIMER = (
    "本结果仅用于状态评估与音乐调养参考，不构成医学诊断或治疗建议。"
)
_QUESTION_SOURCE_BY_DIMENSION = {
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
}
_QUESTION_SOURCES = frozenset(_QUESTION_SOURCE_BY_DIMENSION.values())
_DIMENSION_LABELS = {
    "tension_worry": "紧张担忧",
    "overthinking": "反复思虑",
    "irritability_anger": "烦躁易怒",
    "low_mood": "情绪低落",
    "interest_loss": "兴趣减退",
    "fear_unease": "不安恐惧",
    "sleep_disturbance": "睡眠困扰",
    "low_energy": "精力不足",
    "appetite_change": "食欲变化",
    "daily_impact": "日常受影响",
}
_REQUIRED_MODEL_FIELDS = frozenset(
    {"state_summary", "context", "evidence"}
)
_STATE_SUMMARY_FIELDS = frozenset({"summary"})
_CONTEXT_FIELDS = frozenset({"triggers", "physical_signals"})
_EVIDENCE_FIELDS = frozenset({"claim", "sources", "summary"})
_CONFLICT_FIELDS = frozenset({"topic", "sources", "summary"})
_OCR_STATUSES = frozenset(
    {"confirmed", "pending", "failed", "unconfirmed"}
)
_RISK_FLAGS = frozenset(
    {
        "self_harm_thoughts",
        "severe_chest_pain",
        "severe_breathing_difficulty",
    }
)


class AssessmentValidationError(ValueError):
    """Raised when an Assessment V2 envelope violates its runtime contract."""


class _AssessmentV2OptionalInput(TypedDict, total=False):
    document_id: str | None
    document_text: str | None
    narrative_text: str | None


class AssessmentV2Submission(_AssessmentV2OptionalInput):
    session_id: str
    user_id: str
    questionnaire_answers: (
        Mapping[str, Any] | Sequence[Mapping[str, Any]]
    )


def run_assessment_v2(
    submission: AssessmentV2Submission | Mapping[str, object],
    llm: JsonLLMProvider | None = None,
) -> dict:
    """Fuse Questionnaire V2 with reliable text sources and validated LLM output."""
    (
        session_id,
        user_id,
        document_text,
        document_status,
        unconfirmed_text,
        narrative,
        questionnaire,
    ) = _validate_submission(submission)
    narrative_text = _non_blank_text(narrative)

    safety = evaluate_safety(
        narrative_text=narrative_text,
        confirmed_ocr_text=document_text,
        questionnaire_safety_flags=_extract_raw_questionnaire_risk_flags(
            questionnaire
        ),
    )
    questionnaire_invalid = False
    try:
        questionnaire_result = score_questionnaire(
            questionnaire  # type: ignore[arg-type]
        )
    except QuestionnaireValidationError as exc:
        if safety["status"] != "blocked_safety":
            raise AssessmentValidationError(
                "invalid assessment questionnaire"
            ) from exc
        questionnaire_invalid = True
        questionnaire_result = None
        dimensions = {}
    else:
        safety = evaluate_safety(
            narrative_text=narrative_text,
            confirmed_ocr_text=document_text,
            questionnaire_safety_flags=questionnaire_result["safety_flags"],
        )
        dimensions = {
            dimension: score["normalized_score"]
            for dimension, score
            in questionnaire_result["dimension_scores"].items()
        }
    analysis_mode = _analysis_mode(
        has_document=document_text is not None,
        has_narrative=narrative_text is not None,
    )
    sources_used = [
        {
            "source": "document",
            "status": document_status,
        },
        {
            "source": "narrative",
            "status": "used" if narrative_text is not None else "missing",
        },
        {
            "source": "questionnaire",
            "status": "invalid" if questionnaire_invalid else "used",
        },
    ]
    missing_information = []
    if document_text is None:
        missing_information.append("document")
    if narrative_text is None:
        missing_information.append("narrative")

    reason_codes = []
    if document_status == "unconfirmed":
        reason_codes.append("DOCUMENT_UNCONFIRMED")
    if questionnaire_invalid:
        reason_codes.append("QUESTIONNAIRE_INVALID")

    physical_signals = (
        []
        if questionnaire_result is None
        else list(questionnaire_result["physical_signals"])
    )
    evidence = (
        []
        if questionnaire_result is None
        else _questionnaire_evidence(dimensions)
    )
    result = {
        "agent_id": "assessment_agent",
        "session_id": session_id,
        "user_id": user_id,
        "status": "success",
        "analysis_mode": analysis_mode,
        "sources_used": sources_used,
        "emotion_profile": _build_emotion_profile(dimensions),
        "physical_profile": _build_physical_profile(
            dimensions,
            physical_signals,
        ),
        "life_events": {"triggers": []},
        "assessment_summary": "已根据问卷完成确定性状态评估。",
        "extracted_evidence": evidence,
        "conflicts": [],
        "missing_information": missing_information,
        "degradation": _degradation(reason_codes),
        "warnings": _warning_messages(reason_codes),
        "safety_flags": list(safety["flags"]),
        "disclaimer": _DISCLAIMER,
    }

    if safety["status"] == "blocked_safety":
        result["status"] = "blocked_safety"
        result["assessment_summary"] = (
            "检测到需要优先处理的安全风险，普通状态分析已终止。"
        )
        result["extracted_evidence"] = []
        result["degradation"] = _degradation(reason_codes)
        result["warnings"] = _warning_messages(reason_codes)
        return result

    try:
        provider = llm if llm is not None else qwen_provider_from_env()
        if provider is None:
            reason_codes.append("LLM_NOT_CONFIGURED")
            result["status"] = "degraded"
            _apply_llm_fallback(result)
            result["degradation"] = _degradation(reason_codes)
            result["warnings"] = _warning_messages(reason_codes)
            return result

        system_prompt, user_prompt = _build_prompts(
            analysis_mode=analysis_mode,
            dimensions=dimensions,
            questionnaire_result=questionnaire_result,
            document_text=document_text,
            narrative_text=narrative_text,
        )
        model_result = provider.complete_json(system_prompt, user_prompt)
    except TimeoutError:
        reason_codes.append("LLM_TIMEOUT")
        result["status"] = "degraded"
        _apply_llm_fallback(result)
        result["degradation"] = _degradation(reason_codes)
        result["warnings"] = _warning_messages(reason_codes)
        return result
    except json.JSONDecodeError:
        reason_codes.append("LLM_INVALID_JSON")
        result["status"] = "degraded"
        _apply_llm_fallback(result)
        result["degradation"] = _degradation(reason_codes)
        result["warnings"] = _warning_messages(reason_codes)
        return result
    except LLMProviderError:
        reason_codes.append("LLM_PROVIDER_ERROR")
        result["status"] = "degraded"
        _apply_llm_fallback(result)
        result["degradation"] = _degradation(reason_codes)
        result["warnings"] = _warning_messages(reason_codes)
        return result
    except Exception:
        reason_codes.append("LLM_UNEXPECTED_ERROR")
        result["status"] = "degraded"
        _apply_llm_fallback(result)
        result["degradation"] = _degradation(reason_codes)
        result["warnings"] = _warning_messages(reason_codes)
        return result

    available_sources = set(_QUESTION_SOURCES)
    if document_text is not None:
        available_sources.add("document")
    if narrative_text is not None:
        available_sources.add("narrative")
    validated_model, validation_reason = _validate_model_result(
        model_result,
        available_sources=available_sources,
        unconfirmed_text=unconfirmed_text,
    )
    if validation_reason is not None:
        reason_codes.append(validation_reason)
        result["status"] = "degraded"
        _apply_llm_fallback(result)
        result["degradation"] = _degradation(reason_codes)
        result["warnings"] = _warning_messages(reason_codes)
        return result

    model_context = validated_model["context"]
    result["assessment_summary"] = validated_model["state_summary"][
        "summary"
    ]
    result["life_events"] = {
        "triggers": list(model_context["triggers"]),
    }
    result["physical_profile"] = _build_physical_profile(
        dimensions,
        _unique_strings(
            physical_signals,
            list(model_context["physical_signals"]),
        ),
    )
    result["extracted_evidence"] = validated_model["evidence"]
    result["conflicts"] = validated_model["conflicts"]
    if validated_model["conflicts"]:
        reason_codes.append("SOURCE_CONFLICT")
    if reason_codes:
        result["status"] = "degraded"
    result["degradation"] = _degradation(reason_codes)
    result["warnings"] = _warning_messages(reason_codes)
    return result


def _validate_submission(
    submission: object,
) -> tuple[str, str, str | None, str, str | None, str | None, object]:
    if not isinstance(submission, Mapping):
        raise AssessmentValidationError("submission must be a mapping")

    session_id = submission.get("session_id")
    if not isinstance(session_id, str) or not session_id.strip():
        raise AssessmentValidationError(
            "session_id must be a non-empty string"
        )
    user_id = submission.get("user_id")
    if not isinstance(user_id, str) or not user_id.strip():
        raise AssessmentValidationError(
            "user_id must be a non-empty string"
        )

    document_id = submission.get("document_id")
    if document_id is not None and not isinstance(document_id, str):
        raise AssessmentValidationError(
            "document_id must be a string or None"
        )

    if "document_text" in submission or "document_id" in submission:
        raw_document_text = submission.get("document_text")
        if raw_document_text is not None and not isinstance(
            raw_document_text,
            str,
        ):
            raise AssessmentValidationError(
                "document_text must be a string or None"
            )
        document_text = _non_blank_text(raw_document_text)
        document_status = (
            "confirmed" if document_text is not None else "missing"
        )
        unconfirmed_text = None
    else:
        document = submission.get("document")
        if document is not None:
            if not isinstance(document, Mapping):
                raise AssessmentValidationError(
                    "document must be a mapping or None"
                )
            if document.get("ocr_status") not in _OCR_STATUSES:
                raise AssessmentValidationError(
                    "document.ocr_status is invalid"
                )
            if (
                "confirmed_text" not in document
                or (
                    document["confirmed_text"] is not None
                    and not isinstance(document["confirmed_text"], str)
                )
            ):
                raise AssessmentValidationError(
                    "document.confirmed_text must be a string or None"
                )
        document_text, document_status, unconfirmed_text = (
            _document_source(document)
        )

    narrative_text = submission.get("narrative_text")
    if narrative_text is not None and not isinstance(narrative_text, str):
        raise AssessmentValidationError(
            "narrative_text must be a string or None"
        )
    return (
        session_id.strip(),
        user_id.strip(),
        document_text,
        document_status,
        unconfirmed_text,
        narrative_text,
        submission.get(
            "questionnaire_answers",
            submission.get("questionnaire"),
        ),
    )


def _extract_raw_questionnaire_risk_flags(
    questionnaire: object,
) -> list[str]:
    q12_values: list[object] = []
    if isinstance(questionnaire, Mapping):
        records = questionnaire.get("answers")
        if isinstance(records, Sequence) and not isinstance(
            records,
            (str, bytes),
        ):
            q12_values.extend(
                record.get("value")
                for record in records
                if isinstance(record, Mapping)
                and record.get("question_id")
                == "q12_physical_safety"
            )
        else:
            q12_values.append(
                questionnaire.get("q12_physical_safety")
            )
    elif (
        isinstance(questionnaire, Sequence)
        and not isinstance(questionnaire, (str, bytes))
    ):
        q12_values.extend(
            record.get("value")
            for record in questionnaire
            if isinstance(record, Mapping)
            and record.get("question_id") == "q12_physical_safety"
        )

    selected = set()
    for value in q12_values:
        if isinstance(value, (list, tuple)):
            selected.update(
                flag
                for flag in value
                if isinstance(flag, str) and flag in _RISK_FLAGS
            )
    return [
        flag
        for flag in (
            "self_harm_thoughts",
            "severe_chest_pain",
            "severe_breathing_difficulty",
        )
        if flag in selected
    ]


def _apply_llm_fallback(result: dict[str, object]) -> None:
    result["analysis_mode"] = "questionnaire_only"
    sources = result.get("sources_used")
    if not isinstance(sources, list):
        return
    for source in sources:
        if (
            isinstance(source, dict)
            and source.get("source") in {"document", "narrative"}
            and source.get("status") in {"confirmed", "used"}
        ):
            source["status"] = "unavailable"


def _document_source(
    value: object,
) -> tuple[str | None, str, str | None]:
    if not isinstance(value, Mapping):
        return None, "missing", None

    ocr_status = value.get("ocr_status")
    raw_text = value.get("confirmed_text")
    text = _non_blank_text(raw_text)
    if ocr_status == "confirmed" and text is not None:
        return text, "used", None
    if ocr_status in {"pending", "failed", "unconfirmed"} or (
        text is not None and ocr_status != "confirmed"
    ):
        return None, "unconfirmed", text
    return None, "missing", None


def _non_blank_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _analysis_mode(*, has_document: bool, has_narrative: bool) -> str:
    if has_document and has_narrative:
        return "document_narrative_questionnaire"
    if has_document:
        return "document_questionnaire"
    if has_narrative:
        return "narrative_questionnaire"
    return "questionnaire_only"


def _questionnaire_evidence(
    dimensions: Mapping[str, object],
) -> list[dict[str, object]]:
    return [
        {
            "claim": f"{dimension}维度问卷结果",
            "sources": [_QUESTION_SOURCE_BY_DIMENSION[dimension]],
            "summary": f"归一化得分为{score}。",
        }
        for dimension, score in dimensions.items()
    ]


def _degradation(reason_codes: list[str]) -> dict[str, object]:
    reason_code = reason_codes[0] if reason_codes else None
    if reason_code in {
        "LLM_NOT_CONFIGURED",
        "LLM_TIMEOUT",
        "LLM_INVALID_JSON",
        "LLM_MISSING_FIELDS",
        "LLM_SCHEMA_INVALID",
        "LLM_PROVIDER_ERROR",
        "LLM_UNEXPECTED_ERROR",
        "LLM_UNKNOWN_SOURCE",
        "LLM_PROHIBITED_MEDICAL_FIELD",
        "LLM_UNCONFIRMED_OCR_ECHO",
    }:
        fallback = "deterministic_questionnaire"
    elif reason_code == "SOURCE_CONFLICT":
        fallback = "review_required"
    elif reason_code == "QUESTIONNAIRE_INVALID":
        fallback = "safety_only"
    elif reason_code == "DOCUMENT_UNCONFIRMED":
        fallback = "questionnaire_and_narrative"
    else:
        fallback = None
    return {
        "triggered": bool(reason_codes),
        "reason_code": reason_code,
        "fallback": fallback,
    }


def _warning_messages(reason_codes: list[str]) -> list[str]:
    messages = {
        "DOCUMENT_UNCONFIRMED": (
            "未经确认的 OCR 文本未作为可靠评估来源。"
        ),
        "QUESTIONNAIRE_INVALID": "问卷无效，仅保留安全阻断结果。",
        "SOURCE_CONFLICT": "不同来源存在冲突，请用户确认评估结果。",
    }
    return [
        (
            f"{reason_code}: "
            f"{messages.get(reason_code, 'AI 分析暂时不可用，已切换到确定性问卷评估。')}"
        )
        for reason_code in reason_codes
    ]


def _build_emotion_profile(
    dimensions: Mapping[str, object],
) -> dict[str, object]:
    scores = {
        dimension: int(score)
        for dimension, score in dimensions.items()
        if dimension in _DIMENSION_LABELS
        and isinstance(score, (int, float))
    }
    ranked = sorted(
        (
            (dimension, score)
            for dimension, score in scores.items()
            if score > 0
        ),
        key=lambda item: (
            -item[1],
            list(_DIMENSION_LABELS).index(item[0]),
        ),
    )
    labels = [_DIMENSION_LABELS[dimension] for dimension, _ in ranked]
    return {
        "primary_states": labels[:2],
        "secondary_states": labels[2:],
        "dimension_scores": scores,
        "tcm_emotion_candidates": [],
    }


def _build_physical_profile(
    dimensions: Mapping[str, object],
    physical_signals: list[str],
) -> dict[str, object]:
    return {
        "sleep_disturbance": int(
            dimensions.get("sleep_disturbance", 0)
        ),
        "low_energy": int(dimensions.get("low_energy", 0)),
        "appetite_change": int(
            dimensions.get("appetite_change", 0)
        ),
        "physical_signals": list(physical_signals),
    }


def _unique_strings(*groups: list[str]) -> list[str]:
    return list(dict.fromkeys(item for group in groups for item in group))


def _build_prompts(
    *,
    analysis_mode: str,
    dimensions: Mapping[str, object],
    questionnaire_result: Mapping[str, object],
    document_text: str | None,
    narrative_text: str | None,
) -> tuple[str, str]:
    system_prompt = (
        "你是状态评估信息整理助手。只提取和归纳输入，不作医学诊断。"
        "返回JSON对象，必须包含state_summary对象、context对象、evidence数组；"
        "state_summary只能包含非空summary；context只能包含triggers和"
        "physical_signals，二者必须是无重复的字符串数组；"
        "evidence每项只能包含claim、sources、summary。"
        "sources只能引用实际提供的document、narrative或questionnaire:q02到q11。"
        "可选conflicts数组每项只能包含topic、sources、summary。"
        "不得返回syndrome、diagnosis或其他医学结论字段，也不得改写问卷维度分数。"
    )
    payload: dict[str, object] = {
        "analysis_mode": analysis_mode,
        "questionnaire": {
            "dimensions": dict(dimensions),
            "mood_metaphor": questionnaire_result["mood_metaphor"],
            "physical_signals": questionnaire_result["physical_signals"],
        },
    }
    if document_text is not None:
        payload["document"] = document_text
    if narrative_text is not None:
        payload["narrative"] = narrative_text
    return system_prompt, json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
    )


def _validate_model_result(
    value: object,
    *,
    available_sources: set[str],
    unconfirmed_text: str | None,
) -> tuple[dict[str, object] | None, str | None]:
    if not isinstance(value, Mapping):
        return None, "LLM_INVALID_JSON"
    if not _REQUIRED_MODEL_FIELDS.issubset(value):
        return None, "LLM_MISSING_FIELDS"
    if _contains_prohibited_medical_field(value):
        return None, "LLM_PROHIBITED_MEDICAL_FIELD"

    state_summary = value["state_summary"]
    context = value["context"]
    evidence = value["evidence"]
    conflicts = value.get("conflicts", [])
    if (
        not _valid_state_summary(state_summary)
        or not _valid_context(context)
        or not isinstance(evidence, list)
        or not isinstance(conflicts, list)
    ):
        return None, "LLM_SCHEMA_INVALID"

    evidence_reason = _validate_evidence(
        evidence,
        available_sources=available_sources,
    )
    if evidence_reason is not None:
        return None, evidence_reason
    conflict_reason = _validate_conflicts(
        conflicts,
        available_sources=available_sources,
    )
    if conflict_reason is not None:
        return None, conflict_reason

    accepted = {
        "state_summary": deepcopy(dict(state_summary)),
        "context": deepcopy(dict(context)),
        "evidence": deepcopy(evidence),
        "conflicts": deepcopy(conflicts),
    }
    sensitive_tokens = _unconfirmed_sensitive_tokens(unconfirmed_text)
    if sensitive_tokens and _contains_sensitive_token(
        accepted,
        sensitive_tokens,
    ):
        return None, "LLM_UNCONFIRMED_OCR_ECHO"
    return accepted, None


def _validate_evidence(
    evidence: list[object],
    *,
    available_sources: set[str],
) -> str | None:
    for item in evidence:
        if not isinstance(item, Mapping) or set(item) != _EVIDENCE_FIELDS:
            return "LLM_SCHEMA_INVALID"
        if (
            not _non_empty_string(item["claim"])
            or not _non_empty_string(item["summary"])
            or not _valid_source_list(item["sources"])
        ):
            return "LLM_SCHEMA_INVALID"
        if not set(item["sources"]).issubset(available_sources):
            return "LLM_UNKNOWN_SOURCE"
    return None


def _valid_state_summary(value: object) -> bool:
    return (
        isinstance(value, Mapping)
        and set(value) == _STATE_SUMMARY_FIELDS
        and _non_empty_string(value["summary"])
    )


def _valid_context(value: object) -> bool:
    return (
        isinstance(value, Mapping)
        and set(value) == _CONTEXT_FIELDS
        and _valid_string_list(value["triggers"])
        and _valid_string_list(value["physical_signals"])
    )


def _validate_conflicts(
    conflicts: list[object],
    *,
    available_sources: set[str],
) -> str | None:
    for item in conflicts:
        if not isinstance(item, Mapping) or set(item) != _CONFLICT_FIELDS:
            return "LLM_SCHEMA_INVALID"
        if (
            not _non_empty_string(item["topic"])
            or not _non_empty_string(item["summary"])
            or not _valid_source_list(item["sources"], minimum=2)
        ):
            return "LLM_SCHEMA_INVALID"
        if not set(item["sources"]).issubset(available_sources):
            return "LLM_UNKNOWN_SOURCE"
    return None


def _valid_source_list(value: object, minimum: int = 1) -> bool:
    return (
        isinstance(value, list)
        and len(value) >= minimum
        and all(isinstance(source, str) for source in value)
        and len(set(value)) == len(value)
    )


def _valid_string_list(value: object) -> bool:
    return (
        isinstance(value, list)
        and all(_non_empty_string(item) for item in value)
        and len(set(value)) == len(value)
    )


def _non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _contains_prohibited_medical_field(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if isinstance(key, str):
                normalized = key.casefold()
                if (
                    "diagnosis" in normalized
                    or "syndrome" in normalized
                    or "诊断" in key
                    or "证型" in key
                ):
                    return True
            if _contains_prohibited_medical_field(child):
                return True
    elif isinstance(value, list):
        return any(_contains_prohibited_medical_field(item) for item in value)
    return False


def _unconfirmed_sensitive_tokens(
    text: str | None,
) -> frozenset[str]:
    if not text:
        return frozenset()

    tokens = {
        _normalize_echo_text(token)
        for token in re.findall(
            r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{6,}"
            r"(?![A-Za-z0-9_-])",
            text,
        )
        if any(character.isdigit() for character in token)
    }
    normalized_full_text = _normalize_echo_text(text)
    for match in re.finditer(
        r"\bid\s*[-:]\s*\d+\b|\brecord\s+id\s+\d+\b",
        normalized_full_text,
    ):
        explicit_id = match.group()
        tokens.add(explicit_id)
        if explicit_id.startswith("record "):
            tokens.add(explicit_id.removeprefix("record "))
    if (
        len(normalized_full_text) >= 8
        and re.search(r"[a-z]", normalized_full_text)
    ):
        tokens.add(normalized_full_text)
    return frozenset(tokens)


def _contains_sensitive_token(
    value: object,
    tokens: frozenset[str],
) -> bool:
    if isinstance(value, str):
        normalized = _normalize_echo_text(value)
        return any(token in normalized for token in tokens)
    if isinstance(value, Mapping):
        return any(
            _contains_sensitive_token(item, tokens)
            for item in value.values()
        )
    if isinstance(value, list):
        return any(
            _contains_sensitive_token(item, tokens)
            for item in value
        )
    return False


def _normalize_echo_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"\s+", " ", normalized).strip()


def _is_json_value(value: object) -> bool:
    if value is None or isinstance(value, (str, int, float, bool)):
        return True
    if isinstance(value, list):
        return all(_is_json_value(item) for item in value)
    if isinstance(value, Mapping):
        return all(
            isinstance(key, str) and _is_json_value(item)
            for key, item in value.items()
        )
    return False


def run_assessment_v21(
    submission: Mapping[str, object],
    *,
    provider: object | None = None,
) -> dict[str, object]:
    """Run the Sprint 4 evidence-first Assessment path synchronously."""
    return asyncio.run(_run_assessment_v21_async(submission, provider=provider))


async def _run_assessment_v21_async(
    submission: Mapping[str, object],
    *,
    provider: object | None,
) -> dict[str, object]:
    if not isinstance(submission, Mapping):
        raise AssessmentValidationError("assessment_v2.1 submission must be a mapping")
    assessment_id = _v21_required_id(submission, "assessment_id")
    session_id = _v21_required_id(submission, "session_id")
    user_id = _v21_required_id(submission, "user_id")
    try:
        questionnaire = score_questionnaire_v21(
            submission.get("questionnaire_answers")  # type: ignore[arg-type]
        )
    except QuestionnaireValidationError as exc:
        raise AssessmentValidationError("invalid questionnaire_v2.1") from exc

    narrative_text = _non_blank_text(submission.get("narrative_text"))
    document_text = _non_blank_text(submission.get("document_text"))
    document_confirmed = submission.get("document_confirmed") is True
    if document_text is not None and not document_confirmed:
        document_text = None

    safety = evaluate_safety(
        narrative_text=narrative_text,
        confirmed_ocr_text=document_text,
        questionnaire_safety_flags=list(questionnaire.safety_flags),
    )
    evidence = _v21_questionnaire_evidence(questionnaire)
    input_status: dict[str, dict[str, object]] = {
        "questionnaire": {
            "version": questionnaire.schema_version,
            "status": "processed",
            "questions_answered": questionnaire.questions_answered,
            "dimensions_scored": len(questionnaire.dimension_scores),
            "safety_flags": list(questionnaire.safety_flags),
        },
        "narrative": {
            "status": "skipped" if narrative_text is None else "unavailable",
            "text_length": len(narrative_text or ""),
            "evidence_items_extracted": 0,
            "warnings": [],
        },
        "document": {
            "status": "skipped" if document_text is None else "confirmed",
            "evidence_items_extracted": 0,
            "warnings": [],
        },
    }
    degradation_reasons: list[str] = []

    if safety["status"] == "blocked_safety":
        return _v21_result(
            assessment_id=assessment_id,
            session_id=session_id,
            user_id=user_id,
            status="blocked_safety",
            evidence=[],
            conflicts=[],
            missing_information=[],
            follow_up_questions=[],
            input_status=input_status,
            questionnaire=questionnaire,
            safety_flags=list(safety["flags"]),
            degradation={"active": True, "reason_codes": ["SAFETY_BLOCKED"]},
            requires_confirmation=False,
        )

    if provider is not None and narrative_text is not None:
        narrative_result = await extract_narrative(
            narrative_text,
            source_type="narrative",
            provider=provider,  # type: ignore[arg-type]
        )
        _merge_v21_narrative_status(input_status["narrative"], narrative_result)
        if narrative_result.status == "processed":
            evidence.extend(
                _v21_narrative_evidence(narrative_result, source_type="narrative")
            )
        else:
            degradation_reasons.append(
                narrative_result.reason_code or "NARRATIVE_UNAVAILABLE"
            )

    if provider is not None and document_text is not None:
        document_result = await extract_narrative(
            document_text,
            source_type="document",
            provider=provider,  # type: ignore[arg-type]
        )
        _merge_v21_narrative_status(input_status["document"], document_result)
        input_status["document"]["status"] = "confirmed"
        if document_result.status == "processed":
            evidence.extend(
                _v21_narrative_evidence(document_result, source_type="document")
            )
        else:
            degradation_reasons.append(
                document_result.reason_code or "DOCUMENT_EXTRACTION_UNAVAILABLE"
            )

    conflicts = _v21_conflicts(evidence)
    coverage = _v21_evidence_coverage(evidence, len(questionnaire.dimension_scores))
    missing_information = _v21_missing_information(
        narrative_text=narrative_text,
        document_text=document_text,
        evidence=evidence,
    )
    follow_up_questions = _v21_follow_up_questions(
        assessment_id=assessment_id,
        coverage=coverage,
        missing_information=missing_information,
        conflicts=conflicts,
    )
    status = "needs_follow_up" if follow_up_questions else "success"
    if degradation_reasons and status == "success":
        status = "degraded"
    return _v21_result(
        assessment_id=assessment_id,
        session_id=session_id,
        user_id=user_id,
        status=status,
        evidence=evidence,
        conflicts=conflicts,
        missing_information=missing_information,
        follow_up_questions=follow_up_questions,
        input_status=input_status,
        questionnaire=questionnaire,
        safety_flags=list(safety["flags"]),
        degradation={
            "active": bool(degradation_reasons),
            "reason_codes": _unique_strings(degradation_reasons),
        },
        requires_confirmation=submission.get("confirmation_status") != "confirmed",
        coverage=coverage,
    )


def _v21_required_id(submission: Mapping[str, object], key: str) -> str:
    value = submission.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AssessmentValidationError(f"{key} must be a non-empty string")
    return value.strip()


def _v21_questionnaire_evidence(questionnaire: object) -> list[EvidenceItem]:
    result: list[EvidenceItem] = []
    for dimension, score in questionnaire.dimension_scores.items():
        result.append(
            {
                "evidence_id": f"ev-questionnaire-{dimension}",
                "category": "emotion",
                "label": dimension,
                "display_name": dimension,
                "value": score.raw_score,
                "polarity": "present" if score.raw_score else "absent",
                "severity": _v21_severity(score.raw_score),
                "severity_display": _v21_severity(score.raw_score),
                "time_window": "过去两周",
                "source_type": "questionnaire",
                "source_ref": f"questionnaire:{score.source_questions[0]}",
                "confirmed": True,
                "dimension_score": score.normalized_score,
            }
        )
    return result


def _v21_narrative_evidence(
    extraction: NarrativeExtractionResult,
    *,
    source_type: str,
) -> list[EvidenceItem]:
    return [
        {
            "evidence_id": f"ev-{source_type}-{index}-{uuid4().hex[:8]}",
            "category": item.category,
            "label": item.label,
            "display_name": item.label,
            "value": item.value,
            "polarity": item.polarity,
            "severity": "moderate" if item.value else "none",
            "severity_display": "有一定表现" if item.value else "当前不明显",
            "time_window": item.time_window or "未说明",
            "source_type": source_type,  # type: ignore[typeddict-item]
            "source_ref": item.source_ref,
            "quote": item.quote,
            "extraction_confidence": item.extraction_confidence,
            "confirmed": source_type == "document",
            "negated": item.negated,
        }
        for index, item in enumerate(extraction.items, start=1)
    ]


def _merge_v21_narrative_status(
    target: dict[str, object],
    result: NarrativeExtractionResult,
) -> None:
    target["status"] = result.status
    target["evidence_items_extracted"] = len(result.items)
    target["warnings"] = list(result.warnings)
    if result.model_metadata:
        target["model_metadata"] = result.model_metadata


def _v21_evidence_coverage(evidence: list[EvidenceItem], total_dimensions: int) -> float:
    if total_dimensions <= 0:
        return 0.0
    covered = {
        item["label"]
        for item in evidence
        if item.get("confirmed") is True or item["source_type"] == "questionnaire"
    }
    source_types = {item["source_type"] for item in evidence}
    return (len(covered) / total_dimensions) * min(1.0, len(source_types) / 3)


def _v21_missing_information(
    *,
    narrative_text: str | None,
    document_text: str | None,
    evidence: list[EvidenceItem],
) -> list[dict[str, object]]:
    missing: list[dict[str, object]] = []
    labels = {item["label"] for item in evidence}
    if narrative_text is None and document_text is None:
        missing.append(
            {
                "field": "supplementary_context",
                "display_name": "补充描述或材料",
                "reason": "当前只有问卷来源，缺少第二类可靠来源。",
                "severity": "important",
            }
        )
    if "duration" not in labels and narrative_text is not None:
        missing.append(
            {
                "field": "duration",
                "display_name": "状态持续时间",
                "reason": "文本和现有证据未提供可定位的持续时间。",
                "severity": "important",
            }
        )
    return missing


def _v21_conflicts(evidence: list[EvidenceItem]) -> list[dict[str, object]]:
    by_label: dict[str, list[EvidenceItem]] = {}
    for item in evidence:
        by_label.setdefault(item["label"], []).append(item)
    conflicts: list[dict[str, object]] = []
    for label, items in by_label.items():
        values = {str(item.get("value")) for item in items}
        sources = {item["source_type"] for item in items}
        if len(values) > 1 and len(sources) > 1:
            conflicts.append(
                {
                    "conflict_id": f"cf-{label}",
                    "topic": label,
                    "display_topic": label,
                    "severity": "moderate",
                    "sources": [
                        {"source_type": item["source_type"], "value": item.get("value")}
                        for item in items
                    ],
                    "summary": f"{label} 在多个来源中存在不同值。",
                    "resolution": "awaiting_user",
                }
            )
    return conflicts


def _v21_follow_up_questions(
    *,
    assessment_id: str,
    coverage: float,
    missing_information: list[dict[str, object]],
    conflicts: list[dict[str, object]],
) -> list[dict[str, object]]:
    questions: list[dict[str, object]] = []
    if any(item["field"] == "duration" for item in missing_information):
        questions.append(
            {
                "follow_up_id": f"fu-{uuid4().hex[:8]}",
                "assessment_id": assessment_id,
                "trigger_reason": "duration_unclear",
                "priority": 1,
                "question_id": "fu_duration_001",
                "text": "这些状态大概持续了多久？",
                "type": "single_choice",
                "options": ["少于3天", "3-6天", "1-2周", "2周以上"],
                "required": True,
                "max_questions_total": 6,
            }
        )
    if conflicts:
        questions.append(
            {
                "follow_up_id": f"fu-{uuid4().hex[:8]}",
                "assessment_id": assessment_id,
                "trigger_reason": "source_conflict",
                "priority": 3,
                "question_id": "fu_conflict_001",
                "text": "不同来源对这项状态的描述不一致，哪一种更接近你当前的感受？",
                "type": "single_choice",
                "options": ["问卷更准确", "文字或材料更准确", "都不准确"],
                "required": True,
                "max_questions_total": 6,
            }
        )
    if coverage < 0.70 and not questions:
        questions.append(
            {
                "follow_up_id": f"fu-{uuid4().hex[:8]}",
                "assessment_id": assessment_id,
                "trigger_reason": "supplementary_context",
                "priority": 7,
                "question_id": "fu_context_001",
                "text": "可以补充描述最近发生了什么，以及它对日常生活的影响吗？",
                "type": "text",
                "options": [],
                "required": True,
                "max_questions_total": 6,
            }
        )
    return sorted(questions, key=lambda item: int(item["priority"]))[:4]


def _v21_result(
    *,
    assessment_id: str,
    session_id: str,
    user_id: str,
    status: str,
    evidence: list[EvidenceItem],
    conflicts: list[dict[str, object]],
    missing_information: list[dict[str, object]],
    follow_up_questions: list[dict[str, object]],
    input_status: dict[str, dict[str, object]],
    questionnaire: object,
    safety_flags: list[str],
    degradation: dict[str, object],
    requires_confirmation: bool,
    coverage: float = 0.0,
) -> dict[str, object]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "agent_id": "assessment_agent",
        "assessment_id": assessment_id,
        "session_id": session_id,
        "user_id": user_id,
        "status": status,
        "revision": 1,
        "analysis_mode": _v21_analysis_mode(input_status),
        "confidence": coverage,
        "confidence_semantics": "evidence_coverage",
        "input_processing_status": input_status,
        "emotion_profile": {
            "dimension_scores": {
                label: score.normalized_score
                for label, score in questionnaire.dimension_scores.items()
            }
        },
        "physical_profile": {
            "physical_signals": list(questionnaire.physical_signals)
        },
        "life_events": {"triggers": []},
        "user_goal": questionnaire.qualitative.get("goal"),
        "assessment_summary": "已根据可追溯来源生成状态评估，等待用户确认。",
        "evidence_items": evidence,
        "evidence_coverage_score": coverage,
        "conflicts": conflicts,
        "missing_information": missing_information,
        "follow_up_questions": follow_up_questions,
        "requires_user_confirmation": requires_confirmation,
        "safety_flags": safety_flags,
        "degradation": degradation,
        "warnings": [],
        "revision_metadata": {
            "revision": 1,
            "created_at": now,
            "previous_revision": None,
        },
        "disclaimer": _DISCLAIMER,
    }


def _v21_analysis_mode(input_status: Mapping[str, Mapping[str, object]]) -> str:
    has_document = input_status["document"]["status"] == "confirmed"
    has_narrative = input_status["narrative"]["status"] == "processed"
    if has_document and has_narrative:
        return "document_narrative_questionnaire"
    if has_document:
        return "document_questionnaire"
    if has_narrative:
        return "narrative_questionnaire"
    return "questionnaire_only"


def _v21_severity(value: int) -> str:
    if value <= 0:
        return "none"
    if value == 1:
        return "mild"
    if value <= 3:
        return "moderate"
    return "severe"
