"""Pydantic schemas for Music Generation — Agent ④.

Strictly mirrors agent-schemas.md Agent ④ 音乐生成Agent output.
"""
from __future__ import annotations
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class Audio(BaseModel):
    url: Optional[str] = None
    duration_seconds: Optional[int] = None
    file_size_bytes: Optional[int] = None
    format: str = "mp3"
    bitrate_kbps: Optional[int] = None


class InstrumentUsed(BaseModel):
    id: str
    name: str


class ActualParams(BaseModel):
    bpm: int
    instruments_used: list[InstrumentUsed]
    prompt_template_used: str
    prompt_sent: Optional[str] = None
    prompt_truncated: bool = False


class Provider(BaseModel):
    name: str = Field(..., description="skymusic / musicmini / funmusic / local")
    attempt_order: int = 1
    retry_count: int = 0
    degradation_triggered: bool = False
    api_response_time_ms: int
    cost_cny: float = 0.0


class DegradationLogEntry(BaseModel):
    attempt: int
    provider: str
    status: str = Field(..., description="success / failed / degraded")
    latency_ms: int


# ---------------------------------------------------------------------------
# Request / Response
# ---------------------------------------------------------------------------

class GenerationRequest(BaseModel):
    """Request to generate music — passes Agent ③ daily_plan[day] to Agent ④."""
    user_id: str
    session_id: str
    prescription_id: str
    day: int = Field(..., ge=1, le=30)
    daily_plan_entry: dict
    prompt_template: dict


class GenerationResponse(BaseModel):
    """Agent ④ output."""
    agent_id: str = "generation_agent"
    agent_version: str = "1.0.0"
    user_id: str
    session_id: str
    prescription_id: str
    day: int
    audio: Audio
    actual_params: ActualParams
    provider: Provider
    degradation_log: list[DegradationLogEntry]
    confidence: float
    reason: list[str]
    processing_time_ms: int
    timestamp: datetime
