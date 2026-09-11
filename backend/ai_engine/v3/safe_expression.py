"""Guards for text that may cross the public V3.1 boundary."""

from __future__ import annotations

import re


class UnsafePublicExpression(ValueError):
    """Raised when text contains medical certainty or internal details."""


_FORBIDDEN_PATTERNS = (
    re.compile(r"\b(?:provider|model|prompt|completion|raw\s+rag)\b", re.IGNORECASE),
    re.compile(
        r"(?:你的|您|当前状态|本次|患者).{0,12}(?:证型|辨证|诊断|确诊|病因|病症|syndrome|diagnos(?:is|ed)|是|属于)",
        re.IGNORECASE,
    ),
    re.compile(r"(?:治愈|治疗|处方|prescription|treatment|cure)", re.IGNORECASE),
)


def validate_public_text(text: str) -> str:
    """Return bounded public text or reject internal/overclaiming wording."""

    if not isinstance(text, str) or not text.strip():
        raise UnsafePublicExpression("public text must be non-empty")
    value = text.strip()
    if any(pattern.search(value) for pattern in _FORBIDDEN_PATTERNS):
        raise UnsafePublicExpression("public text contains forbidden internal or medical certainty wording")
    return value
