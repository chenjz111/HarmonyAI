from __future__ import annotations

from typing import Any, NotRequired, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from .agent_stubs import generation_stub
from .feedback_store import SQLiteFeedbackStore
from .langgraph_workflow import low_confidence_handler, route_after_diagnosis
from .providers import JsonLLMProvider, qwen_provider_from_env
from .real_agents import AssessmentAgent, DiagnosisAgent, FeedbackAgent, PrescriptionAgent


class RealWorkflowState(TypedDict):
    run_id: str
    session_id: str
    user_id: str
    questionnaire: dict[str, object]
    feedback: dict[str, object]
    assessment: NotRequired[dict[str, object]]
    diagnosis: NotRequired[dict[str, object]]
    prescription: NotRequired[dict[str, object]]
    generation: NotRequired[dict[str, object]]
    feedback_result: NotRequired[dict[str, object]]
    low_confidence: NotRequired[dict[str, object]]


def build_real_graph(
    *,
    llm: JsonLLMProvider | None,
    knowledge_store: Any | None,
    feedback_store: SQLiteFeedbackStore | None,
):
    assessment_agent = AssessmentAgent(llm)
    diagnosis_agent = DiagnosisAgent(llm)
    prescription_agent = PrescriptionAgent(knowledge_store)
    feedback_agent = FeedbackAgent(feedback_store)

    graph = StateGraph(RealWorkflowState)
    graph.add_node("assessment", assessment_agent.run)
    graph.add_node("diagnosis", diagnosis_agent.run)
    graph.add_node("prescription", prescription_agent.run)
    graph.add_node("generation", generation_stub)
    graph.add_node("feedback", feedback_agent.run)
    graph.add_node("low_confidence", low_confidence_handler)
    graph.add_edge(START, "assessment")
    graph.add_edge("assessment", "diagnosis")
    graph.add_conditional_edges(
        "diagnosis", route_after_diagnosis,
        {"low_confidence": "low_confidence", "prescription": "prescription"},
    )
    graph.add_edge("prescription", "generation")
    graph.add_edge("generation", "feedback")
    graph.add_edge("feedback", END)
    graph.add_edge("low_confidence", END)
    return graph.compile()


def run_real_workflow(
    *,
    user_id: str,
    session_id: str,
    questionnaire: dict[str, object],
    llm: JsonLLMProvider | None = None,
    knowledge_store: Any | None = None,
    feedback_store: SQLiteFeedbackStore | None = None,
) -> dict[str, object]:
    llm = llm or qwen_provider_from_env()
    graph = build_real_graph(llm=llm, knowledge_store=knowledge_store, feedback_store=feedback_store)
    return dict(graph.invoke({
        "run_id": f"real-run-{uuid4().hex[:12]}",
        "session_id": session_id,
        "user_id": user_id,
        "questionnaire": questionnaire,
        "feedback": {"rating": 4, "comment": ""},
    }))
