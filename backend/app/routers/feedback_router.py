"""Agent 5 — feedback_agent: POST /api/v1/feedback + /api/v2/feedback

Sprint 3 Issue #37: Feedback 2.0 with backward compatibility.
"""
from datetime import datetime, timezone
import traceback

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.feedback import Feedback
from backend.app.models.session import Session
from backend.ai_engine.agent_stubs import feedback_stub
from backend.app.schemas.common import make_run_id, AgentLayer
from backend.app.core.exceptions import build_error_response

router = APIRouter()


def _normalize_v1(body: dict) -> dict:
    """Normalize v1 field names to v2 internal format."""
    return {
        "overall_satisfaction": body.get("overall_satisfaction") or body.get("rating"),
        "emotion_match": body.get("emotion_match"),
    }


@router.post("/feedback", summary="Agent 5 — 用户反馈 (v1+v2 兼容)")
async def feedback(body: dict, db: Session = Depends(get_db)):
    """接收反馈 → AI引擎决策。兼容 v1 (rating/overall_satisfaction) 和 v2 字段。"""
    session_id = body.get("session_id")
    user_id = body.get("user_id", "u_001")
    run_id = body.get("run_id", make_run_id("fb"))

    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    try:
        # Detect version
        is_v2 = any(k in body for k in ["mood_before", "music_match", "will_continue", "relaxation_before"])
        schema_ver = "2.0" if is_v2 else "1.0"

        # Normalize v1 fields
        satisfaction = body.get("overall_satisfaction") or body.get("rating", 4)
        emotion_match = body.get("emotion_match", 3)

        # Call AI Engine
        generation_envelope = body.get("generation", body.get("generation_result", {}))
        result = feedback_stub({
            "run_id": run_id, "session_id": session_id,
            "user_id": user_id,
            "generation": generation_envelope or {
                "confidence": 0.8,
                "output": {"audio": {"url": "local://demo.mp3"}},
            },
        })
        envelope = result["feedback"]

        # Persist to DB
        try:
            decision = envelope.get("output", {}).get("decision", {})
            today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
            feedback_id = f"fb_{today_str}_{datetime.now(timezone.utc).strftime('%H%M%S')}"

            db_fb = Feedback(
                user_id=1, session_id=session_id, feedback_id=feedback_id,
                prescription_id=body.get("prescription_id"),
                track_id=body.get("track_id"),
                subjective_satisfaction=satisfaction,
                subjective_emotion_match=emotion_match,
                subjective_text=body.get("text_feedback", ""),
                decision_action=decision.get("action", "continue"),
                decision_detail=decision.get("next_step", ""),
                decision_next_step=decision.get("next_step", ""),
                confidence=envelope["confidence"],
                reason=str(envelope.get("reason", [])),
                processing_time_ms=envelope.get("processing_time_ms", 0),
                # v2 fields
                schema_version=schema_ver,
                mood_before=body.get("mood_before"),
                mood_after=body.get("mood_after"),
                relaxation_before=body.get("relaxation_before"),
                relaxation_after=body.get("relaxation_after"),
                music_match=body.get("music_match"),
                will_continue=body.get("will_continue"),
                is_favorite=body.get("is_favorite"),
                disliked_features=str(body.get("disliked_features", [])),
                global_rules_modified=0,  # NEVER modified by feedback
            )
            db.add(db_fb)
            db.query(Session).filter(Session.session_id == session_id).update(
                {"current_agent": "feedback", "status": "completed"}
            )
            db.commit()
        except Exception as db_err:
            db.rollback()
            envelope["warnings"] = envelope.get("warnings", []) + [
                {"code": "DB_WRITE_FAILED", "message": f"数据库写入失败(已回滚): {db_err}"}
            ]

        # Add v2 metadata to response
        envelope["schema_version"] = schema_ver
        if is_v2:
            envelope["feedback_v2"] = {
                "mood_before": body.get("mood_before"),
                "mood_after": body.get("mood_after"),
                "music_match": body.get("music_match"),
                "will_continue": body.get("will_continue"),
                "is_favorite": body.get("is_favorite"),
            }
            envelope["global_rules_modified"] = False  # Contract: never true

        return envelope

    except Exception as e:
        traceback.print_exc()
        return build_error_response(
            agent_id="feedback_agent", agent_name="反馈Agent",
            agent_layer=AgentLayer.AI_GENERATION,
            session_id=session_id, user_id=user_id, error=e, run_id=run_id,
        )
