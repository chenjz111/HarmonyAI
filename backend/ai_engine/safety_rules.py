from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
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
    (
        "confusion",
        "SAFETY_ACUTE_CONFUSION",
    ),
    (
        "near_fainting",
        "SAFETY_NEAR_FAINTING",
    ),
    (
        "rapid_worsening",
        "SAFETY_RAPID_WORSENING",
    ),
)

_RISK_PATTERNS = {
    "self_harm_thoughts": (
        re.compile(
            r"(?:正在)?(?:想|要|准备|打算|计划|企图|决定|考虑)(?:要|去)?"
            r"(?:自杀|轻生|死|结束自己的生命|伤害自己|自残)"
        ),
        re.compile(
            r"(?:明确|强烈)?(?:的)?"
            r"(?:自杀|轻生|自残|伤害自己)(?:的)?(?:想法|念头|计划)"
        ),
        re.compile(r"(?:不想活了|结束自己的生命)"),
        re.compile(r"(?:正在|在)(?:自残|伤害自己)"),
        re.compile(
            r"\b(?:kill(?:ing)?|hurt(?:ing)?|harm(?:ing)?)\s+myself\b"
        ),
        re.compile(r"\b(?:am|is|are)\s+self[- ]harming\b"),
        re.compile(r"\b(?:end|take|taking)\s+my\s+own\s+life\b"),
        re.compile(
            r"\b(?:want(?:ing)?|plan(?:ning)?|intend(?:ing)?|"
            r"think(?:ing)?|consider(?:ing)?|feel(?:ing)?)\b"
            r"(?:(?![,，;；]|\b(?:but|however|yet)\b).){0,32}?"
            r"\b(?:die|suicide|suicidal|self[- ]harm)\b"
        ),
        re.compile(
            r"\b(?:suicidal\s+(?:thoughts?|plan)|"
            r"(?:thoughts?|plan)\s+(?:of\s+)?"
            r"(?:suicide|self[- ]harm))\b"
        ),
        re.compile(r"\bsuicide\s+plan\b"),
        re.compile(r"\b(?:don't|do not)\s+want\s+to\s+live\b"),
    ),
    "severe_chest_pain": (
        re.compile(r"(?:严重|剧烈|重度|持续)(?:的)?(?:胸痛|胸口(?:疼痛|痛))"),
        re.compile(
            r"(?:胸痛|胸口(?:疼|痛))[^,，]{0,12}"
            r"(?:剧烈|严重|持续|不缓解|得厉害)"
        ),
        re.compile(r"胸口(?:剧痛|疼得厉害)"),
        re.compile(r"(?:胸口|胸部)(?:一直|持续)(?:疼|痛)"),
        re.compile(
            r"(?:胸痛|胸口(?:疼|痛))[^,，]{0,12}"
            r"(?:\d+|半|[一二两三四五六七八九十数几])(?:个)?"
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
            r"(?:\d+|one|two|three|four|five|several|half(?:\s+an?)?)\s+"
            r"(?:minutes?|hours?|days?)\b"
        ),
        re.compile(
            r"\bchest pain\b.{0,16}\bfor\s+"
            r"(?:\d+|one|two|three|four|five|several|half(?:\s+an?)?)\s+"
            r"(?:minutes?|hours?|days?)\b"
        ),
    ),
    "severe_breathing_difficulty": (
        re.compile(r"(?:明显|严重)(?:的)?呼吸困难"),
        re.compile(r"呼吸(?:很|非常|十分|极其)困难"),
        re.compile(r"(?:喘不上气|无法呼吸|不能呼吸|快(?:要)?窒息)"),
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
            r"\b(?:(?:cannot|can't|unable to|can barely|struggling to)\s+breathe|"
            r"gasping for air)\b"
        ),
        re.compile(r"\btoo\s+breathless\s+to\s+speak\b"),
        re.compile(
            r"\b(?:shortness of breath|breathlessness).{0,20}"
            r"(?:cannot|can't|unable).{0,10}\bspeak\b"
        ),
    ),
    "confusion": (),
    "near_fainting": (),
    "rapid_worsening": (),
}

_CLAUSE_SPLIT_RE = re.compile(r"[。.!?！？;\n]+")
_CHINESE_NEGATION_RE = re.compile(
    r"(?:没有|没|不|无|未见|否认(?:有)?)(?:任何)?\s*$"
)
_ENGLISH_NEGATION_RE = re.compile(
    r"(?:\b(?:no|not|never|deny|denies|denied|without)\b"
    r"(?:\s+having)?|\b(?:do|does|did)\s+not|\bdon't)\s*$"
)
_CONDITIONAL_PREFIX_RE = re.compile(
    r"(?:\bif\b|如果|如(?:果)?(?:出现)?|若(?:出现)?)"
)
_GUIDANCE_RE = re.compile(
    r"(?:请.{0,8}(?:就医|急救)|立即就医|"
    r"\bseek\s+(?:urgent|medical)\s+care\b|"
    r"\burgent\s+care\b|\bcall\s+911\b|拨打\s*120)"
)
_INTERNAL_NEGATION_RE = re.compile(
    r"(?:胸痛|胸口(?:疼|痛))[^,，]{0,6}(?:不|并不)(?:严重|剧烈)"
)
_CHINESE_PAST_RE = re.compile(r"(?:曾经|以前|过去)")
_CHINESE_RESOLVED_RE = re.compile(
    r"(?:但|不过)?(?:现在|目前).{0,10}"
    r"(?:已无|不再|没有|已没有|已经没有).{0,8}"
    r"(?:这种想法|自杀(?:想法|念头|计划)|轻生(?:想法|念头)|"
    r"自残(?:想法|念头)|伤害自己的想法)"
)
_ENGLISH_PAST_RE = re.compile(
    r"\b(?:in the past|previously|formerly|used to)\b"
)
_ENGLISH_RESOLVED_RE = re.compile(
    r"\b(?:"
    r"no longer\s+(?:do|have\s+(?:those|these)\s+thoughts?|"
    r"(?:am|feel)\s+suicidal)|"
    r"(?:am|feel)\s+not\s+suicidal\s+anymore"
    r")\b"
)

_ALLOWED_REASON_CODES = tuple(reason_code for _, reason_code in _RULES)
_ALLOWED_QUESTIONNAIRE_FLAGS = frozenset(flag for flag, _ in _RULES)


@dataclass(frozen=True)
class _ClauseContext:
    conditional_starts: tuple[int, ...]
    has_guidance: bool
    chinese_past_ends: tuple[int, ...]
    chinese_resolved_starts: tuple[int, ...]
    english_past_starts: tuple[int, ...]
    english_resolved_starts: tuple[int, ...]


def evaluate_safety(
    narrative_text: str | None = None,
    confirmed_ocr_text: str | None = None,
    questionnaire_safety_flags: list[str] | tuple[str, ...] | None = None,
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


_MENTAL_HEALTH_FLAGS = frozenset({"self_harm_thoughts"})
_ACUTE_PHYSICAL_FLAGS = frozenset(
    {
        "severe_chest_pain",
        "severe_breathing_difficulty",
        "confusion",
        "near_fainting",
        "rapid_worsening",
    }
)


def detect_safety_signals(
    narrative_text: str | None = None,
    confirmed_ocr_text: str | None = None,
    questionnaire_safety_flags: list[str] | tuple[str, ...] | None = None,
) -> list[dict[str, object]]:
    """Detect source-labelled safety signals without logging source text."""
    selected_flags = _validate_questionnaire_safety_flags(
        questionnaire_safety_flags
    )
    sources = (
        (
            "questionnaire",
            tuple(
                flag
                for flag, _ in _RULES
                if flag in selected_flags
            ),
            1.0,
            "current",
            "user",
            "confirmed",
        ),
        (
            "user_narrative",
            tuple(
                flag
                for flag, _ in _RULES
                if _text_matches_rule(_normalize_text(narrative_text), flag)
            ),
            0.95,
            "current",
            "user",
            "confirmed",
        ),
        (
            "ocr_document",
            tuple(
                flag
                for flag, _ in _RULES
                if _text_matches_rule(_normalize_text(confirmed_ocr_text), flag)
            ),
            0.8,
            "unknown",
            "unknown",
            "pending",
        ),
    )
    return [
        {
            "signal_id": f"safety-{source}-{flag}",
            "type": flag,
            "source": source,
            "confidence": confidence,
            "temporal_context": temporal_context,
            "subject_context": subject_context,
            "verification_status": verification_status,
        }
        for (
            source,
            flags,
            confidence,
            temporal_context,
            subject_context,
            verification_status,
        ) in sources
        for flag in flags
    ]


def decide_safety_state(
    signals: Sequence[dict[str, object]],
) -> dict[str, object]:
    """Turn detected signals into an explicit workflow state."""
    confirmed_flags = {
        str(signal.get("type"))
        for signal in signals
        if signal.get("verification_status") == "confirmed"
    }
    pending = any(
        signal.get("verification_status") == "pending"
        for signal in signals
    )
    if confirmed_flags.intersection(_ACUTE_PHYSICAL_FLAGS):
        safety_status = "confirmed_acute_physical_risk"
    elif confirmed_flags.intersection(_MENTAL_HEALTH_FLAGS):
        safety_status = "confirmed_mental_health_risk"
    elif pending:
        safety_status = "needs_verification"
    else:
        safety_status = "clear"

    blocked = safety_status != "clear"
    return {
        "safety_status": safety_status,
        "requires_safety_verification": safety_status == "needs_verification",
        "personalized_prescription_allowed": not blocked,
        "comfort_audio_allowed": safety_status
        == "confirmed_mental_health_risk",
    }


def evaluate_safety_state(
    narrative_text: str | None = None,
    confirmed_ocr_text: str | None = None,
    questionnaire_safety_flags: list[str] | tuple[str, ...] | None = None,
) -> dict[str, object]:
    """Separate source-aware detection from the workflow safety decision."""
    signals = detect_safety_signals(
        narrative_text=narrative_text,
        confirmed_ocr_text=confirmed_ocr_text,
        questionnaire_safety_flags=questionnaire_safety_flags,
    )
    decision = decide_safety_state(signals)
    flags = [
        flag
        for flag, _ in _RULES
        if any(signal.get("type") == flag for signal in signals)
    ]
    reason_by_flag = dict(_RULES)
    blocked = decision["safety_status"] != "clear"
    return {
        "status": "blocked_safety" if blocked else "success",
        "level": "high" if blocked else "none",
        "flags": flags,
        "reason_codes": [reason_by_flag[flag] for flag in flags],
        "block_standard_prescription": blocked,
        "signals": signals,
        **decision,
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
    flags: list[str] | tuple[str, ...] | None,
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
        context = _build_clause_context(clause)
        for pattern in _RISK_PATTERNS[flag]:
            for candidate in pattern.finditer(clause):
                if not _candidate_is_excluded(
                    flag,
                    clause,
                    candidate,
                    context,
                ):
                    return True
    return False


def _build_clause_context(clause: str) -> _ClauseContext:
    return _ClauseContext(
        conditional_starts=tuple(
            match.start()
            for match in _CONDITIONAL_PREFIX_RE.finditer(clause)
        ),
        has_guidance=bool(_GUIDANCE_RE.search(clause)),
        chinese_past_ends=tuple(
            match.end()
            for match in _CHINESE_PAST_RE.finditer(clause)
        ),
        chinese_resolved_starts=tuple(
            match.start()
            for match in _CHINESE_RESOLVED_RE.finditer(clause)
        ),
        english_past_starts=tuple(
            match.start()
            for match in _ENGLISH_PAST_RE.finditer(clause)
        ),
        english_resolved_starts=tuple(
            match.start()
            for match in _ENGLISH_RESOLVED_RE.finditer(clause)
        ),
    )


def _candidate_is_excluded(
    flag: str,
    clause: str,
    candidate: re.Match[str],
    context: _ClauseContext,
) -> bool:
    candidate_start = candidate.start()
    local_start, nearby_prefix = _local_context(
        clause,
        candidate_start,
    )
    if (
        context.has_guidance
        and _has_position_between(
            context.conditional_starts,
            local_start,
            candidate_start,
        )
    ):
        return True

    if (
        _CHINESE_NEGATION_RE.search(nearby_prefix)
        or _ENGLISH_NEGATION_RE.search(nearby_prefix)
        or _INTERNAL_NEGATION_RE.search(candidate.group())
    ):
        return True

    return flag == "self_harm_thoughts" and _is_resolved_history(
        candidate,
        context,
    )


def _local_context(
    clause: str,
    candidate_start: int,
) -> tuple[int, str]:
    window_start = max(0, candidate_start - 48)
    delimiter_index = max(
        clause.rfind(",", window_start, candidate_start),
        clause.rfind("，", window_start, candidate_start),
    )
    local_start = max(window_start, delimiter_index + 1)
    return local_start, clause[local_start:candidate_start]


def _has_position_between(
    positions: tuple[int, ...],
    start: int,
    end: int,
) -> bool:
    index = bisect_left(positions, start)
    return index < len(positions) and positions[index] < end


def _is_resolved_history(
    candidate: re.Match[str],
    context: _ClauseContext,
) -> bool:
    chinese_resolution_index = bisect_left(
        context.chinese_resolved_starts,
        candidate.end(),
    )
    chinese_resolved = (
        bisect_right(context.chinese_past_ends, candidate.start()) > 0
        and chinese_resolution_index
        < len(context.chinese_resolved_starts)
    )

    english_resolution_index = bisect_left(
        context.english_resolved_starts,
        candidate.end(),
    )
    english_resolved = False
    if english_resolution_index < len(context.english_resolved_starts):
        resolution_start = context.english_resolved_starts[
            english_resolution_index
        ]
        english_resolved = bool(
            context.english_past_starts
            and context.english_past_starts[0] < resolution_start
        )
    return bool(chinese_resolved or english_resolved)
