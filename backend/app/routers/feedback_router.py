"""MVP API: POST /api/feedback — Agent ⑤.

Receives user feedback after listening → returns decision: continue / adjust / rediag.
"""
from datetime import datetime, timezone
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.session import Session
from backend.app.models.feedback import Feedback

router = APIRouter()


@router.post("/feedback", summary="MVP — 提交用户反馈")
async def submit_feedback(
    body: dict,
    db: Session = Depends(get_db),
):
    """
    用户听完音乐后打分 → 返回决策:
      - action: continue (继续) / adjust (微调) / rediag (重辨证)
      - action_detail: 解释为什么做这个决定
    """
    start_time = datetime.now(timezone.utc)
    user_id = body.get("user_id", "u_001")
    session_id = body.get("session_id")
    satisfaction = body.get("overall_satisfaction", 3)
    emotion_match = body.get("emotion_match", 3)
    text_feedback = body.get("text_feedback", "")

    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    # ── Determine action ──
    if satisfaction >= 4:
        action = "continue"
        action_detail = f"用户满意度{satisfaction}分，维持当前方案"
        next_step = "push_next_day"
    elif satisfaction == 3:
        action = "adjust"
        action_detail = f"满意度{satisfaction}分，微调BPM和乐器配比"
        next_step = "trigger_adjust"
    elif satisfaction == 2:
        action = "adjust"
        action_detail = "满意度偏低，需要较大幅度调整"
        next_step = "trigger_adjust"
    else:
        action = "rediag"
        action_detail = f"满意度{satisfaction}分，情绪匹配度{emotion_match}分，建议重新辨证"
        next_step = "trigger_rediag"

    confidence = round(0.6 + satisfaction * 0.10, 2)
    today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    feedback_id = f"fb_{today_str}_001"

    # Persist
    db_fb = Feedback(
        user_id=1, session_id=session_id, feedback_id=feedback_id,
        subjective_satisfaction=satisfaction,
        subjective_emotion_match=emotion_match,
        subjective_text=text_feedback,
        decision_action=action, decision_detail=action_detail,
        decision_next_step=next_step,
        confidence=confidence,
        reason=json.dumps([f"满意度{satisfaction}分", f"情绪匹配{emotion_match}分"]),
        processing_time_ms=0,
    )
    db.add(db_fb)
    db.query(Session).filter(Session.session_id == session_id).update(
        {"current_agent": "feedback", "updated_at": datetime.now(timezone.utc)}
    )
    db.commit()
    db.refresh(db_fb)

    processing_time = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

    return {
        "agent_id": "feedback_agent",
        "agent_version": "1.0.0",
        "user_id": user_id,
        "session_id": session_id,
        "feedback_id": feedback_id,
        "feedback": {
            "overall_satisfaction": satisfaction,
            "emotion_match": emotion_match,
            "text_feedback": text_feedback,
        },
        "decision": {
            "action": action,
            "action_detail": action_detail,
            "next_step": next_step,
            "adjustments": None if action == "continue" else (
                {"bpm_adjust": -4} if action == "adjust" else {"trigger_rediag": True}
            ),
        },
        "confidence": confidence,
        "reason": [f"满意度{satisfaction}分", f"情绪匹配{emotion_match}分"],
        "processing_time_ms": processing_time,
        "timestamp": start_time.isoformat(),
    }
