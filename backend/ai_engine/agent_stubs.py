"""Deterministic Sprint 2 Agent stubs for the Day 4 integration demo."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def make_agent_result(
    *,
    agent_id: str,
    agent_name: str,
    agent_layer: str,
    run_id: str,
    session_id: str,
    user_id: str,
    status: str,
    confidence: float,
    reason: list[str],
    warnings: list[str],
    input_data: dict[str, object],
    output_data: dict[str, object],
) -> dict[str, object]:
    """Build the universal result envelope required by Agent Architecture."""
    return {
        "agent_id": agent_id,
        "agent_version": "1.0.0",
        "agent_name": agent_name,
        "agent_layer": agent_layer,
        "run_id": run_id,
        "session_id": session_id,
        "user_id": user_id,
        "status": status,
        "confidence": confidence,
        "reason": reason,
        "warnings": warnings,
        "input": input_data,
        "output": output_data,
        "processing_time_ms": 0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "retry_count": 0,
    }


def assessment_stub(state: dict[str, Any]) -> dict[str, object]:
    """Create a deterministic assessment result from supplied emotion scores."""
    emotion_scores = dict(state.get("emotion_scores", {}))
    has_input = bool(emotion_scores)
    envelope = make_agent_result(
        agent_id="evaluation_agent",
        agent_name="评估Agent",
        agent_layer="medical_analysis",
        run_id=str(state["run_id"]),
        session_id=str(state["session_id"]),
        user_id=str(state["user_id"]),
        status="success" if has_input else "degraded",
        confidence=0.85 if has_input else 0.3,
        reason=["stub：使用提交的情绪评分"] if has_input else ["stub：输入为空，使用保守降级结果"],
        warnings=[] if has_input else ["输入不足，建议补充问卷"],
        input_data={"emotion_scores": emotion_scores},
        output_data={"emotion_profile": emotion_scores},
    )
    return {"assessment": envelope}
