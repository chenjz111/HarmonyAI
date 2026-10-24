"""Agent 2 — diagnosis_agent: POST /api/v1/diagnosis

Integrated with AI Engine: real agents when HARMONYAI_REAL_AGENTS=true, stubs otherwise.
Exception/degradation handling per agent-architecture.md Chapter 3.
"""
from datetime import datetime, timezone
import json
import traceback

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.agent_config import use_real_agents, get_llm_provider
from backend.app.models.syndrome_diagnosis import SyndromeDiagnosis
from backend.app.models.session import Session
from backend.app.schemas.common import make_run_id, AgentLayer
from backend.app.core.exceptions import build_error_response

router = APIRouter()


@router.post("/diagnosis", summary="Agent 2 — 中医辨证Agent")
async def diagnosis(body: dict, db: Session = Depends(get_db)):
    """接收健康画像 → AI引擎辨证 → 返回证型诊断。异常时返回 Universal Shell 而非 500。"""
    session_id = body.get("session_id")
    user_id = body.get("user_id", "u_001")
    run_id = body.get("run_id", make_run_id("diag"))
    assessment_envelope = body.get("assessment", body.get("assessment_result", {}))

    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    try:
        if use_real_agents():
            from backend.ai_engine.real_agents import DiagnosisAgent
            agent = DiagnosisAgent(llm=get_llm_provider())
            result = agent.run({
                "run_id": run_id, "session_id": session_id,
                "user_id": user_id,
                "assessment": assessment_envelope or {
                    "confidence": 0.85,
                    "output": {"emotion_profile": {"dominant_emotion": "anxiety"}},
                },
            })
        else:
            from backend.ai_engine.agent_stubs import diagnosis_stub
            result = diagnosis_stub({
                "run_id": run_id, "session_id": session_id,
                "user_id": user_id,
                "assessment": assessment_envelope or {
                    "confidence": 0.85,
                    "output": {"emotion_profile": body.get("emotion_scores", {})},
                },
            })

        envelope = result["diagnosis"]

        # Persist to DB
        try:
            out = envelope.get("output", {})
            sd = out.get("syndrome_diagnosis", {})
            primary = sd.get("primary", {})
            db.add(SyndromeDiagnosis(
                user_id=1, session_id=session_id,  # MVP: hardcoded until auth is in place (Sprint 3)
                primary_name=primary.get("name", ""),
                primary_element=primary.get("element"),
                primary_organ=primary.get("organ"),
                primary_emotion=primary.get("emotion"),
                primary_severity_level=primary.get("severity_level"),
                primary_severity_name=primary.get("severity_name"),
                secondary_syndromes=json.dumps(sd.get("secondary", []), ensure_ascii=False),
                confidence_overall=envelope["confidence"],
                search_keywords=json.dumps(out.get("search_keywords", []), ensure_ascii=False),
                confidence=envelope["confidence"],
                reason=json.dumps(envelope["reason"], ensure_ascii=False),
                processing_time_ms=envelope.get("processing_time_ms", 0),
            ))
            db.query(Session).filter(Session.session_id == session_id).update(
                {"current_agent": "diagnosis", "updated_at": datetime.now(timezone.utc)}
            )
            db.commit()
        except Exception as db_err:
            db.rollback()
            envelope["warnings"] = envelope.get("warnings", []) + [
                f"DB_WRITE_FAILED: {db_err}"
            ]

        return envelope

    except Exception as e:
        traceback.print_exc()
        return build_error_response(
            agent_id="diagnosis_agent", agent_name="辨证Agent",
            agent_layer=AgentLayer.MEDICAL_ANALYSIS,
            session_id=session_id, user_id=user_id, error=e, run_id=run_id,
        )
