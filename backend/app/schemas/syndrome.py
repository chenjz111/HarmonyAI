"""Pydantic schemas for Syndrome Diagnosis — Agent ②.

Strictly mirrors agent-schemas.md Agent ② 中医辨证Agent output.
"""
from __future__ import annotations
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class PrimarySyndrome(BaseModel):
    name: str = Field(..., description="证型名，如'肝郁化火'")
    element: str = Field(..., description="五行: 木/火/土/金/水")
    organ: str = Field(..., description="五脏: 肝/心/脾/肺/肾")
    emotion: str = Field(..., description="对应情绪")
    severity_level: int = Field(..., ge=1, le=5)
    severity_name: str = Field(..., description="轻度/中度/重度")


class SecondarySyndrome(BaseModel):
    name: str
    element: str
    organ: str
    emotion: str
    severity_level: int = Field(..., ge=1, le=5)
    severity_name: str


class SyndromeDiagnosis(BaseModel):
    primary: PrimarySyndrome
    secondary: list[SecondarySyndrome] = []


class ConfidenceBreakdown(BaseModel):
    rule_engine_match: float = Field(..., alias="rule_engine_match")
    llm_confidence: float = Field(..., alias="llm_confidence")
    literature_support: float = Field(..., alias="literature_support")

    model_config = {"populate_by_name": True}


class SyndromeConfidence(BaseModel):
    overall: float
    breakdown: ConfidenceBreakdown


class Evidence(BaseModel):
    source: str
    excerpt: str
    relevance: str = Field(..., description="high / medium / low")


class Warnings(BaseModel):
    low_confidence: bool = False
    conflicting_signals: bool = False
    recommend_professional: bool = False


# ---------------------------------------------------------------------------
# Request / Response
# ---------------------------------------------------------------------------

class SyndromeRequest(BaseModel):
    """Request to trigger diagnosis — passes Agent ① output to Agent ②."""
    user_id: str
    session_id: str
    assessment_id: Optional[int] = None
    health_profile: dict  # full Agent ① health_profile
    term_mapping: Optional[list[dict]] = None


class SyndromeResponse(BaseModel):
    """Agent ② output."""
    agent_id: str = "diagnosis_agent"
    agent_version: str = "1.0.0"
    user_id: str
    session_id: str
    syndrome_diagnosis: SyndromeDiagnosis
    confidence: SyndromeConfidence
    evidence: list[Evidence]
    search_keywords: list[str]
    warnings: Warnings
    reason: list[str]
    processing_time_ms: int
    timestamp: datetime
