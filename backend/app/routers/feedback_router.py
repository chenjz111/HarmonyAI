"""Agent 5 — feedback_agent: POST /api/v1/feedback (v1+v2 compat)
+ POST /api/v2/feedback (full Feedback 2.0 per feedback-v2-spec.md)

Integrated with AI Engine: real agents when HARMONYAI_REAL_AGENTS=true, stubs otherwise.
Exception/degradation handling per agent-architecture.md Chapter 3.
"""
from datetime import datetime, timezone
import logging
import traceback
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import ValidationError

from backend.app.core.database import get_db
from backend.app.core.agent_config import use_real_agents, get_feedback_store
from backend.app.models.feedback import Feedback
from backend.app.models.session import Session as SessionModel
from backend.app.schemas.common import make_run_id, AgentLayer
from backend.app.core.exceptions import build_error_response
from backend.app.schemas.v2 import v2_ok, v2_err, FeedbackV2Request

router = APIRouter()
logger = logging.getLogger(__name__)


def _ensure_session(session_id: str, db: Session):
    existing = db.query(SessionModel).filter(SessionModel.session_id == session_id).first()
    if not existing:
        db.add(SessionModel(user_id=1, session_id=session_id, status="active",
                           current_agent="feedback"))
        db.commit()


def _make_feedback_id() -> str:
    return f"fb_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"


# ===== V1 compatible =====

@router.post("/feedback", summary="Agent 5 — 用户反馈 (v1+v2 兼容)")
async def feedback_v1(body: dict, db: Session = Depends(get_db)):
    """接收反馈 → AI引擎决策。兼容 v1 (rating/overall_satisfaction) 和 v2 字段。"""
    session_id = body.get("session_id")
    user_id = body.get("user_id", "u_001")
    run_id = body.get("run_id", make_run_id("fb"))

    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    try:
        _ensure_session(session_id, db)

        # Determine version
        is_v2 = any(k in body for k in ["pre_state", "post_state", "music_id"])
        schema_ver = "2.0" if is_v2 else "1.0"

        # v1 rating — NO auto-default to 4 (fixes Review issue #5)
        rating = body.get("overall_satisfaction") or body.get("rating")
        satisfaction = rating if rating is not None else None

        # Run agent (real or stub depending on config)
        if use_real_agents():
            from backend.ai_engine.real_agents import FeedbackAgent
            agent = FeedbackAgent(store=get_feedback_store())
            result = agent.run({
                "run_id": run_id, "session_id": session_id,
                "user_id": user_id,
                "feedback": {"rating": satisfaction or 0, "comment": body.get("comment", "")},
            })
        else:
            from backend.ai_engine.agent_stubs import feedback_stub
            gen_envelope = body.get("generation", body.get("generation_result", {}))
            result = feedback_stub({
                "run_id": run_id, "session_id": session_id,
                "user_id": user_id,
                "generation": gen_envelope or {"confidence": 0.8, "output": {"audio": {"url": "local://demo.mp3"}}},
            })

        envelope = result["feedback"]
        decision = envelope.get("output", {}).get("decision", {})
        feedback_id = _make_feedback_id()

        # V2 extra fields
        pre = body.get("pre_state", {})
        post = body.get("post_state", {})
        exp = body.get("experience", {})
        pb = body.get("playback", {})

        db_fb = Feedback(
            user_id=1, session_id=session_id, feedback_id=feedback_id,
            prescription_id=body.get("prescription_id"),
            track_id=body.get("music_id"),
            subjective_satisfaction=satisfaction,
            subjective_emotion_match=exp.get("music_match_rating"),
            subjective_relaxation=exp.get("relaxation_rating"),
            subjective_text=exp.get("comment", body.get("text_feedback", "")),
            decision_action=decision.get("action", "continue"),
            decision_next_step=decision.get("next_step", ""),
            confidence=envelope["confidence"],
            reason=str(envelope.get("reason", [])),
            processing_time_ms=envelope.get("processing_time_ms", 0),
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

        envelope["schema_version"] = schema_ver
        envelope["global_rules_modified"] = False
        if is_v2:
            envelope["feedback_v2"] = {"pre_state": pre, "post_state": post,
                                       "experience": exp, "playback": pb,
                                       "feedback_id": feedback_id}
        return envelope

    except Exception as e:
        traceback.print_exc()
        return build_error_response(
            agent_id="feedback_agent", agent_name="反馈Agent",
            agent_layer=AgentLayer.AI_GENERATION,
            session_id=session_id, user_id=user_id, error=e, run_id=run_id,
        )


# ===== V2 Feedback endpoint (uses Pydantic — fixes Review issue #6) =====

@router.post("/v2/feedback", summary="V2 — Feedback 2.0 完整提交")
async def feedback_v2(body: dict, db: Session = Depends(get_db)):
    """Feedback 2.0 per feedback-v2-spec.md: pre/post state + experience + playback."""
    session_id = body.get("session_id")
    req_id = f"req_{datetime.now(timezone.utc).strftime('%H%M%S')}_{uuid.uuid4().hex[:4]}"

    if not session_id:
        return v2_err("MISSING_SESSION", "session_id is required", req_id, retryable=False)

    # Validate with Pydantic (fixes Review issue #6)
    try:
        validated = FeedbackV2Request(**body)
    except ValidationError as ve:
        return v2_err("VALIDATION_ERROR", str(ve), req_id, retryable=False)

    try:
        _ensure_session(session_id, db)

        pre = validated.pre_state
        post = validated.post_state
        exp = validated.experience
        pb = validated.playback

        # Compute deltas
        tension_delta = (post.tension or 0) - (pre.tension or 0)
        body_delta = (post.body_tension or 0) - (pre.body_tension or 0)
        fatigue_delta = (post.mental_fatigue or 0) - (pre.mental_fatigue or 0)

        feedback_id = _make_feedback_id()

        # Persist ALL v2 fields (fixes Review issue #7)
        db_fb = Feedback(
            user_id=1,
            session_id=session_id,
            feedback_id=feedback_id,
            prescription_id=validated.prescription_id,
            track_id=validated.music_id,
            schema_version="2.0",

            # Satisfaction & ratings (from ExperienceData model)
            subjective_satisfaction=exp.overall_rating,
            subjective_relaxation=exp.relaxation_rating,
            subjective_emotion_match=exp.music_match_rating,
            subjective_text=exp.comment[:500] if exp.comment else "",

            # Pre/post state (0-10)
            mood_before=pre.tension,
            mood_after=post.tension,
            relaxation_before=pre.body_tension,
            relaxation_after=post.body_tension,

            # Mental fatigue + goal
            profile_update=str({
                "mental_fatigue_before": pre.mental_fatigue,
                "mental_fatigue_after": post.mental_fatigue,
                "goal": pre.goal,
                "change_label": post.change_label,
            }),

            # Music & preferences
            music_match=exp.music_match_rating,
            will_continue=1 if exp.continue_use == "yes" else (0 if exp.continue_use == "no" else None),
            is_favorite=1 if exp.favorite else 0,
            disliked_features=str(exp.disliked_features + exp.disliked_instruments),

            # Playback
            behavioral_completion_rate=pb.completion_rate if pb else None,
            behavioral_replay_count=0,
            behavioral_listen_session=str(pb.listened_seconds) if pb else None,

            # Decision
            decision_action="adjust_personal_preference",
            decision_next_step="complete",
            decision_adjustments=str({
                "tension_delta": tension_delta,
                "body_tension_delta": body_delta,
                "mental_fatigue_delta": fatigue_delta,
            }),

            # Safety — NEVER modified
            global_rules_modified=0,
            confidence=0.8,
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
            "decision": {"action": "adjust_personal_preference", "next_step": "complete"},
            "personal_preference_patch": {
                "reduce_instruments": exp.disliked_instruments,
                "favorite_tracks_add": [validated.music_id] if exp.favorite and validated.music_id else [],
            },
            "global_rule_update": False,
        }, req_id)

    except Exception:
        db.rollback()
        logger.exception(
            "feedback_v2 failed",
            extra={"session_id": session_id},
        )
        return v2_err(
            "FEEDBACK_FAILED",
            "反馈保存失败，请稍后重试",
            req_id,
            retryable=True,
            next_actions=["retry_feedback"],
        )
