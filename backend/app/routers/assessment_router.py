"""Agent 1 — evaluation_agent: POST /api/v1/assessment

Integrated with AI Engine + exception/degradation handling (Chapter 3).
"""
from datetime import datetime, timezone
import json
import traceback

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.emotion_assessment import EmotionAssessment
from backend.app.models.session import Session
from backend.ai_engine.agent_stubs import assessment_stub
from backend.app.schemas.common import make_run_id, AgentLayer
from backend.app.core.exceptions import build_error_response

router = APIRouter()


@router.post("/assessment", summary="Agent 1 — 评估Agent")
async def assessment(body: dict, db: Session = Depends(get_db)):
    """接收问卷 → AI引擎评估 → 返回健康画像。异常时返回 Universal Shell 而非 500。"""
    session_id = body.get("session_id", f"sess_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}")
    user_id = body.get("user_id", "u_001")
    emotion_scores = body.get("emotion_scores", {})
    run_id = body.get("run_id", make_run_id("eval"))

    try:
        # Call AI Engine
        result = assessment_stub({
            "run_id": run_id, "session_id": session_id,
            "user_id": user_id, "emotion_scores": emotion_scores,
        })
        envelope = result["assessment"]

        # Persist to DB
        try:
            db_session = db.query(Session).filter(Session.session_id == session_id).first()
            if not db_session:
                db.add(Session(user_id=1, session_id=session_id, status="active",
                               current_agent="evaluation"))
            else:
                db_session.current_agent = "evaluation"
            es = emotion_scores
            db.add(EmotionAssessment(
                user_id=1, session_id=session_id, input_channel="questionnaire",
                emotion_anxiety=es.get("anxiety"), emotion_depression=es.get("depression"),
                emotion_anger=es.get("anger"), emotion_fear=es.get("fear"),
                emotion_overthinking=es.get("overthinking"),
                confidence=envelope["confidence"],
                reason=json.dumps(envelope["reason"], ensure_ascii=False),
                processing_time_ms=envelope.get("processing_time_ms", 0),
            ))
            db.commit()
        except Exception as db_err:
            db.rollback()
            envelope["warnings"] = envelope.get("warnings", []) + [
                {"code": "DB_WRITE_FAILED", "message": f"数据库写入失败(已回滚): {db_err}"}
            ]

        return envelope

    except Exception as e:
        traceback.print_exc()
        return build_error_response(
            agent_id="evaluation_agent", agent_name="评估Agent",
            agent_layer=AgentLayer.MEDICAL_ANALYSIS,
            session_id=session_id, user_id=user_id, error=e, run_id=run_id,
        )
