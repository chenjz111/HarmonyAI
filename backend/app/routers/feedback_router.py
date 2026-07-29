"""Agent 5 — feedback_agent: POST /api/v1/feedback (v1+v2 compat)
+ POST /api/v2/feedback (full Feedback 2.0 per feedback-v2-spec.md)
"""
from datetime import datetime, timezone
import traceback

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.feedback import Feedback
from backend.app.models.session import Session as SessionModel
from backend.ai_engine.agent_stubs import feedback_stub
from backend.app.schemas.common import make_run_id, AgentLayer
from backend.app.core.exceptions import build_error_response
from backend.app.schemas.v2 import v2_ok, v2_err

router = APIRouter()


# ===== V1 compatible (existing) =====

@router.post("/feedback", summary="Agent 5 — 用户反馈 (v1+v2 兼容)")
async def feedback_v1(body: dict, db: Session = Depends(get_db)):
    """接收反馈 → AI引擎决策。兼容 v1 和 v2 字段。"""
    session_id = body.get("session_id")
    user_id = body.get("user_id", "u_001")
    run_id = body.get("run_id", make_run_id("fb"))

    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    try:
        # Ensure session exists
        existing = db.query(SessionModel).filter(SessionModel.session_id == session_id).first()
        if not existing:
            db.add(SessionModel(user_id=1, session_id=session_id, status="active", current_agent="feedback"))
            db.commit()

        is_v2 = any(k in body for k in ["pre_state", "post_state", "music_id"])
        schema_ver = "2.0" if is_v2 else "1.0"
        satisfaction = body.get("overall_satisfaction") or body.get("rating", 4)

        generation_envelope = body.get("generation", {})
        result = feedback_stub({
            "run_id": run_id, "session_id": session_id,
            "user_id": user_id,
            "generation": generation_envelope or {"confidence": 0.8, "output": {"audio": {"url": "local://demo.mp3"}}},
        })

        decision = result["feedback"].get("output", {}).get("decision", {})
        today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        feedback_id = f"fb_{today_str}_{datetime.now(timezone.utc).strftime('%H%M%S')}"

        # V2 pre/post state
        pre = body.get("pre_state", {})
        post = body.get("post_state", {})
        exp = body.get("experience", {})
        pb = body.get("playback", {})

        db_fb = Feedback(
            user_id=1, session_id=session_id, feedback_id=feedback_id,
            prescription_id=body.get("prescription_id"),
            track_id=body.get("music_id"),
            subjective_satisfaction=satisfaction,
            subjective_text=exp.get("comment", body.get("text_feedback", "")),
            decision_action=decision.get("action", "continue"),
            decision_next_step=decision.get("next_step", ""),
            confidence=result["feedback"]["confidence"],
            reason=str(result["feedback"].get("reason", [])),
            schema_version=schema_ver,
            mood_before=pre.get("tension"),
            mood_after=post.get("tension"),
            relaxation_before=pre.get("body_tension"),
            relaxation_after=post.get("body_tension"),
            music_match=exp.get("music_match_rating"),
            will_continue=1 if exp.get("continue_use") == "yes" else (0 if exp.get("continue_use") == "no" else None),
            is_favorite=1 if exp.get("favorite") else 0,
            disliked_features=str(exp.get("disliked_features", [])),
            global_rules_modified=0,
        )
        db.add(db_fb)
        db.query(SessionModel).filter(SessionModel.session_id == session_id).update(
            {"status": "completed"}
        )
        db.commit()

        resp = result["feedback"]
        resp["schema_version"] = schema_ver
        resp["global_rules_modified"] = False

        if is_v2:
            resp["feedback_v2"] = {
                "pre_state": pre, "post_state": post,
                "experience": exp, "playback": pb,
                "feedback_id": feedback_id,
            }
        return resp

    except Exception as e:
        traceback.print_exc()
        return build_error_response(
            agent_id="feedback_agent", agent_name="反馈Agent",
            agent_layer=AgentLayer.AI_GENERATION,
            session_id=session_id, user_id=user_id, error=e, run_id=run_id,
        )


# ===== V2 Feedback endpoint =====

@router.post("/v2/feedback", summary="V2 — Feedback 2.0 完整提交")
async def feedback_v2(body: dict, db: Session = Depends(get_db)):
    """Feedback 2.0 per feedback-v2-spec.md: pre/post state + experience + playback."""
    req_id = f"req_{datetime.now(timezone.utc).strftime('%H%M%S')}"
    session_id = body.get("session_id")
    if not session_id:
        return v2_err("MISSING_SESSION", "session_id is required", req_id, retryable=False)

    try:
        existing = db.query(SessionModel).filter(SessionModel.session_id == session_id).first()
        if not existing:
            db.add(SessionModel(user_id=1, session_id=session_id, status="active", current_agent="feedback"))
            db.commit()

        pre = body.get("pre_state", {})
        post = body.get("post_state", {})
        exp = body.get("experience", {})
        pb = body.get("playback", {})

        # Compute deltas
        tension_delta = (post.get("tension", 0) or 0) - (pre.get("tension", 0) or 0)
        body_delta = (post.get("body_tension", 0) or 0) - (pre.get("body_tension", 0) or 0)
        fatigue_delta = (post.get("mental_fatigue", 0) or 0) - (pre.get("mental_fatigue", 0) or 0)

        today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        feedback_id = f"fb_{today_str}_{datetime.now(timezone.utc).strftime('%H%M%S')}"

        # Persist
        db_fb = Feedback(
            user_id=1, session_id=session_id, feedback_id=feedback_id,
            prescription_id=body.get("prescription_id"),
            track_id=body.get("music_id"),
            subjective_satisfaction=exp.get("overall_rating"),
            subjective_text=exp.get("comment", ""),
            schema_version="2.0",
            mood_before=pre.get("tension"),
            mood_after=post.get("tension"),
            relaxation_before=pre.get("body_tension"),
            relaxation_after=post.get("body_tension"),
            music_match=exp.get("music_match_rating"),
            will_continue=1 if exp.get("continue_use") == "yes" else (0 if exp.get("continue_use") == "no" else None),
            is_favorite=1 if exp.get("favorite") else 0,
            disliked_features=str(exp.get("disliked_features", [])),
            global_rules_modified=0,
            confidence=0.8,
            decision_action="adjust_personal_preference",
            decision_next_step="complete",
        )
        db.add(db_fb)
        db.query(SessionModel).filter(SessionModel.session_id == session_id).update(
            {"status": "completed"}
        )
        db.commit()

        return v2_ok({
            "feedback_id": feedback_id,
            "agent_id": "feedback_agent",
            "status": "success",
            "subjective_change": {
                "tension_delta": tension_delta,
                "body_tension_delta": body_delta,
                "mental_fatigue_delta": fatigue_delta,
            },
            "decision": {
                "action": "adjust_personal_preference",
                "next_step": "complete",
            },
            "personal_preference_patch": {
                "reduce_instruments": exp.get("disliked_instruments", []),
                "favorite_tracks_add": [body.get("music_id")] if exp.get("favorite") and body.get("music_id") else [],
            },
            "global_rule_update": False,
        }, req_id)

    except Exception as e:
        db.rollback()
        return v2_err("FEEDBACK_FAILED", str(e), req_id, retryable=True)
