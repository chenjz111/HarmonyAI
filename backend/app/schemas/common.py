"""Universal Shell — agent-architecture.md Chapter 1.

Every Agent input/output MUST follow this structure.
"""
from __future__ import annotations
from typing import Optional, Any
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Status enum (Chapter 2.1)
# ---------------------------------------------------------------------------
class AgentStatus(str, Enum):
    READY = "ready"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    DEGRADED = "degraded"
    RETRY = "retry"
    SKIPPED = "skipped"


# Agent layer (Chapter 1.3)
class AgentLayer(str, Enum):
    MEDICAL_ANALYSIS = "medical_analysis"
    KNOWLEDGE_MAPPING = "knowledge_mapping"
    AI_GENERATION = "ai_generation"


# ---------------------------------------------------------------------------
# Warning object
# ---------------------------------------------------------------------------
class WarningInfo(BaseModel):
    code: str = Field(..., description="Warning code, e.g. UPSTREAM_DEGRADED")
    message: str = Field(..., description="Human-readable warning")


# ---------------------------------------------------------------------------
# Universal output fields (every Agent response includes these)
# ---------------------------------------------------------------------------
class UniversalOutput(BaseModel):
    """Base for all Agent responses — agent-architecture.md §1.2"""
    agent_id: str = Field(..., description="Agent unique ID, e.g. 'assessment_agent'")
    agent_version: str = Field(default="1.0.0")
    agent_name: str = Field(..., description="Chinese name for frontend display")
    agent_layer: AgentLayer

    run_id: str = Field(..., description="Unique run ID: run_YYYYMMDD_NNN_agent")
    session_id: str
    user_id: str

    status: AgentStatus
    confidence: float = Field(..., ge=0, le=1)
    reason: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    input: Optional[dict] = Field(None, description="Input snapshot")
    output: Optional[dict] = Field(None, description="Output data per agent-schemas.md")

    processing_time_ms: int = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    retry_count: int = 0

    # Upstream degradation propagation (Chapter 3.3)
    upstream_degraded: bool = False
    upstream_warnings: list[str] = Field(default_factory=list)

    # Sprint 2: real-agent degradation flag
    degradation_triggered: bool = Field(default=False, description="Set when any agent degrades to rule fallback")


def make_run_id(agent: str) -> str:
    """Generate a unique run ID."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    import random
    n = random.randint(100, 999)
    return f"run_{ts}_{agent}_{n}"
