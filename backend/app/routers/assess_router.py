"""MVP API: POST /api/assess — consolidated Agent ① + ②.

Receives questionnaire → runs evaluation + diagnosis → returns combined result.

Per mvp-definition.md:
- Agent ① transforms raw questionnaire into emotion_profile
- Agent ② maps emotion_profile to TCM syndrome diagnosis
"""
from datetime import datetime, timezone
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.session import Session
from backend.app.models.emotion_assessment import EmotionAssessment
from backend.app.models.syndrome_diagnosis import SyndromeDiagnosis

router = APIRouter()

# ---------------------------------------------------------------------------
# Emotion → Syndrome rule engine (simplified; real version uses LLM)
# ---------------------------------------------------------------------------
EMOTION_SYNDROME_MAP = {
    "anxiety": {
        "primary_name": "肝郁化火", "element": "木", "organ": "肝", "emotion": "怒",
        "evidence": [{"source": "《黄帝内经·素问·阴阳应象大论》",
                       "excerpt": "东方生风，风生木...在脏为肝...在音为角", "relevance": "high"}],
    },
    "depression": {
        "primary_name": "肝郁脾虚", "element": "木", "organ": "肝", "emotion": "怒",
        "evidence": [{"source": "《黄帝内经·素问》", "excerpt": "怒伤肝，悲胜怒...", "relevance": "high"}],
    },
    "anger": {
        "primary_name": "肝火上炎", "element": "木", "organ": "肝", "emotion": "怒",
        "evidence": [],
    },
    "fear": {
        "primary_name": "肾气不足", "element": "水", "organ": "肾", "emotion": "恐",
        "evidence": [],
    },
    "overthinking": {
        "primary_name": "心脾两虚", "element": "土", "organ": "脾", "emotion": "思",
        "evidence": [],
    },
}

WUXING_TONE_MAP = {"木": "角", "火": "徵", "土": "宫", "金": "商", "水": "羽"}


# ---------------------------------------------------------------------------
# POST /api/assess
# ---------------------------------------------------------------------------

@router.post("/assess", summary="MVP — 提交问卷，返回评估+辨证")
async def assess(
    body: dict,
    db: Session = Depends(get_db),
):
    """
    前端发送 30 题问卷 → 返回:
      - emotion_profile (Agent ①)
      - syndrome_diagnosis (Agent ②)
      - user_facing_summary (给用户看的文字)
    """
    start_time = datetime.now(timezone.utc)
    user_id = body.get("user_id", "u_001")
    session_id = body.get("session_id", f"sess_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}")
    emotion_scores = body.get("emotion_scores", {})

    if not emotion_scores:
        raise HTTPException(status_code=400, detail="emotion_scores is required")

    # ── Ensure session exists ──
    existing = db.query(Session).filter(Session.session_id == session_id).first()
    if not existing:
        db.add(Session(user_id=int(user_id.replace("u_", "")) if user_id.startswith("u_") else 1,
                       session_id=session_id, status="active", current_agent="evaluation"))
        db.commit()

    # ── Agent ①: Evaluation ──
    dominant_emotion = max(emotion_scores, key=emotion_scores.get)
    dominant_score = emotion_scores[dominant_emotion]

    # Build health_profile
    health_profile = {
        "emotion_scores": emotion_scores,
        "dominant_emotion": dominant_emotion,
        "dominant_score": dominant_score,
    }

    # Persist
    db_asmnt = EmotionAssessment(
        user_id=1,
        session_id=session_id,
        input_channel="questionnaire",
        emotion_anxiety=emotion_scores.get("anxiety"),
        emotion_depression=emotion_scores.get("depression"),
        emotion_anger=emotion_scores.get("anger"),
        emotion_fear=emotion_scores.get("fear"),
        emotion_overthinking=emotion_scores.get("overthinking"),
        confidence=0.90,
        reason=json.dumps([f"主导情绪: {dominant_emotion} ({dominant_score}分)"]),
        processing_time_ms=0,
    )
    db.add(db_asmnt)

    # ── Agent ②: Syndrome Diagnosis ──
    mapping = EMOTION_SYNDROME_MAP.get(dominant_emotion, EMOTION_SYNDROME_MAP["anxiety"])

    if dominant_score >= 80:
        severity_level, severity_name = 3, "中度"
    elif dominant_score >= 60:
        severity_level, severity_name = 2, "轻度"
    else:
        severity_level, severity_name = 1, "轻微"

    # Detect secondary syndromes
    secondary = []
    for emo, score in sorted(emotion_scores.items(), key=lambda x: -x[1]):
        if emo == dominant_emotion or score < 30:
            continue
        info = EMOTION_SYNDROME_MAP.get(emo)
        if info:
            secondary.append({
                "name": info["primary_name"], "element": info["element"],
                "organ": info["organ"], "emotion": info["emotion"],
                "severity_level": 3 if score >= 70 else (2 if score >= 50 else 1),
            })

    confidence_overall = round(0.70 + dominant_score * 0.002, 2)
    warnings_low = confidence_overall < 0.40

    db_syn = SyndromeDiagnosis(
        user_id=1, session_id=session_id,
        primary_name=mapping["primary_name"], primary_element=mapping["element"],
        primary_organ=mapping["organ"], primary_emotion=mapping["emotion"],
        primary_severity_level=severity_level, primary_severity_name=severity_name,
        secondary_syndromes=json.dumps(secondary),
        confidence_overall=confidence_overall,
        confidence_rule_engine=0.85, confidence_llm=0.72, confidence_literature=0.65,
        evidence=json.dumps(mapping["evidence"]),
        search_keywords=json.dumps([mapping["primary_name"], "五音", "调理"]),
        warn_low_confidence=warnings_low, warn_recommend_professional=warnings_low,
        confidence=confidence_overall,
        reason=json.dumps([f"{dominant_emotion}({dominant_score}分)→{mapping['emotion']}→{mapping['primary_name']}"]),
        processing_time_ms=0,
    )
    db.add(db_syn)
    db.commit()
    db.refresh(db_syn)

    # Update session
    db.query(Session).filter(Session.session_id == session_id).update(
        {"current_agent": "diagnosis", "updated_at": datetime.now(timezone.utc)}
    )
    db.commit()

    processing_time = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

    tone = WUXING_TONE_MAP.get(mapping["element"], "角")
    user_facing_summary = (
        f"根据您的问卷结果，您的主要情绪为{dominant_emotion}({dominant_score}分)，"
        f"对应中医证型「{mapping['primary_name']}」，五行属{mapping['element']}，"
        f"关联脏器为{mapping['organ']}。推荐以{tone}调式音乐进行调理。"
    )

    return {
        "agent_id": "evaluation_agent",
        "agent_version": "1.0.0",
        "user_id": user_id,
        "session_id": session_id,
        # Agent ① output
        "health_profile": health_profile,
        "evaluation_confidence": 0.90,
        # Agent ② output
        "syndrome_diagnosis": {
            "primary": {
                "name": mapping["primary_name"], "element": mapping["element"],
                "organ": mapping["organ"], "emotion": mapping["emotion"],
                "severity_level": severity_level, "severity_name": severity_name,
            },
            "secondary": secondary,
            "confidence": {"overall": confidence_overall},
            "warnings": {"low_confidence": warnings_low, "recommend_professional": warnings_low},
        },
        # User-facing text
        "user_facing_summary": user_facing_summary,
        "confidence": confidence_overall,
        "reason": [f"主导情绪{dominant_emotion}{dominant_score}分→{mapping['primary_name']}"],
        "processing_time_ms": processing_time,
        "timestamp": start_time.isoformat(),
    }
