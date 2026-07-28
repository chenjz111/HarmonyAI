from __future__ import annotations

from collections.abc import Sequence
import re
import unicodedata


_RULES = (
    (
        "self_harm_thoughts",
        "SAFETY_SELF_HARM_OR_SUICIDE",
    ),
    (
        "severe_chest_pain",
        "SAFETY_SEVERE_OR_PERSISTENT_CHEST_PAIN",
    ),
    (
        "severe_breathing_difficulty",
        "SAFETY_SEVERE_BREATHING_DIFFICULTY",
    ),
)

_RISK_PATTERNS = {
    "self_harm_thoughts": (
        re.compile(
            r"(?:想|要|准备|打算|计划|企图|决定)(?:要|去)?"
            r"(?:自杀|轻生|死|结束自己的生命|伤害自己|自残)"
        ),
        re.compile(
            r"(?:明确|强烈)?(?:的)?"
            r"(?:自杀|轻生|自残|伤害自己)(?:的)?(?:想法|念头|计划)"
        ),
        re.compile(r"(?:不想活了|结束自己的生命)"),
        re.compile(
            r"\b(?:kill(?:ing)?|hurt(?:ing)?|harm(?:ing)?)\s+myself\b"
        ),
        re.compile(r"\b(?:end|take|taking)\s+my\s+own\s+life\b"),
        re.compile(
            r"\b(?:want(?:ing)?|plan(?:ning)?|intend(?:ing)?|"
            r"think(?:ing)?|consider(?:ing)?|feel(?:ing)?)\b"
            r".{0,32}\b(?:die|suicide|suicidal|self[- ]harm)\b"
        ),
        re.compile(
            r"\b(?:suicidal\s+(?:thoughts?|plan)|"
            r"(?:thoughts?|plan)\s+(?:of\s+)?"
            r"(?:suicide|self[- ]harm))\b"
        ),
        re.compile(r"\b(?:don't|do not)\s+want\s+to\s+live\b"),
    ),
    "severe_chest_pain": (
        re.compile(r"(?:严重|剧烈|重度|持续)(?:的)?(?:胸痛|胸口(?:疼痛|痛))"),
        re.compile(
            r"(?:胸痛|胸口(?:疼|痛))[^,，]{0,12}"
            r"(?:剧烈|严重|持续|不缓解|得厉害)"
        ),
        re.compile(r"胸口(?:剧痛|疼得厉害)"),
        re.compile(
            r"(?:胸痛|胸口(?:疼|痛))[^,，]{0,12}"
            r"(?:\d+|[一二两三四五六七八九十数几])(?:个)?"
            r"(?:分钟|小时|天)"
        ),
        re.compile(r"\b(?:severe|intense|crushing|persistent)\s+chest pain\b"),
        re.compile(
            r"\bchest pain\b.{0,24}\b"
            r"(?:last(?:ed|ing)?|persist(?:ed|ing)?|"
            r"won't go away|will not go away)\b"
        ),
        re.compile(
            r"\b(?:have|has|had)\s+(?:had\s+)?chest pain\s+for\s+"
            r"(?:\d+|one|two|three|four|five|several)\s+"
            r"(?:minutes?|hours?|days?)\b"
        ),
        re.compile(
            r"\bchest pain\b.{0,16}\bfor\s+"
            r"(?:\d+|one|two|three|four|five|several)\s+"
            r"(?:minutes?|hours?|days?)\b"
        ),
    ),
    "severe_breathing_difficulty": (
        re.compile(r"(?:明显|严重)(?:的)?呼吸困难"),
        re.compile(r"呼吸(?:非常|十分|极其)困难"),
        re.compile(r"(?:喘不上气|无法呼吸|快(?:要)?窒息)"),
        re.compile(
            r"(?:呼吸困难|气短).{0,20}"
            r"(?:(?:说不出|无法说).{0,8}(?:完整)?(?:的)?话|"
            r"(?:一?句)?(?:完整)?(?:的)?话.{0,6}说不出来)"
        ),
        re.compile(
            r"\b(?:severe|extreme|marked)\s+"
            r"(?:difficulty breathing|shortness of breath|breathlessness)\b"
        ),
        re.compile(
            r"\b(?:(?:cannot|can't|struggling to)\s+breathe|gasping for air)\b"
        ),
        re.compile(r"\btoo\s+breathless\s+to\s+speak\b"),
        re.compile(
            r"\b(?:shortness of breath|breathlessness).{0,20}"
            r"(?:cannot|can't|unable).{0,10}\bspeak\b"
        ),
    ),
}

_CLAUSE_SPLIT_RE = re.compile(r"[。.!?！？;\n]+")
_CHINESE_NEGATION_RE = re.compile(r"(?:没有|没|不|无|未见|否认)(?:任何)?\s*$")
_ENGLISH_NEGATION_RE = re.compile(
    r"(?:\b(?:no|not|never|deny|denies|denied|without)\b|"
    r"\b(?:do|does|did)\s+not)\s*$"
)
_CONDITIONAL_PREFIX_RE = re.compile(
    r"(?:\bif\b|如果|如(?:果)?出现|若(?:出现)?)"
)
_GUIDANCE_RE = re.compile(
    r"(?:请.{0,8}(?:就医|急救)|立即就医|"
    r"\bseek\s+(?:urgent|medical)\s+care\b|"
    r"\burgent\s+care\b)"
)
_CHINESE_PAST_RE = re.compile(r"(?:曾经|以前|过去)")
_CHINESE_RESOLVED_RE = re.compile(
    r"(?:但|不过)?(?:现在|目前).{0,10}"
    r"(?:已无|不再|没有|已没有|已经没有)"
)
_ENGLISH_PAST_RE = re.compile(
    r"\b(?:in the past|previously|formerly|used to)\b"
)
_ENGLISH_RESOLVED_RE = re.compile(r"\b(?:no longer|not anymore)\b")

_ALLOWED_REASON_CODES = tuple(reason_code for _, reason_code in _RULES)
_ALLOWED_QUESTIONNAIRE_FLAGS = frozenset(flag for flag, _ in _RULES)


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
    selected_questionnaire_flags = _validate_questionnaire_safety_flags(
        questionnaire_safety_flags
    )

    matched = [
        (flag, reason_code)
        for flag, reason_code in _RULES
        if flag in selected_questionnaire_flags
        or any(
            _text_matches_rule(text, flag)
            for text in normalized_texts
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
    normalized = re.sub(r"[^\S\n]+", " ", normalized)
    normalized = re.sub(r"\n+", "\n", normalized)
    return normalized.strip()


def _validate_questionnaire_safety_flags(
    flags: Sequence[str] | None,
) -> set[str]:
    if flags is None:
        return set()
    if not isinstance(flags, (list, tuple)) or any(
        not isinstance(flag, str) or flag not in _ALLOWED_QUESTIONNAIRE_FLAGS
        for flag in flags
    ):
        raise ValueError("invalid questionnaire safety flags")
    return set(flags)


def _text_matches_rule(text: str, flag: str) -> bool:
    for clause in _CLAUSE_SPLIT_RE.split(text):
        clause = clause.strip()
        if not clause:
            continue
        for pattern in _RISK_PATTERNS[flag]:
            for candidate in pattern.finditer(clause):
                if not _candidate_is_excluded(flag, clause, candidate):
                    return True
    return False


def _candidate_is_excluded(
    flag: str,
    clause: str,
    candidate: re.Match[str],
) -> bool:
    prefix = clause[:candidate.start()]
    local_prefix = re.split(r"[,，]", prefix)[-1]
    if (
        _CONDITIONAL_PREFIX_RE.search(local_prefix)
        and _GUIDANCE_RE.search(clause)
    ):
        return True

    nearby_prefix = local_prefix[-32:]
    if (
        _CHINESE_NEGATION_RE.search(nearby_prefix)
        or _ENGLISH_NEGATION_RE.search(nearby_prefix)
    ):
        return True

    return flag == "self_harm_thoughts" and _is_resolved_history(
        clause,
        candidate,
    )


def _is_resolved_history(
    clause: str,
    candidate: re.Match[str],
) -> bool:
    prefix = clause[:candidate.start()]
    suffix = clause[candidate.end():]
    chinese_resolved = (
        _CHINESE_PAST_RE.search(prefix)
        and _CHINESE_RESOLVED_RE.search(suffix)
    )
    english_resolved = (
        _ENGLISH_PAST_RE.search(clause)
        and _ENGLISH_RESOLVED_RE.search(suffix)
    )
    return bool(chinese_resolved or english_resolved)
