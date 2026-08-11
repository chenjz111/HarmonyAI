"""Log sanitization — Sprint 4: never log patient data.

Blocks: narrative, document text, OCR full text, questionnaire free-text.
Allows: session_id, agent_id, status, confidence, latency_ms.
"""
from __future__ import annotations
import re

SENSITIVE_FIELDS = [
    "narrative_text", "narrative",
    "document_text", "ocr_text", "extracted_text",
    "questionnaire", "comment", "text_feedback",
    "original_diagnosis", "medical_history",
    "free_text", "answer",
]


def sanitize_log(data: dict | str, max_len: int = 100) -> str:
    """Return a log-safe string with sensitive values replaced."""
    if isinstance(data, str):
        return "[REDACTED]"

    safe = {}
    for k, v in data.items():
        if k in SENSITIVE_FIELDS:
            safe[k] = f"[REDACTED:{len(str(v))}chars]"
        elif isinstance(v, dict):
            safe[k] = sanitize_log(v, max_len)
        elif isinstance(v, list):
            safe[k] = f"[list:{len(v)}items]"
        else:
            s = str(v)
            safe[k] = s[:max_len]
    return str(safe)
