"""Agent 1 — evaluation_agent: POST /api/v1/assessment

Integrated with AI Engine (钟睿宸) agent_stubs.assessment_stub().
"""
from datetime import datetime, timezone
import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.emotion_assessment import EmotionAssessment
from backend.app.models.session import Session
from backend.ai_engine.agent_stubs import assessment_stub
from backend.app.schemas.common import make_run_id

router = APIRouter()


@router.post("/assessment", summary="Agent 1 — 评估Agent")
async def assessment(body: dict, db: Session = Depends(get_db)):
    """接收问卷 → AI引擎评估 → 返回健康画像。"""
    session_id = body.get("session_id", f"sess_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}")
    user_id = body.get("user_id", "u_001")
    emotion_scores = body.get("emotion_scores", {})
    run_id = body.get("run_id", make_run_id("eval"))

    # Call AI Engine stub
    result = assessment_stub({
        "run_id": run_id, "session_id": session_id,
        "user_id": user_id, "emotion_scores": emotion_scores,
    })

    envelope = result["assessment"]

    # Persist to DB
    db_session = db.query(Session).filter(Session.session_id == session_id).first()
    if not db_session:
        # MVP: user_id hardcoded to 1 until auth system is in place (Sprint 3)
        db.add(Session(user_id=1, session_id=session_id, status="active",
                       current_agent="evaluation"))
    else:
        db_session.current_agent = "evaluation"

    es = emotion_scores
    db.add(EmotionAssessment(
        user_id=1, session_id=session_id, input_channel="questionnaire",  # MVP: hardcoded until auth is in place (Sprint 3)
        emotion_anxiety=es.get("anxiety"), emotion_depression=es.get("depression"),
        emotion_anger=es.get("anger"), emotion_fear=es.get("fear"),
        emotion_overthinking=es.get("overthinking"),
        confidence=envelope["confidence"],
        reason=json.dumps(envelope["reason"], ensure_ascii=False),
        processing_time_ms=envelope.get("processing_time_ms", 0),
    ))
    db.commit()

    return envelope
