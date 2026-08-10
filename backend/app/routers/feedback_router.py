"""Agent 5 — feedback_agent: POST /api/v1/feedback (v1+v2 compat)
+ POST /api/v2/feedback (full Feedback 2.0 per feedback-v2-spec.md)

Integrated with AI Engine: real agents when HARMONYAI_REAL_AGENTS=true, stubs otherwise.
Exception/degradation handling per agent-architecture.md Chapter 3.
"""
from datetime import datetime, timezone
import json
import logging
import traceback
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.ai_engine.feedback_v2 import submit_feedback_v2
from backend.app.core.database import get_db
from backend.app.core.agent_config import use_real_agents, get_feedback_store
from backend.app.models.feedback import Feedback
from backend.app.models.session import Session as SessionModel
from backend.app.schemas.common import make_run_id, AgentLayer
from backend.app.core.exceptions import build_error_response
from backend.app.schemas.v2 import v2_ok, v2_err

router = APIRouter()
v2_router = APIRouter()
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


# ===== V2 Feedback endpoint =====

class _SQLAlchemyFeedbackRepository:
    """Persist the canonical AI Feedback V2 record exactly once."""

    def __init__(self, db: Session):
        self.db = db

    def save_once(
        self,
        record: dict[str, object],
        preference_patch: dict[str, object],
    ) -> bool:
        feedback_id = str(record["feedback_id"])
        existing = self.db.query(Feedback).filter(
            Feedback.feedback_id == feedback_id
        ).first()
        if existing is not None:
            return False

        session_id = str(record["session_id"])
        _ensure_session(session_id, self.db)
        pre = dict(record["pre_state"])
        post = dict(record["post_state"])
        experience = dict(record["experience"])
        playback_value = record.get("playback")
        playback = (
            dict(playback_value)
            if isinstance(playback_value, dict)
            else None
        )
        completion_rate = None
        if playback is not None:
            duration = int(playback["duration_seconds"])
            listened = int(playback["listened_seconds"])
            completion_rate = min(listened / duration, 1.0)

        disliked_features = list(experience["disliked_features"])
        disliked_instruments = list(experience["disliked_instruments"])
        change_label = str(post["change_label"])
        if change_label == "worse":
            decision_action = "reduce_current_music"
        elif disliked_features or disliked_instruments or experience["favorite"]:
            decision_action = "adjust_personal_preference"
        else:
            decision_action = "keep_personal_preference"

        tension_delta = int(post["tension"]) - int(pre["tension"])
        body_delta = _optional_delta(
            pre.get("body_tension"),
            post.get("body_tension"),
        )
        fatigue_delta = _optional_delta(
            pre.get("mental_fatigue"),
            post.get("mental_fatigue"),
        )
        feedback = Feedback(
            user_id=1,
            session_id=session_id,
            feedback_id=feedback_id,
            prescription_id=str(record["prescription_id"]),
            track_id=str(record["music_id"]),
            schema_version="2.0",
            subjective_satisfaction=int(experience["overall_rating"]),
            subjective_relaxation=int(experience["relaxation_rating"]),
            subjective_emotion_match=int(experience["music_match_rating"]),
            subjective_text=str(experience["comment"]),
            mood_before=int(pre["tension"]),
            mood_after=int(post["tension"]),
            relaxation_before=pre.get("body_tension"),
            relaxation_after=post.get("body_tension"),
            music_match=int(experience["music_match_rating"]),
            will_continue=(
                1
                if experience["continue_use"] == "yes"
                else (0 if experience["continue_use"] == "no" else None)
            ),
            is_favorite=1 if experience["favorite"] else 0,
            disliked_features=json.dumps(
                disliked_features + disliked_instruments,
                ensure_ascii=False,
            ),
            behavioral_completion_rate=completion_rate,
            behavioral_replay_count=0,
            behavioral_pause_count=(
                int(playback["pause_count"])
                if playback is not None
                else None
            ),
            behavioral_skip_count=(
                int(playback["skip_count"])
                if playback is not None
                else None
            ),
            decision_action=decision_action,
            decision_next_step="complete",
            decision_adjustments=json.dumps(
                {
                    "tension_delta": tension_delta,
                    "body_tension_delta": body_delta,
                    "mental_fatigue_delta": fatigue_delta,
                },
                ensure_ascii=False,
            ),
            profile_update=json.dumps(
                {
                    "goal": pre["goal"],
                    "change_label": change_label,
                    "personal_preference_patch": preference_patch,
                },
                ensure_ascii=False,
            ),
            global_rules_modified=0,
            confidence=1.0,
            reason="结构化反馈已通过 Feedback V2 合同校验",
            processing_time_ms=0,
        )
        self.db.add(feedback)
        self.db.query(SessionModel).filter(
            SessionModel.session_id == session_id
        ).update({"status": "completed", "current_agent": "feedback"})
        self.db.commit()
        return True


def _optional_delta(before: object, after: object) -> int | None:
    if before is None or after is None:
        return None
    return int(after) - int(before)


@v2_router.post("/feedback", summary="V2 — Feedback 2.0 完整提交")
async def feedback_v2(body: dict, db: Session = Depends(get_db)):
    req_id = f"req_feedback_{uuid.uuid4().hex[:10]}"
    result = submit_feedback_v2(
        body,
        _SQLAlchemyFeedbackRepository(db),
    )
    if result.get("status") != "failed":
        return v2_ok(result, req_id)

    db.rollback()
    if result.get("error_code") == "INVALID_PAYLOAD":
        return v2_err(
            "VALIDATION_ERROR",
            "反馈数据格式不正确，请检查后重试",
            req_id,
            retryable=False,
            next_actions=["review_feedback_fields"],
        )

    logger.error(
        "feedback v2 persistence failed",
        extra={"error_code": result.get("error_code")},
    )
    return v2_err(
        "FEEDBACK_FAILED",
        "反馈保存失败，请稍后重试",
        req_id,
        retryable=True,
        next_actions=["retry_feedback"],
    )
