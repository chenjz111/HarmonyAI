from __future__ import annotations

from collections.abc import Sequence
import unicodedata


_RULES = (
    (
        "self_harm_thoughts",
        "SAFETY_SELF_HARM_OR_SUICIDE",
        (
            "想自杀",
            "要自杀",
            "准备自杀",
            "打算自杀",
            "想轻生",
            "要轻生",
            "想结束自己的生命",
            "结束自己的生命",
            "不想活了",
            "想伤害自己",
            "伤害自己的念头",
            "想自残",
            "kill myself",
            "end my life",
            "take my own life",
            "taking my own life",
            "hurt myself",
            "harm myself",
            "don't want to live",
            "do not want to live",
            "want to die",
            "thinking about suicide",
            "thoughts of suicide",
            "thoughts of self-harm",
            "thoughts of self harm",
            "suicidal thoughts",
        ),
    ),
    (
        "severe_chest_pain",
        "SAFETY_SEVERE_OR_PERSISTENT_CHEST_PAIN",
        (
            "严重胸痛",
            "剧烈胸痛",
            "胸口剧痛",
            "持续胸痛",
            "胸痛持续不缓解",
            "胸痛一直不缓解",
            "胸口疼得厉害",
            "severe chest pain",
            "intense chest pain",
            "crushing chest pain",
            "persistent chest pain",
            "chest pain that won't go away",
            "chest pain that will not go away",
        ),
    ),
    (
        "severe_breathing_difficulty",
        "SAFETY_SEVERE_BREATHING_DIFFICULTY",
        (
            "明显呼吸困难",
            "严重呼吸困难",
            "呼吸非常困难",
            "喘不上气",
            "无法呼吸",
            "快窒息",
            "severe difficulty breathing",
            "cannot breathe",
            "can't breathe",
            "struggling to breathe",
            "gasping for air",
        ),
    ),
)

_ALLOWED_REASON_CODES = tuple(reason_code for _, reason_code, _ in _RULES)


def evaluate_safety(
    narrative_text: str | None = None,
    confirmed_ocr_text: str | None = None,
    questionnaire_safety_flags: Sequence[str] | None = None,
) -> dict[str, object]:
    """Evaluate high-risk signals without model calls or unconfirmed OCR input."""
    normalized_texts = (
        _normalize_text(narrative_text),
        _normalize_text(confirmed_ocr_text),
    )
    selected_questionnaire_flags = set(questionnaire_safety_flags or ())

    matched = [
        (flag, reason_code)
        for flag, reason_code, phrases in _RULES
        if flag in selected_questionnaire_flags
        or any(
            phrase in text
            for text in normalized_texts
            for phrase in phrases
        )
    ]
    blocked = bool(matched)
    return {
        "status": "blocked_safety" if blocked else "success",
        "level": "high" if blocked else "none",
        "flags": [flag for flag, _ in matched],
        "reason_codes": [reason_code for _, reason_code in matched],
        "block_standard_prescription": blocked,
    }


def build_safety_log_fields(reason_codes: Sequence[str]) -> dict[str, object]:
    """Build non-sensitive log fields from fixed reason codes only."""
    supplied_codes = set(reason_codes)
    unsupported_codes = supplied_codes.difference(_ALLOWED_REASON_CODES)
    if unsupported_codes:
        raise ValueError("unsupported safety reason code")

    ordered_codes = [
        reason_code
        for reason_code in _ALLOWED_REASON_CODES
        if reason_code in supplied_codes
    ]
    blocked = bool(ordered_codes)
    return {
        "status": "blocked_safety" if blocked else "success",
        "level": "high" if blocked else "none",
        "reason_codes": ordered_codes,
        "block_standard_prescription": blocked,
    }


def _normalize_text(text: str | None) -> str:
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = normalized.replace("’", "'").replace("‘", "'")
    return " ".join(normalized.split())
