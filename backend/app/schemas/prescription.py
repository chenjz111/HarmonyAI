"""Pydantic schemas for Music Prescription — Agent ③.

Strictly mirrors agent-schemas.md Agent ③ 音乐处方Agent output.
"""
from __future__ import annotations
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class ToneWeight(BaseModel):
    tone_id: str = Field(..., description="jiao / gong / shang / zhi / yu")
    tone_name: str = Field(..., description="角调 / 宫调 / 商调 / 徵调 / 羽调")
    note: str = Field(..., description="Do / Re / Mi / Sol / La")
    element: str
    organ: str
    weight: float = Field(..., ge=0, le=1)
    role: str = Field(..., description="主调 / 辅调")


class Instrument(BaseModel):
    id: str
    name: str
    role: str = Field(..., description="primary / secondary / harmony")
    weight: float = Field(..., ge=0, le=1)


class AmbientSound(BaseModel):
    id: str
    name: str
    volume: float = Field(..., ge=0, le=1)


class DailyPlanEntry(BaseModel):
    day: int
    title: str
    tone_weights: list[ToneWeight]
    strategy: str
    bpm: int
    duration_minutes: int
    instruments: list[Instrument]
    ambient_sound: AmbientSound
    mood: str
    scenario: str


class PromptTemplate(BaseModel):
    template_id: str
    template_version: str
    parameters: dict  # {day, duration, tone_weights, bpm, instruments, ambient, mood, scenario}


class Explanation(BaseModel):
    summary: str
    user_facing: str
    warnings: list[str] = []


# ---------------------------------------------------------------------------
# Request / Response
# ---------------------------------------------------------------------------

class PrescriptionRequest(BaseModel):
    """Request to generate prescription — passes Agent ② output to Agent ③."""
    user_id: str
    session_id: str
    syndrome_diagnosis: dict
    search_keywords: Optional[list[str]] = None
    evidence: Optional[list[dict]] = None


class PrescriptionResponse(BaseModel):
    """Agent ③ output."""
    agent_id: str = "prescription_agent"
    agent_version: str = "1.0.0"
    user_id: str
    session_id: str
    prescription_id: str = Field(..., pattern=r"^rx_\d{8}_\d{3}$")
    daily_plan: list[DailyPlanEntry]
    prompt_template: PromptTemplate
    explanation: Explanation
    confidence: float
    reason: list[str]
    processing_time_ms: int
    timestamp: datetime
