from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
import json
import re
from typing import Any, TypedDict
import unicodedata

from .providers import (
    JsonLLMProvider,
    LLMProviderError,
    qwen_provider_from_env,
)
from .questionnaire_v2 import (
    QuestionnaireValidationError,
    score_questionnaire,
)
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


class AssessmentDocumentInput(TypedDict):
    ocr_status: str
    confirmed_text: str | None


class _AssessmentV2OptionalInput(TypedDict, total=False):
    document: AssessmentDocumentInput | None
    narrative_text: str | None


class AssessmentV2Submission(_AssessmentV2OptionalInput):
    session_id: str
    user_id: str
    questionnaire: Mapping[str, Any] | Sequence[Mapping[str, Any]]


def run_assessment_v2(
    submission: AssessmentV2Submission | Mapping[str, object],
    llm: JsonLLMProvider | None = None,
) -> dict:
    """Fuse Questionnaire V2 with reliable text sources and validated LLM output."""
    (
        session_id,
        user_id,
        document,
        narrative,
        questionnaire,
    ) = _validate_submission(submission)
    document_text, document_status, unconfirmed_text = _document_source(
        document
    )
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
            "source": "questionnaire",
            "status": "invalid" if questionnaire_invalid else "used",
        },
        {"source": "document", "status": document_status},
        {
            "source": "narrative",
            "status": "used" if narrative_text is not None else "missing",
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

    result = {
        "agent_id": "assessment_agent",
        "session_id": session_id,
        "user_id": user_id,
        "status": "success",
        "analysis_mode": analysis_mode,
        "sources_used": sources_used,
        "state_summary": {
            "summary": "已根据问卷完成确定性状态评估。"
        },
        "dimensions": dimensions,
        "context": {
            "triggers": [],
            "physical_signals": (
                []
                if questionnaire_result is None
                else list(questionnaire_result["physical_signals"])
            ),
        },
        "evidence": (
            []
            if questionnaire_result is None
            else _questionnaire_evidence(dimensions)
        ),
        "conflicts": [],
        "missing_information": missing_information,
        "safety": safety,
        "degradation": _degradation(reason_codes),
        "disclaimer": _DISCLAIMER,
    }

    if safety["status"] == "blocked_safety":
        result["status"] = "blocked_safety"
        result["state_summary"] = {
            "summary": "检测到需要优先处理的安全风险，普通状态分析已终止。"
        }
        result["evidence"] = []
        return result

    try:
        provider = llm if llm is not None else qwen_provider_from_env()
        if provider is None:
            reason_codes.append("LLM_NOT_CONFIGURED")
            result["status"] = "degraded"
            result["degradation"] = _degradation(reason_codes)
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
        result["degradation"] = _degradation(reason_codes)
        return result
    except json.JSONDecodeError:
        reason_codes.append("LLM_INVALID_JSON")
        result["status"] = "degraded"
        result["degradation"] = _degradation(reason_codes)
        return result
    except LLMProviderError:
        reason_codes.append("LLM_PROVIDER_ERROR")
        result["status"] = "degraded"
        result["degradation"] = _degradation(reason_codes)
        return result
    except Exception:
        reason_codes.append("LLM_UNEXPECTED_ERROR")
        result["status"] = "degraded"
        result["degradation"] = _degradation(reason_codes)
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
        result["degradation"] = _degradation(reason_codes)
        return result

    result["state_summary"] = validated_model["state_summary"]
    result["context"] = validated_model["context"]
    result["evidence"] = validated_model["evidence"]
    result["conflicts"] = validated_model["conflicts"]
    if validated_model["conflicts"]:
        reason_codes.append("SOURCE_CONFLICT")
    if reason_codes:
        result["status"] = "degraded"
    result["degradation"] = _degradation(reason_codes)
    return result


def _validate_submission(
    submission: object,
) -> tuple[str, str, Mapping[str, object] | None, str | None, object]:
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

    narrative_text = submission.get("narrative_text")
    if narrative_text is not None and not isinstance(narrative_text, str):
        raise AssessmentValidationError(
            "narrative_text must be a string or None"
        )
    return (
        session_id.strip(),
        user_id.strip(),
        document,
        narrative_text,
        submission.get("questionnaire"),
    )


def _extract_raw_questionnaire_risk_flags(
    questionnaire: object,
) -> list[str]:
    q12_values: list[object] = []
    if isinstance(questionnaire, Mapping):
        q12_values.append(questionnaire.get("q12_physical_safety"))
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
        return "document_text_questionnaire"
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
    return {
        "active": bool(reason_codes),
        "reason_codes": list(reason_codes),
    }


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
