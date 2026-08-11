from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, NotRequired, TypedDict
from uuid import uuid4

try:
    from langgraph.graph import END, START, StateGraph
except ModuleNotFoundError:  # pragma: no cover - optional local test dependency
    END = "__end__"
    START = "__start__"
    StateGraph = None  # type: ignore[assignment,misc]

from .agent_stubs import generation_stub
from .assessment_v2 import run_assessment_v2, run_assessment_v21
from .diagnosis_v2 import run_diagnosis_v2, run_diagnosis_v21
from .feedback_store import SQLiteFeedbackStore
from .feedback_v2 import FeedbackRepository, submit_feedback_v2
try:
    from .langgraph_workflow import low_confidence_handler, route_after_diagnosis
except ModuleNotFoundError:  # pragma: no cover - optional local test dependency
    low_confidence_handler = None
    route_after_diagnosis = None
from .music_agent import match_music_v2
from .prescription_v2 import run_prescription_v2
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


class RealWorkflowV2State(TypedDict, total=False):
    result_id: str
    session_id: str
    user_id: str
    questionnaire_answers: object
    document_id: str | None
    document_text: str | None
    narrative_text: str | None
    assessment_confirmed: bool
    feedback_payload: Mapping[str, object] | None
    assessment: dict[str, object]
    confirmation: dict[str, object]
    diagnosis: dict[str, object]
    prescription: dict[str, object]
    music: dict[str, object]
    feedback: dict[str, object]
    agent_statuses: dict[str, str]
    degradations: dict[str, dict[str, object]]


def build_real_graph_v2(
    *,
    llm: JsonLLMProvider | None,
    knowledge_store: Any | None,
    music_catalog: Sequence[Mapping[str, object]],
    feedback_repository: FeedbackRepository | None,
):
    """Build the independently versioned LangGraph adapter for V2 agents."""

    def run_assessment(state: RealWorkflowV2State) -> dict[str, object]:
        return {
            "assessment": run_assessment_v2(
                {
                    "session_id": state["session_id"],
                    "user_id": state["user_id"],
                    "questionnaire_answers": state[
                        "questionnaire_answers"
                    ],
                    "document_id": state.get("document_id"),
                    "document_text": state.get("document_text"),
                    "narrative_text": state.get("narrative_text"),
                },
                llm=llm,
            )
        }

    def confirmation_gate(state: RealWorkflowV2State) -> dict[str, object]:
        assessment = _mapping_value(state.get("assessment"))
        if assessment.get("status") == "blocked_safety":
            return {"confirmation": {"status": "blocked_safety"}}
        if state.get("assessment_confirmed") is not True:
            return {"confirmation": {"status": "needs_confirmation"}}
        return {"confirmation": {"status": "confirmed"}}

    def route_after_confirmation(state: RealWorkflowV2State) -> str:
        confirmation = _mapping_value(state.get("confirmation"))
        if confirmation.get("status") in {
            "blocked_safety",
            "needs_confirmation",
        }:
            return "finalize"
        return "diagnosis"

    def run_diagnosis(state: RealWorkflowV2State) -> dict[str, object]:
        return {"diagnosis": run_diagnosis_v2(_mapping_value(state.get("assessment")), llm=llm)}

    def run_prescription(state: RealWorkflowV2State) -> dict[str, object]:
        return {
            "prescription": run_prescription_v2(
                _mapping_value(state.get("diagnosis")),
                knowledge_store=knowledge_store,
            )
        }

    def run_music(state: RealWorkflowV2State) -> dict[str, object]:
        return {
            "music": match_music_v2(
                _mapping_value(state.get("prescription")),
                music_catalog,
            )
        }

    def run_feedback(state: RealWorkflowV2State) -> dict[str, object]:
        payload = state.get("feedback_payload")
        if payload is None:
            return {"feedback": {"status": "not_submitted"}}
        if not isinstance(payload, Mapping):
            return {"feedback": _invalid_feedback("payload")}
        if payload.get("session_id") != state.get("session_id"):
            return {"feedback": _invalid_feedback("session_id")}
        music = _mapping_value(state.get("music"))
        if payload.get("music_id") != music.get("music_id"):
            return {"feedback": _invalid_feedback("music_id")}
        save_once = getattr(feedback_repository, "save_once", None)
        if not callable(save_once):
            return {
                "feedback": {
                    "status": "not_submitted",
                    "reason_code": "REPOSITORY_NOT_SUPPORTED",
                }
            }
        return {"feedback": submit_feedback_v2(payload, feedback_repository)}

    def finalize(state: RealWorkflowV2State) -> dict[str, object]:
        assessment = _mapping_value(state.get("assessment"))
        confirmation = _mapping_value(state.get("confirmation"))
        diagnosis = _mapping_value(state.get("diagnosis"))
        prescription = _mapping_value(state.get("prescription"))
        music = _mapping_value(state.get("music"))
        feedback = _mapping_value(state.get("feedback"))
        return {
            "agent_statuses": {
                "assessment": _status(assessment),
                "confirmation": _status(confirmation),
                "diagnosis": _status(diagnosis),
                "prescription": _status(prescription),
                "music": _status(music),
                "feedback": _status(feedback, default="not_submitted"),
            },
            "degradations": {
                "assessment": _degradation(assessment),
                "diagnosis": _degradation(diagnosis),
                "prescription": _degradation(prescription),
                "music": _degradation(music),
                "feedback": _degradation(feedback),
            },
        }

    graph = StateGraph(RealWorkflowV2State)
    graph.add_node("assessment", run_assessment)
    graph.add_node("confirmation", confirmation_gate)
    graph.add_node("diagnosis", run_diagnosis)
    graph.add_node("prescription", run_prescription)
    graph.add_node("music", run_music)
    graph.add_node("feedback", run_feedback)
    graph.add_node("finalize", finalize)
    graph.add_edge(START, "assessment")
    graph.add_edge("assessment", "confirmation")
    graph.add_conditional_edges(
        "confirmation",
        route_after_confirmation,
        {"diagnosis": "diagnosis", "finalize": "finalize"},
    )
    graph.add_edge("diagnosis", "prescription")
    graph.add_edge("prescription", "music")
    graph.add_edge("music", "feedback")
    graph.add_edge("feedback", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()


def run_real_workflow_v2(
    *,
    user_id: str,
    session_id: str,
    questionnaire_answers: object,
    assessment_confirmed: bool,
    document_id: str | None = None,
    document_text: str | None = None,
    narrative_text: str | None = None,
    llm: JsonLLMProvider | None = None,
    knowledge_store: Any | None = None,
    music_catalog: Sequence[Mapping[str, object]] = (),
    feedback_payload: Mapping[str, object] | None = None,
    feedback_repository: FeedbackRepository | None = None,
) -> dict[str, object]:
    """Run the V2 workflow without changing the Sprint2 entry point."""
    if type(assessment_confirmed) is not bool:
        raise TypeError("assessment_confirmed must be a bool")
    graph = build_real_graph_v2(
        llm=llm,
        knowledge_store=knowledge_store,
        music_catalog=music_catalog,
        feedback_repository=feedback_repository,
    )
    return dict(graph.invoke({
        "result_id": f"v2-result-{uuid4().hex[:12]}",
        "session_id": session_id,
        "user_id": user_id,
        "questionnaire_answers": questionnaire_answers,
        "document_id": document_id,
        "document_text": document_text,
        "narrative_text": narrative_text,
        "assessment_confirmed": assessment_confirmed,
        "feedback_payload": feedback_payload,
    }))


def run_real_workflow_v21(
    *,
    user_id: str,
    session_id: str,
    questionnaire_answers: object,
    assessment_confirmed: bool,
    assessment_id: str | None = None,
    document_text: str | None = None,
    narrative_text: str | None = None,
    provider: object | None = None,
    knowledge_store: Any | None = None,
    music_catalog: Sequence[Mapping[str, object]] = (),
) -> dict[str, object]:
    """Run the opt-in Sprint 4 AI Understanding path without replacing V2.0."""
    if type(assessment_confirmed) is not bool:
        raise TypeError("assessment_confirmed must be a bool")
    assessment = run_assessment_v21(
        {
            "assessment_id": assessment_id or f"v21-assessment-{uuid4().hex[:12]}",
            "session_id": session_id,
            "user_id": user_id,
            "questionnaire_answers": questionnaire_answers,
            "document_text": document_text,
            "document_confirmed": document_text is not None,
            "narrative_text": narrative_text,
            "confirmation_status": "confirmed" if assessment_confirmed else "pending",
        },
        provider=provider,
    )
    if assessment["status"] == "blocked_safety":
        confirmation_status = "blocked_safety"
    elif not assessment_confirmed:
        confirmation_status = "needs_confirmation"
    elif assessment.get("follow_up_questions"):
        confirmation_status = "needs_follow_up"
    else:
        confirmation_status = "confirmed"

    diagnosis: dict[str, object] | None = None
    prescription: dict[str, object] | None = None
    music: dict[str, object] | None = None
    if confirmation_status == "confirmed":
        diagnosis = run_diagnosis_v21(assessment, provider=provider)  # type: ignore[arg-type]
        if diagnosis.get("abstained") is not True:
            prescription = run_prescription_v2(
                diagnosis,
                knowledge_store=knowledge_store,
            )
            music = match_music_v2(prescription, music_catalog)

    return {
        "assessment": assessment,
        "confirmation": {"status": confirmation_status},
        "diagnosis": diagnosis,
        "prescription": prescription,
        "music": music,
        "feedback": {"status": "not_submitted"},
        "agent_statuses": {
            "assessment": str(assessment.get("status", "unknown")),
            "confirmation": confirmation_status,
            "diagnosis": _status(diagnosis or {}),
            "prescription": _status(prescription or {}),
            "music": _status(music or {}),
            "feedback": "not_submitted",
        },
        "degradations": {
            "assessment": _degradation(assessment),
            "diagnosis": _degradation(diagnosis or {}),
            "prescription": _degradation(prescription or {}),
            "music": _degradation(music or {}),
        },
    }


def continue_real_workflow_v21(*, assessment: Mapping[str, object], provider: object | None = None, knowledge_store: Any | None = None, music_catalog: Sequence[Mapping[str, object]] = ()) -> dict[str, object]:
    assessment = dict(assessment)
    confirmation_status = "blocked_safety" if assessment.get("status") == "blocked_safety" else "confirmed"
    if assessment.get("status") != "confirmed" or assessment.get("confirmation_level") != "fully_accurate":
        confirmation_status = "needs_confirmation"
    if assessment.get("follow_up_questions"):
        confirmation_status = "needs_follow_up"
    diagnosis = prescription = music = None
    if confirmation_status == "confirmed":
        diagnosis = run_diagnosis_v21(assessment, provider=provider)
        if diagnosis.get("abstained") is not True:
            prescription = run_prescription_v2(diagnosis, knowledge_store=knowledge_store)
            music = match_music_v2(prescription, music_catalog)
    return {"assessment": assessment, "confirmation": {"status": confirmation_status}, "diagnosis": diagnosis, "prescription": prescription, "music": music, "feedback": {"status": "not_submitted"}, "agent_statuses": {"assessment": str(assessment.get("status", "unknown")), "confirmation": confirmation_status, "diagnosis": _status(diagnosis or {}), "prescription": _status(prescription or {}), "music": _status(music or {}), "feedback": "not_submitted"}, "degradations": {"assessment": _degradation(assessment), "diagnosis": _degradation(diagnosis or {}), "prescription": _degradation(prescription or {}), "music": _degradation(music or {})}}
def _mapping_value(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, Mapping) else {}


def _status(value: Mapping[str, object], *, default: str = "not_run") -> str:
    status = value.get("status")
    return status if isinstance(status, str) else default


def _degradation(value: Mapping[str, object]) -> dict[str, object]:
    raw_degradation = value.get("degradation")
    if isinstance(raw_degradation, Mapping):
        if "triggered" in raw_degradation:
            reason_code = raw_degradation.get("reason_code")
            return {
                "active": bool(
                    raw_degradation.get("triggered", False)
                ),
                "reason_codes": (
                    [str(reason_code)]
                    if reason_code is not None
                    else []
                ),
            }
        return {
            "active": bool(raw_degradation.get("active", False)),
            "reason_codes": list(raw_degradation.get("reason_codes", [])),
        }
    raw_knowledge_degradation = value.get("knowledge_degradation")
    if isinstance(raw_knowledge_degradation, Mapping):
        return {
            "active": bool(raw_knowledge_degradation.get("active", False)),
            "reason_codes": list(raw_knowledge_degradation.get("reason_codes", [])),
        }
    status = _status(value)
    if status in {"success", "not_run", "not_submitted"}:
        return {"active": False, "reason_codes": []}
    error_code = value.get("error_code") or value.get("reason_code") or status.upper()
    return {"active": True, "reason_codes": [str(error_code)]}


def _invalid_feedback(field: str) -> dict[str, object]:
    return {
        "status": "failed",
        "error_code": "INVALID_PAYLOAD",
        "field": field,
        "global_rule_update": False,
    }
