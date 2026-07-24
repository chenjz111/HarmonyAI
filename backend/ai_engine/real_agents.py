from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping

from .agent_stubs import make_agent_result
from .feedback_store import SQLiteFeedbackStore
from .prompt_engine import PromptEngine
from .providers import JsonLLMProvider, LLMProviderError


MVP_SYNDROMES: dict[str, dict[str, object]] = {
    "syd_001": {"name": "肝郁化火", "element": "木", "organ": "肝", "tone_id": "jiao"},
    "syd_002": {"name": "肝气郁结", "element": "木", "organ": "肝", "tone_id": "jiao"},
    "syd_003": {"name": "心火上炎", "element": "火", "organ": "心", "tone_id": "zhi"},
    "syd_004": {"name": "心脾两虚", "element": "火土", "organ": "心脾", "tone_id": "gong"},
    "syd_005": {"name": "脾虚湿困", "element": "土", "organ": "脾", "tone_id": "gong"},
    "syd_006": {"name": "肺气虚", "element": "金", "organ": "肺", "tone_id": "shang"},
    "syd_007": {"name": "肾阴不足", "element": "水", "organ": "肾", "tone_id": "yu"},
    "syd_008": {"name": "心肾不交", "element": "火水", "organ": "心肾", "tone_id": "zhi"},
}

EMOTION_TO_SYNDROME = {
    "anxiety": "syd_001",
    "depression": "syd_002",
    "anger": "syd_003",
    "overthinking": "syd_004",
    "fatigue": "syd_005",
    "grief": "syd_006",
    "fear": "syd_007",
    "insomnia": "syd_008",
}


def _context(state: Mapping[str, object]) -> tuple[str, str, str]:
    return (
        str(state.get("run_id", "real-run")),
        str(state.get("session_id", "real-session")),
        str(state.get("user_id", "real-user")),
    )


def _envelope(
    *, agent_id: str, agent_name: str, layer: str, state: Mapping[str, object], status: str,
    confidence: float, reason: list[str], warnings: list[str], input_data: dict[str, object],
    output_data: dict[str, object],
) -> dict[str, object]:
    run_id, session_id, user_id = _context(state)
    result = make_agent_result(
        agent_id=agent_id, agent_name=agent_name, agent_layer=layer,
        run_id=run_id, session_id=session_id, user_id=user_id, status=status,
        confidence=confidence, reason=reason, warnings=warnings,
        input_data=input_data, output_data=output_data,
    )
    result["degradation_triggered"] = status != "success" or any(
        "fallback" in warning.lower() or "degraded" in warning.lower()
        for warning in warnings
    )
    return result


class AssessmentAgent:
    def __init__(self, llm: JsonLLMProvider | None) -> None:
        self.llm = llm

    def run(self, state: Mapping[str, object]) -> dict[str, object]:
        questionnaire = dict(state.get("questionnaire", {}))
        if self.llm is not None and questionnaire:
            try:
                response = self.llm.complete_json(
                    "Return JSON only. Assess emotions; do not diagnose medical disease.",
                    json.dumps(questionnaire, ensure_ascii=False),
                )
                if not isinstance(response, dict):
                    raise ValueError("assessment response must be a JSON object")
                profile_raw = response.get("emotion_profile")
                if not isinstance(profile_raw, dict) or not profile_raw.get("dominant_emotion"):
                    raise ValueError("assessment JSON missing emotion_profile.dominant_emotion")
                profile = dict(profile_raw)
                dominant = str(profile["dominant_emotion"])
                profile.setdefault("dominant_emotion", dominant)
                profile.setdefault("dominant_score", 70)
                return {"assessment": _envelope(
                    agent_id="assessment_agent", agent_name="Assessment Agent", layer="medical_analysis",
                    state=state, status="success", confidence=0.8, reason=["Qwen-compatible structured assessment"],
                    warnings=[], input_data={"questionnaire": questionnaire}, output_data={"emotion_profile": profile},
                )}
            except (LLMProviderError, ValueError, TypeError, KeyError, AttributeError):
                pass

        text = " ".join(str(value) for value in questionnaire.values())
        dominant = "anxiety" if any(token in text for token in ("睡", "焦虑", "担心", "紧张")) else "anxiety"
        profile = {
            "dominant_emotion": dominant,
            "dominant_score": 70 if questionnaire else 0,
            "dimensions": {dominant: {"score": 70 if questionnaire else 0, "severity": "medium"}},
        }
        return {"assessment": _envelope(
            agent_id="assessment_agent", agent_name="Assessment Agent", layer="medical_analysis",
            state=state, status="degraded", confidence=(0.3 if self.llm is not None else (0.3 if not questionnaire else 0.55)),
            reason=["local rule fallback: questionnaire keyword mapping"],
            warnings=["Qwen unavailable or not configured; local fallback used"],
            input_data={"questionnaire": questionnaire}, output_data={"emotion_profile": profile},
        )}


class DiagnosisAgent:
    def __init__(self, llm: JsonLLMProvider | None) -> None:
        self.llm = llm

    def run(self, state: Mapping[str, object]) -> dict[str, object]:
        assessment = dict(state.get("assessment", {}))
        assessment_output = dict(assessment.get("output", {}))
        profile = dict(assessment_output.get("emotion_profile", assessment_output))
        emotion = str(profile.get("dominant_emotion", "anxiety"))
        syndrome_id = EMOTION_TO_SYNDROME.get(emotion, "syd_001")
        confidence = float(assessment.get("confidence", 0.55))
        reason = ["local rule mapping: emotion to MVP syndrome"]
        warnings: list[str] = []
        if self.llm is not None:
            try:
                response = self.llm.complete_json(
                    "Return JSON only with syndrome_id and confidence. Use only the supplied MVP syndrome IDs.",
                    json.dumps({"emotion_profile": profile, "allowed_ids": list(MVP_SYNDROMES)}, ensure_ascii=False),
                )
                if not isinstance(response, dict):
                    raise ValueError("diagnosis response must be a JSON object")
                proposed_id = response.get("syndrome_id")
                proposed_confidence = response.get("confidence")
                if not proposed_id or not isinstance(proposed_confidence, (int, float)):
                    raise ValueError("diagnosis JSON missing syndrome_id or numeric confidence")
                proposed_id = str(proposed_id)
                if proposed_id in MVP_SYNDROMES:
                    syndrome_id = proposed_id
                    confidence = max(0.0, min(1.0, float(proposed_confidence)))
                    reason = ["Qwen-compatible structured diagnosis validated against MVP rules"]
                else:
                    warnings.append("Qwen proposed an unknown syndrome; rule mapping retained")
            except (LLMProviderError, ValueError, TypeError, KeyError, AttributeError):
                warnings.append("Qwen unavailable or not configured; local rule fallback used")
                confidence = min(confidence, 0.3)

        syndrome = dict(MVP_SYNDROMES[syndrome_id])
        syndrome.update({"syndrome_id": syndrome_id, "severity_level": 3, "severity_name": "中度"})
        return {"diagnosis": _envelope(
            agent_id="diagnosis_agent", agent_name="Diagnosis Agent", layer="medical_analysis",
            state=state, status="success" if confidence >= 0.4 else "degraded", confidence=confidence,
            reason=reason, warnings=warnings, input_data={"assessment": assessment_output},
            output_data={"syndrome_diagnosis": {"primary": syndrome}, "search_keywords": [syndrome["name"], emotion]},
        )}


class PrescriptionAgent:
    def __init__(self, knowledge_store: Any | None) -> None:
        self.knowledge_store = knowledge_store

    def run(self, state: Mapping[str, object]) -> dict[str, object]:
        diagnosis = dict(state.get("diagnosis", {}))
        diagnosis_confidence = float(diagnosis.get("confidence", 0.55))
        if diagnosis_confidence < 0.4:
            return {"prescription": _envelope(
                agent_id="prescription_agent", agent_name="Prescription Agent", layer="knowledge_mapping",
                state=state, status="degraded", confidence=diagnosis_confidence,
                reason=["diagnosis confidence below safety threshold"],
                warnings=["prescription withheld pending higher-confidence assessment"],
                input_data={"diagnosis": dict(diagnosis.get("output", {}))},
                output_data={"action": "recommend_professional"},
            )}
        diagnosis_output = dict(diagnosis.get("output", {}))
        primary = dict(dict(diagnosis_output.get("syndrome_diagnosis", {})).get("primary", {}))
        syndrome_id = str(primary.get("syndrome_id", "syd_001"))
        syndrome = MVP_SYNDROMES.get(syndrome_id, MVP_SYNDROMES["syd_001"])
        tone_id = str(syndrome["tone_id"])
        tone_config = {
            "jiao": {"tone_name": "角调", "bpm": 68, "instruments": ["古筝", "古琴"]},
            "zhi": {"tone_name": "徵调", "bpm": 70, "instruments": ["琵琶", "古琴"]},
            "gong": {"tone_name": "宫调", "bpm": 62, "instruments": ["编钟", "古琴"]},
            "shang": {"tone_name": "商调", "bpm": 66, "instruments": ["二胡", "洞箫"]},
            "yu": {"tone_name": "羽调", "bpm": 58, "instruments": ["箫", "古琴"]},
        }[tone_id]
        root = Path(__file__).resolve().parents[2]
        prompt = PromptEngine(root / "prompt" / "v1").render(
            "CN_V1",
            {"duration": 15, "bpm": tone_config["bpm"], "tone": tone_config["tone_name"], "style": "传统五声音阶疗愈音乐"},
        )
        evidence: list[dict[str, object]] = []
        warnings: list[str] = []
        if self.knowledge_store is not None:
            try:
                hits = self.knowledge_store.query(str(primary.get("name", "")), limit=3)
                evidence = [
                    {"text": hit.text, "metadata": hit.metadata, "distance": hit.distance}
                    for hit in hits
                ]
            except (OSError, ValueError, TypeError):
                warnings.append("knowledge retrieval failed; rule prescription retained")
        else:
            warnings.append("knowledge store not configured; rule prescription used")
        output = {
            "music_feature": {
                "tone_id": tone_id,
                "tone_name": tone_config["tone_name"],
                "bpm": tone_config["bpm"],
                "duration_minutes": 15,
                "instruments": tone_config["instruments"],
            },
            "prompt_template": {"template_id": prompt.template_id, "template_version": prompt.template_version},
            "prompt_tags": {"tone_id": tone_id, "style": "healing", "duration": "15_minutes"},
            "evidence": evidence,
        }
        return {"prescription": _envelope(
            agent_id="prescription_agent", agent_name="Prescription Agent", layer="knowledge_mapping",
            state=state, status="success", confidence=diagnosis_confidence,
            reason=["rule-based tone weights with Chroma evidence"], warnings=warnings,
            input_data={"diagnosis": diagnosis_output}, output_data=output,
        )}


class FeedbackAgent:
    def __init__(self, store: SQLiteFeedbackStore | None) -> None:
        self.store = store

    def run(self, state: Mapping[str, object]) -> dict[str, object]:
        feedback = dict(state.get("feedback", {}))
        rating = int(feedback.get("rating", 4))
        comment = feedback.get("comment")
        warnings: list[str] = []
        status = "success"
        if self.store is None:
            warnings.append("feedback store not configured; feedback was not persisted")
            status = "degraded"
        else:
            try:
                run_id, session_id, user_id = _context(state)
                self.store.save(
                    run_id=run_id, session_id=session_id, user_id=user_id,
                    rating=rating, comment=None if comment is None else str(comment),
                )
            except (OSError, sqlite3.Error, ValueError) as exc:
                warnings.append(f"feedback persistence failed: {exc}")
                status = "degraded"
        action = "continue" if rating >= 4 else "adjust" if rating == 3 else "stop"
        return {"feedback": _envelope(
            agent_id="feedback_agent", agent_name="Feedback Agent", layer="feedback",
            state=state, status=status, confidence=0.9 if status == "success" else 0.3,
            reason=[f"rating {rating} mapped to {action}"], warnings=warnings,
            input_data={"feedback": feedback}, output_data={"decision": {"action": action, "rating": rating}},
        )}
