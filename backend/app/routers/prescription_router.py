"""Agent 3 — prescription_agent: POST /api/v1/prescription

Integrated with AI Engine: real agents when HARMONYAI_REAL_AGENTS=true, stubs otherwise.
"""
from datetime import datetime, timezone
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.agent_config import use_real_agents, get_knowledge_store
from backend.app.models.prescription import Prescription
from backend.app.models.session import Session
from backend.app.schemas.common import make_run_id

router = APIRouter()


@router.post("/prescription", summary="Agent 3 — 音乐处方Agent")
async def prescription(body: dict, db: Session = Depends(get_db)):
    """接收证型 → AI引擎生成处方 → 返回音乐处方 + Prompt。"""
    session_id = body.get("session_id")
    user_id = body.get("user_id", "u_001")
    run_id = body.get("run_id", make_run_id("rx"))
    diagnosis_envelope = body.get("diagnosis", body.get("diagnosis_result", {}))

    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    if use_real_agents():
        from backend.ai_engine.real_agents import PrescriptionAgent
        agent = PrescriptionAgent(knowledge_store=get_knowledge_store())
        result = agent.run({
            "run_id": run_id, "session_id": session_id,
            "user_id": user_id,
            "diagnosis": diagnosis_envelope or {
                "confidence": 0.77,
                "output": {"syndrome_diagnosis": {"primary": {"name": "肝郁化火", "element": "木"}}},
            },
        })
    else:
        from backend.ai_engine.agent_stubs import prescription_stub
        result = prescription_stub({
            "run_id": run_id, "session_id": session_id,
            "user_id": user_id,
            "diagnosis": diagnosis_envelope or {
                "confidence": 0.77,
                "output": {"syndrome_diagnosis": {"primary": {"name": "肝郁化火", "element": "木"}}},
            },
        })

    envelope = result["prescription"]

    # Persist
    out = envelope.get("output", {})
    mf = out.get("music_feature", {})
    pt = out.get("prompt_template", {})
    today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    rx_id = f"rx_{today_str}_001"

    db_rx = Prescription(
        user_id=1, session_id=session_id, prescription_id=rx_id,  # MVP: hardcoded until auth is in place (Sprint 3)
        daily_plan=json.dumps([{"day": 1, "tone": mf.get("tone_name"), "bpm": mf.get("bpm"),
                                "instruments": mf.get("instruments", [])}], ensure_ascii=False),
        prompt_template_id=pt.get("template_id", "CN_V1"),
        prompt_template_version=pt.get("template_version", "1.0.0"),
        prompt_parameters=json.dumps(pt.get("parameters", pt.get("text", "")), ensure_ascii=False),
        explanation_summary=f"AI引擎: {mf.get('tone_name', '未知')} {mf.get('bpm', '?')}BPM",
        confidence=envelope["confidence"],
        reason=json.dumps(envelope["reason"], ensure_ascii=False),
        processing_time_ms=envelope.get("processing_time_ms", 0),
    )
    db.add(db_rx)
    db.query(Session).filter(Session.session_id == session_id).update(
        {"current_agent": "prescription"}
    )
    db.commit()

    return envelope
