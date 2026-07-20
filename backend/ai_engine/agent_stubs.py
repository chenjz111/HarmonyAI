"""Deterministic Sprint 2 Agent stubs for the Day 4 integration demo."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .prompt_engine import PromptEngine


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


def diagnosis_stub(state: dict[str, Any]) -> dict[str, object]:
    """Return a schema-shaped diagnosis based on the assessment stub."""
    assessment = dict(state["assessment"])
    confidence = float(assessment["confidence"])
    envelope = make_agent_result(
        agent_id="diagnosis_agent",
        agent_name="辨证Agent",
        agent_layer="medical_analysis",
        run_id=str(state["run_id"]),
        session_id=str(state["session_id"]),
        user_id=str(state["user_id"]),
        status="success" if confidence >= 0.4 else "degraded",
        confidence=confidence,
        reason=["stub：焦虑情绪映射为肝郁化火"],
        warnings=[] if confidence >= 0.4 else ["上游输入可信度不足"],
        input_data={"assessment": assessment["output"]},
        output_data={
            "syndrome_diagnosis": {
                "primary": {
                    "name": "肝郁化火",
                    "element": "木",
                    "organ": "肝",
                    "severity_level": 3,
                    "severity_name": "中度",
                }
            },
            "search_keywords": ["肝郁化火", "角调", "疏肝解郁"],
        },
    )
    return {"diagnosis": envelope}


def prescription_stub(state: dict[str, Any]) -> dict[str, object]:
    """Create a deterministic music prescription and render the existing prompt."""
    diagnosis = dict(state["diagnosis"])
    root = Path(__file__).resolve().parents[2]
    prompt = PromptEngine(root / "prompt" / "v1").render(
        "CN_V1",
        {"duration": 15, "bpm": 68, "tone": "角调式", "style": "中国民族风纯音乐"},
    )
    envelope = make_agent_result(
        agent_id="prescription_agent",
        agent_name="处方Agent",
        agent_layer="knowledge_mapping",
        run_id=str(state["run_id"]),
        session_id=str(state["session_id"]),
        user_id=str(state["user_id"]),
        status="success",
        confidence=float(diagnosis["confidence"]),
        reason=["stub：肝郁化火对应角调、68 BPM 与古筝"],
        warnings=[],
        input_data={"diagnosis": diagnosis["output"]},
        output_data={
            "music_feature": {
                "tone_id": "jiao",
                "tone_name": "角调式",
                "bpm": 68,
                "instruments": ["古筝", "古琴"],
            },
            "prompt_template": {
                "template_id": prompt.template_id,
                "template_version": prompt.template_version,
                "parameters": {"duration": 15, "bpm": 68, "tone": "角调式"},
            },
            "rendered_prompt": prompt.text,
        },
    )
    return {"prescription": envelope}


def generation_stub(state: dict[str, Any]) -> dict[str, object]:
    """Return a local sample-audio reference instead of calling a music API."""
    prescription = dict(state["prescription"])
    envelope = make_agent_result(
        agent_id="generation_agent",
        agent_name="生成Agent",
        agent_layer="ai_generation",
        run_id=str(state["run_id"]),
        session_id=str(state["session_id"]),
        user_id=str(state["user_id"]),
        status="degraded",
        confidence=float(prescription["confidence"]),
        reason=["stub：使用本地曲库示例音频，未调用外部生成服务"],
        warnings=["当前为 Sprint 2 本地曲库 stub"],
        input_data={"prescription": prescription["output"]},
        output_data={"audio": {"url": "local://music/jiao-demo.mp3", "format": "mp3"}},
    )
    return {"generation": envelope}


def feedback_stub(state: dict[str, Any]) -> dict[str, object]:
    """Return a minimal successful feedback decision for the demo loop."""
    generation = dict(state["generation"])
    envelope = make_agent_result(
        agent_id="feedback_agent",
        agent_name="反馈Agent",
        agent_layer="ai_generation",
        run_id=str(state["run_id"]),
        session_id=str(state["session_id"]),
        user_id=str(state["user_id"]),
        status="success",
        confidence=0.8,
        reason=["stub：示例满意度为 4 分，继续当前方案"],
        warnings=[],
        input_data={"audio": generation["output"]["audio"]},
        output_data={"decision": {"action": "continue", "next_step": "push_next_day"}},
    )
    return {"feedback": envelope}
