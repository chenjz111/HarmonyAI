"""LangGraph orchestration for the deterministic Sprint 2 Agent stubs."""

from __future__ import annotations

from typing import NotRequired, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from .agent_stubs import (
    assessment_stub,
    diagnosis_stub,
    feedback_stub,
    generation_stub,
    make_agent_result,
    prescription_stub,
)


class StubWorkflowState(TypedDict):
    run_id: str
    session_id: str
    user_id: str
    emotion_scores: dict[str, int]
    assessment: NotRequired[dict[str, object]]
    diagnosis: NotRequired[dict[str, object]]
    prescription: NotRequired[dict[str, object]]
    generation: NotRequired[dict[str, object]]
    feedback: NotRequired[dict[str, object]]
    low_confidence: NotRequired[dict[str, object]]


def low_confidence_handler(state: StubWorkflowState) -> dict[str, object]:
    """Stop the clinical path and request professional review safely."""
    diagnosis = dict(state["diagnosis"])
    return {
        "low_confidence": make_agent_result(
            agent_id="low_confidence_handler",
            agent_name="低可信度处理器",
            agent_layer="medical_analysis",
            run_id=state["run_id"],
            session_id=state["session_id"],
            user_id=state["user_id"],
            status="success",
            confidence=float(diagnosis["confidence"]),
            reason=["辨证可信度低于 0.4，停止处方与生成流程"],
            warnings=["建议专业人员复核"],
            input_data={"diagnosis": diagnosis["output"]},
            output_data={"action": "recommend_professional"},
        )
    }


def route_after_diagnosis(state: StubWorkflowState) -> str:
    """Choose the safety branch from the diagnosis confidence threshold."""
    diagnosis = dict(state["diagnosis"])
    return "low_confidence" if float(diagnosis["confidence"]) < 0.4 else "prescription"


def build_stub_graph():
    """Compile the five Agent normal path and the low-confidence safety path."""
    graph = StateGraph(StubWorkflowState)
    graph.add_node("assessment", assessment_stub)
    graph.add_node("diagnosis", diagnosis_stub)
    graph.add_node("prescription", prescription_stub)
    graph.add_node("generation", generation_stub)
    graph.add_node("feedback", feedback_stub)
    graph.add_node("low_confidence", low_confidence_handler)

    graph.add_edge(START, "assessment")
    graph.add_edge("assessment", "diagnosis")
    graph.add_conditional_edges(
        "diagnosis",
        route_after_diagnosis,
        {"low_confidence": "low_confidence", "prescription": "prescription"},
    )
    graph.add_edge("prescription", "generation")
    graph.add_edge("generation", "feedback")
    graph.add_edge("feedback", END)
    graph.add_edge("low_confidence", END)
    return graph.compile()


def run_stub_workflow(
    *, user_id: str, session_id: str, emotion_scores: dict[str, int]
) -> dict[str, object]:
    """Run a complete deterministic workflow without external services."""
    graph = build_stub_graph()
    return dict(
        graph.invoke(
            {
                "run_id": f"run-{uuid4().hex[:12]}",
                "session_id": session_id,
                "user_id": user_id,
                "emotion_scores": emotion_scores,
            }
        )
    )
