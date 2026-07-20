"""Agent 5 — feedback_agent: POST /api/v1/feedback

Per agent-schemas.md Agent 5 + agent-architecture.md Universal Shell.
"""
from datetime import datetime, timezone
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.feedback import Feedback
from backend.app.models.session import Session
from backend.app.schemas.common import (
    UniversalOutput, AgentStatus, AgentLayer,
    WarningInfo, make_run_id,
)

router = APIRouter()


@router.post("/feedback", summary="Agent 5 — 用户反馈Agent")
async def feedback(body: dict, db: Session = Depends(get_db)):
    """接收用户反馈 → 返回决策：continue / adjust / rediag。"""
    start = datetime.now(timezone.utc)
    run_id = make_run_id("fb")
    session_id = body.get("session_id")
    user_id = body.get("user_id", "u_001")
    satisfaction = body.get("overall_satisfaction", 3)
    emotion_match = body.get("emotion_match", 3)
    text_feedback = body.get("text_feedback", "")
    upstream_degraded = body.get("_upstream_degraded", False)
    upstream_warnings = body.get("_upstream_warnings", [])

    warnings = []
    if upstream_degraded:
        warnings.append(WarningInfo(code="UPSTREAM_DEGRADED",
                           message="上游生成Agent已降级，音乐来自本地曲库"))

    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    if satisfaction >= 4:
        action, detail, next_step = "continue", f"满意度{satisfaction}分，维持当前方案", "push_next_day"
        adjustments = None
    elif satisfaction == 3:
        action, detail, next_step = "adjust", f"满意度{satisfaction}分，微调参数", "trigger_adjust"
        adjustments = {"param_changes": {"bpm": {"from": 68, "to": 64}}}
    elif satisfaction == 2:
        action, detail, next_step = "adjust", "满意度偏低，较大调整", "trigger_adjust"
        adjustments = {"param_changes": {"bpm": {"from": 68, "to": 60}}}
    else:
        action, detail, next_step = "rediag", f"满意度{satisfaction}分，建议重新辨证", "trigger_rediag"
        adjustments = {"trigger_rediag": True}

    confidence = round(0.6 + satisfaction * 0.10, 2)
    today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    feedback_id = f"fb_{today_str}_001"

    output_data = {
        "feedback_id": feedback_id,
        "feedback": {
            "subjective": {"overall_satisfaction": satisfaction, "emotion_match": emotion_match,
                           "text_feedback": text_feedback},
        },
        "decision": {"action": action, "action_detail": detail, "next_step": next_step,
                     "adjustments": adjustments},
        "user_profile_update": {
            "preferred_instruments": [{"id": "guzheng", "name": "古筝", "score": 0.85, "occurrences": 3}],
        },
    }

    db_fb = Feedback(
        user_id=1, session_id=session_id, feedback_id=feedback_id,
        subjective_satisfaction=satisfaction,
        subjective_emotion_match=emotion_match,
        subjective_text=text_feedback,
        decision_action=action, decision_detail=detail, decision_next_step=next_step,
        decision_adjustments=json.dumps(adjustments) if adjustments else None,
        confidence=confidence,
        reason=json.dumps([f"满意度{satisfaction}分", f"情绪匹配{emotion_match}分"], ensure_ascii=False),
        processing_time_ms=0,
    )
    db.add(db_fb)
    db.query(Session).filter(Session.session_id == session_id).update(
        {"current_agent": "feedback", "status": "completed"}
    )
    db.commit()

    processing_time = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

    return UniversalOutput(
        agent_id="feedback_agent", agent_name="反馈Agent",
        agent_layer=AgentLayer.AI_GENERATION,
        run_id=run_id, session_id=session_id, user_id=user_id,
        status=AgentStatus.SUCCESS, confidence=confidence,
        reason=[f"满意度{satisfaction}分", f"情绪匹配{emotion_match}分"],
        warnings=warnings,
        input={"satisfaction": satisfaction, "emotion_match": emotion_match},
        output=output_data,
        processing_time_ms=processing_time,
        upstream_degraded=upstream_degraded,
        upstream_warnings=upstream_warnings,
    ).model_dump(mode="json")
