"""Agent 5 — feedback_agent: POST /api/v1/feedback

Integrated with AI Engine (钟睿宸) agent_stubs.feedback_stub().
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.feedback import Feedback
from backend.app.models.session import Session
from backend.ai_engine.agent_stubs import feedback_stub
from backend.app.schemas.common import make_run_id

router = APIRouter()


@router.post("/feedback", summary="Agent 5 — 用户反馈Agent")
async def feedback(body: dict, db: Session = Depends(get_db)):
    """接收反馈 → AI引擎决策 → 返回 continue/adjust/rediag。"""
    session_id = body.get("session_id")
    user_id = body.get("user_id", "u_001")
    run_id = body.get("run_id", make_run_id("fb"))
    generation_envelope = body.get("generation", body.get("generation_result", {}))

    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    # Call AI Engine stub
    result = feedback_stub({
        "run_id": run_id, "session_id": session_id,
        "user_id": user_id,
        "generation": generation_envelope or {
            "confidence": 0.8,
            "output": {"audio": {"url": "local://demo.mp3"}},
        },
    })

    envelope = result["feedback"]

    # Persist
    decision = envelope.get("output", {}).get("decision", {})
    satisfaction = body.get("overall_satisfaction", 4)
    today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    feedback_id = f"fb_{today_str}_001"

    db_fb = Feedback(
        user_id=1, session_id=session_id, feedback_id=feedback_id,  # MVP: hardcoded until auth is in place (Sprint 3)
        subjective_satisfaction=satisfaction,
        decision_action=decision.get("action", "continue"),
        decision_detail=decision.get("next_step", ""),
        decision_next_step=decision.get("next_step", ""),
        confidence=envelope["confidence"],
        reason=str(envelope.get("reason", [])),
        processing_time_ms=envelope.get("processing_time_ms", 0),
    )
    db.add(db_fb)
    db.query(Session).filter(Session.session_id == session_id).update(
        {"current_agent": "feedback", "status": "completed"}
    )
    db.commit()

    return envelope
