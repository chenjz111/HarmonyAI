"""Pydantic schema for Qwen narrative text analysis output.

Validates structured extraction from user free-text input.
The model MUST NOT output medical diagnoses or TCM syndrome labels.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class LifeEvent(BaseModel):
    description: str = Field(..., description="Brief description of the event")
    timeframe: str = Field(default="recent", description="When it happened: today/recent/past")


class EmotionSignal(BaseModel):
    emotion: str = Field(..., description="Detected emotion label (anxiety/depression/anger/fear/overthinking/fatigue/grief/insomnia)")
    intensity: int = Field(..., ge=0, le=100, description="Intensity score 0-100")
    evidence: str = Field(..., description="Quote or paraphrase from user text supporting this")


class PhysicalSignal(BaseModel):
    symptom: str = Field(..., description="Physical symptom described")
    severity: str = Field(default="moderate", description="mild/moderate/severe")
    evidence: str = Field(default="", description="Supporting text from user")


class NarrativeAnalysis(BaseModel):
    """Structured output from Qwen after analyzing user free-text.

    The model is instructed NOT to output medical diagnoses or TCM labels.
    This output feeds into the existing AssessmentAgent pipeline, not Diagnosis directly.

    At minimum, 'summary' and 'evidence' must be non-empty strings to pass validation.
    """
    model_config = {"extra": "ignore"}

    life_events: list[LifeEvent] = Field(default_factory=list)
    emotion_signals: list[EmotionSignal] = Field(default_factory=list, min_length=1)
    physical_signals: list[PhysicalSignal] = Field(default_factory=list)
    evidence: str = Field(..., min_length=1, description="Key phrases from user text supporting the analysis")
    summary: str = Field(..., min_length=1, description="One-sentence summary of user's state, in user's own framing")
    needs_confirmation: bool = Field(default=False)


# ---------------------------------------------------------------------------
# Prompt template for narrative extraction
# ---------------------------------------------------------------------------
NARRATIVE_SYSTEM_PROMPT = (
    "You are a clinical intake assistant. Analyze the user's free-text description "
    "of recent experiences. Extract ONLY factual observations — do NOT diagnose, "
    "do NOT assign TCM syndromes, do NOT suggest treatments. "
    "Return JSON with these fields:\n"
    "- life_events: list of {description, timeframe (today/recent/past)}\n"
    "- emotion_signals: list of {emotion, intensity (0-100), evidence}\n"
    "  (emotion must be one of: anxiety, depression, anger, fear, overthinking, fatigue, grief, insomnia)\n"
    "- physical_signals: list of {symptom, severity (mild/moderate/severe), evidence}\n"
    "- evidence: key phrases from user text\n"
    "- summary: one-sentence neutral summary\n"
    "- needs_confirmation: true/false\n"
    "If the text describes self-harm or immediate danger to self/others, "
    "set a field called safety_alert to true and set summary to 'recommend_professional_help'. "
    "Return ONLY valid JSON, no explanation."
)


# ---------------------------------------------------------------------------
# Safety constants
# ---------------------------------------------------------------------------
SAFETY_KEYWORDS = [
    "不想活", "自杀", "结束生命", "自残", "伤害自己", "不想活了",
    "kill myself", "self-harm", "suicide", "end my life",
]

MAX_NARRATIVE_LENGTH = 1000  # chars


def check_safety_alert(text: str) -> bool:
    """Check if free text contains potential self-harm keywords."""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in SAFETY_KEYWORDS)


def sanitize_narrative(text: str | None) -> str | None:
    """Trim whitespace and cap length. Return None for empty/whitespace-only strings."""
    if text is None:
        return None
    cleaned = text.strip()
    if not cleaned:
        return None
    return cleaned[:MAX_NARRATIVE_LENGTH]
