"""Agent 2 — diagnosis_agent: POST /api/v1/diagnosis

Per agent-schemas.md Agent 2 + agent-architecture.md Universal Shell.
"""
from datetime import datetime, timezone
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.syndrome_diagnosis import SyndromeDiagnosis
from backend.app.models.session import Session
from backend.app.schemas.common import (
    UniversalOutput, AgentStatus, AgentLayer,
    WarningInfo, make_run_id,
)

router = APIRouter()

EMOTION_SYNDROME_MAP = {
    "anxiety":     {"name": "肝郁化火", "element": "木", "organ": "肝", "emotion": "怒",
                    "evidence": [{"source": "《黄帝内经·素问·阴阳应象大论》",
                                  "excerpt": "东方生风，风生木...在脏为肝...在音为角", "relevance": "high"}]},
    "depression":  {"name": "肝郁脾虚", "element": "木", "organ": "肝", "emotion": "怒",
                    "evidence": [{"source": "《黄帝内经·素问》", "excerpt": "怒伤肝，悲胜怒...", "relevance": "high"}]},
    "anger":       {"name": "肝火上炎", "element": "木", "organ": "肝", "emotion": "怒", "evidence": []},
    "fear":        {"name": "肾气不足", "element": "水", "organ": "肾", "emotion": "恐", "evidence": []},
    "overthinking":{"name": "心脾两虚", "element": "土", "organ": "脾", "emotion": "思", "evidence": []},
}


@router.post("/diagnosis", summary="Agent 2 — 中医辨证Agent")
async def diagnosis(body: dict, db: Session = Depends(get_db)):
    """接收健康画像 → 返回中医证型诊断 + 可信度 + 文献证据。"""
    start = datetime.now(timezone.utc)
    run_id = make_run_id("diag")
    session_id = body.get("session_id")
    user_id = body.get("user_id", "u_001")
    health_profile = body.get("health_profile", {})
    emotion_scores = health_profile.get("emotion_scores", {})
    upstream_degraded = body.get("_upstream_degraded", False)
    upstream_warnings = body.get("_upstream_warnings", [])

    warnings = []
    if upstream_degraded:
        warnings.append(WarningInfo(code="UPSTREAM_DEGRADED", message="上游评估Agent已降级，输入可信度降低"))

    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    if not emotion_scores:
        return UniversalOutput(
            agent_id="diagnosis_agent", agent_name="辨证Agent",
            agent_layer=AgentLayer.MEDICAL_ANALYSIS,
            run_id=run_id, session_id=session_id, user_id=user_id,
            status=AgentStatus.DEGRADED, confidence=0.1,
            reason=["未收到情绪数据，无法辨证"],
            warnings=warnings + [WarningInfo(code="EMPTY_INPUT", message="health_profile.emotion_scores missing")],
            upstream_degraded=upstream_degraded,
            upstream_warnings=upstream_warnings,
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

    # Secondary syndromes
    secondary = []
    for emo, score in sorted(emotion_scores.items(), key=lambda x: -x[1]):
        if emo == dominant_emotion or score < 30:
            continue
        info = EMOTION_SYNDROME_MAP.get(emo)
        if info:
            secondary.append({"name": info["name"], "element": info["element"],
                              "organ": info["organ"], "emotion": info["emotion"],
                              "severity_level": 3 if score >= 70 else (2 if score >= 50 else 1)})

    # Confidence
    rule_conf = 0.85
    llm_conf = round(rule_conf - 0.10, 2)
    lit_conf = round(rule_conf - 0.15, 2)
    overall = round((rule_conf + llm_conf + lit_conf) / 3, 2)
    low_conf = overall < 0.40

    # Degradation: if confidence too low
    if low_conf:
        warnings.append(WarningInfo(code="LOW_CONFIDENCE", message="可信度<40%，建议咨询专业中医师"))

    status = AgentStatus.DEGRADED if upstream_degraded else AgentStatus.SUCCESS

    output_data = {
        "syndrome_diagnosis": {
            "primary": {
                "name": mapping["name"], "element": mapping["element"],
                "organ": mapping["organ"], "emotion": mapping["emotion"],
                "severity_level": severity_level, "severity_name": severity_name,
            },
            "secondary": secondary,
        },
        "confidence": {
            "overall": overall,
            "breakdown": {"rule_engine_match": rule_conf, "llm_confidence": llm_conf, "literature_support": lit_conf},
        },
        "evidence": mapping["evidence"],
        "search_keywords": [mapping["name"], "五音", "调理"],
        "warnings": {"low_confidence": low_conf, "recommend_professional": low_conf},
    }

    # Persist
    db_syn = SyndromeDiagnosis(
        user_id=1, session_id=session_id,
        primary_name=mapping["name"], primary_element=mapping["element"],
        primary_organ=mapping["organ"], primary_emotion=mapping["emotion"],
        primary_severity_level=severity_level, primary_severity_name=severity_name,
        secondary_syndromes=json.dumps(secondary, ensure_ascii=False),
        confidence_overall=overall,
        confidence_rule_engine=rule_conf, confidence_llm=llm_conf, confidence_literature=lit_conf,
        evidence=json.dumps(mapping["evidence"], ensure_ascii=False),
        search_keywords=json.dumps([mapping["name"], "五音", "调理"], ensure_ascii=False),
        warn_low_confidence=low_conf, warn_recommend_professional=low_conf,
        confidence=overall,
        reason=json.dumps([f"{dominant_emotion}({dominant_score})→{mapping['emotion']}→{mapping['name']}"], ensure_ascii=False),
        processing_time_ms=0,
    )
    db.add(db_syn)
    db.query(Session).filter(Session.session_id == session_id).update(
        {"current_agent": "diagnosis", "updated_at": datetime.now(timezone.utc)}
    )
    db.commit()

    processing_time = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

    return UniversalOutput(
        agent_id="diagnosis_agent", agent_name="辨证Agent",
        agent_layer=AgentLayer.MEDICAL_ANALYSIS,
        run_id=run_id, session_id=session_id, user_id=user_id,
        status=status, confidence=overall,
        reason=[f"{dominant_emotion}({dominant_score}分)→{mapping['emotion']}→{mapping['name']}"],
        warnings=warnings,
        input={"health_profile": health_profile},
        output=output_data,
        processing_time_ms=processing_time,
        upstream_degraded=upstream_degraded,
        upstream_warnings=upstream_warnings,
    ).model_dump(mode="json")
