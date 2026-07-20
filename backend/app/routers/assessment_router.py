"""Agent 1 — evaluation_agent: POST /api/v1/assessment

Per agent-schemas.md Agent 1 + agent-architecture.md Universal Shell.
"""
from datetime import datetime, timezone
import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.emotion_assessment import EmotionAssessment
from backend.app.models.session import Session
from backend.app.schemas.common import (
    UniversalOutput, AgentStatus, AgentLayer,
    WarningInfo, make_run_id,
)

router = APIRouter()

EMOTION_SYNDROME_MAP = {
    "anxiety":     {"name": "肝郁化火", "element": "木", "organ": "肝", "emotion": "怒"},
    "depression":  {"name": "肝郁脾虚", "element": "木", "organ": "肝", "emotion": "怒"},
    "anger":       {"name": "肝火上炎", "element": "木", "organ": "肝", "emotion": "怒"},
    "fear":        {"name": "肾气不足", "element": "水", "organ": "肾", "emotion": "恐"},
    "overthinking":{"name": "心脾两虚", "element": "土", "organ": "脾", "emotion": "思"},
}


@router.post("/assessment", summary="Agent 1 — 评估Agent")
async def assessment(body: dict, db: Session = Depends(get_db)):
    """接收问卷/OCR/语音 → 返回结构化健康画像。"""
    start = datetime.now(timezone.utc)
    run_id = make_run_id("eval")
    session_id = body.get("session_id", f"sess_{start.strftime('%Y%m%d_%H%M%S')}")
    user_id = body.get("user_id", "u_001")
    emotion_scores = body.get("emotion_scores", {})

    warnings = []
    upstream_degraded = body.get("_upstream_degraded", False)
    upstream_warnings = body.get("_upstream_warnings", [])

    # Degradation check: empty input
    if not emotion_scores:
        return UniversalOutput(
            agent_id="evaluation_agent", agent_name="评估Agent",
            agent_layer=AgentLayer.MEDICAL_ANALYSIS,
            run_id=run_id, session_id=session_id, user_id=user_id,
            status=AgentStatus.DEGRADED, confidence=0.1,
            reason=["未收到情绪数据"],
            warnings=[WarningInfo(code="EMPTY_INPUT", message="emotion_scores is empty")],
            output={"health_profile": None, "term_mapping": []},
        ).model_dump(mode="json")

    dominant_emotion = max(emotion_scores, key=emotion_scores.get)
    dominant_score = emotion_scores[dominant_emotion]
    mapping = EMOTION_SYNDROME_MAP.get(dominant_emotion, EMOTION_SYNDROME_MAP["anxiety"])

    if dominant_score >= 80:
        severity_level, severity_name = 3, "中度"
    elif dominant_score >= 60:
        severity_level, severity_name = 2, "轻度"
    else:
        severity_level, severity_name = 1, "轻微"

    term_mapping = [{
        "western_term": dominant_emotion,
        "tcm_syndrome": mapping["name"],
        "source": "preset_table",
        "confidence": 0.85,
    }]

    output_data = {
        "health_profile": {
            "emotion_scores": emotion_scores,
            "body_indicators": {
                "sleep_quality": body.get("body_indicators", {}).get("sleep_quality"),
                "appetite": body.get("body_indicators", {}).get("appetite"),
                "energy": body.get("body_indicators", {}).get("energy"),
                "palpitation": body.get("body_indicators", {}).get("palpitation"),
                "digestion": body.get("body_indicators", {}).get("digestion"),
            },
            "questionnaire_scores": body.get("questionnaire_scores"),
        },
        "term_mapping": term_mapping,
    }

    # Persist
    db_session = db.query(Session).filter(Session.session_id == session_id).first()
    if not db_session:
        db.add(Session(user_id=1, session_id=session_id, status="active",
                       current_agent="evaluation"))
    else:
        db_session.current_agent = "evaluation"
    db.commit()

    db_asmnt = EmotionAssessment(
        user_id=1, session_id=session_id, input_channel="questionnaire",
        emotion_anxiety=emotion_scores.get("anxiety"),
        emotion_depression=emotion_scores.get("depression"),
        emotion_anger=emotion_scores.get("anger"),
        emotion_fear=emotion_scores.get("fear"),
        emotion_overthinking=emotion_scores.get("overthinking"),
        confidence=0.90,
        reason=json.dumps([f"dominant:{dominant_emotion}({dominant_score})"], ensure_ascii=False),
        processing_time_ms=0,
    )
    db.add(db_asmnt)
    db.commit()

    processing_time = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

    return UniversalOutput(
        agent_id="evaluation_agent", agent_name="评估Agent",
        agent_layer=AgentLayer.MEDICAL_ANALYSIS,
        run_id=run_id, session_id=session_id, user_id=user_id,
        status=AgentStatus.SUCCESS, confidence=0.90,
        reason=[f"主导情绪:{dominant_emotion}({dominant_score}分)", f"证型映射:{mapping['name']}"],
        warnings=warnings,
        input={"emotion_scores": emotion_scores},
        output=output_data,
        processing_time_ms=processing_time,
        upstream_degraded=upstream_degraded,
        upstream_warnings=upstream_warnings,
    ).model_dump(mode="json")
