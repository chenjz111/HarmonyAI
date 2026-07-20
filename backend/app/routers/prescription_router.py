"""Agent 3 — prescription_agent: POST /api/v1/prescription

Per agent-schemas.md Agent 3 + agent-architecture.md Universal Shell.
"""
from datetime import datetime, timezone
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.prescription import Prescription
from backend.app.models.session import Session
from backend.app.schemas.common import (
    UniversalOutput, AgentStatus, AgentLayer,
    WarningInfo, make_run_id,
)

router = APIRouter()

TONE_PARAMS = {
    "jiao": {"tone_name": "角调", "note": "Mi", "element": "木", "organ": "肝",
             "bpm_range": (65, 75),
             "instruments": [{"id": "guzheng", "name": "古筝", "role": "primary", "weight": 0.70},
                             {"id": "zhudi", "name": "竹笛", "role": "secondary", "weight": 0.20},
                             {"id": "guqin", "name": "古琴", "role": "harmony", "weight": 0.10}],
             "ambient": {"id": "water_stream", "name": "流水声", "volume": 0.15},
             "mood": "舒缓、清新，如春风拂柳", "scenario": "睡前放松"},
    "gong": {"tone_name": "宫调", "note": "Do", "element": "土", "organ": "脾",
             "bpm_range": (60, 68),
             "instruments": [{"id": "guqin", "name": "古琴", "role": "primary", "weight": 0.70},
                             {"id": "bianzhong", "name": "编钟", "role": "secondary", "weight": 0.20}],
             "ambient": {"id": "earth", "name": "大地回响", "volume": 0.12},
             "mood": "平稳、安定，如大地包容", "scenario": "午后放松"},
    "shang": {"tone_name": "商调", "note": "Re", "element": "金", "organ": "肺",
              "bpm_range": (68, 76),
              "instruments": [{"id": "erhu", "name": "二胡", "role": "primary", "weight": 0.65}],
              "ambient": {"id": "autumn_wind", "name": "秋风", "volume": 0.10},
              "mood": "清肃、深沉", "scenario": "傍晚静思"},
    "zhi":  {"tone_name": "徵调", "note": "Sol", "element": "火", "organ": "心",
             "bpm_range": (70, 80),
             "instruments": [{"id": "pipa", "name": "琵琶", "role": "primary", "weight": 0.65}],
             "ambient": {"id": "birds", "name": "鸟鸣", "volume": 0.12},
             "mood": "明亮、欢快", "scenario": "晨间唤醒"},
    "yu":   {"tone_name": "羽调", "note": "La", "element": "水", "organ": "肾",
             "bpm_range": (55, 65),
             "instruments": [{"id": "guqin", "name": "古琴", "role": "primary", "weight": 0.65}],
             "ambient": {"id": "rain_ocean", "name": "雨声/海洋", "volume": 0.18},
             "mood": "安宁、深邃", "scenario": "深度放松"},
}

ELEMENT_TONE = {"木": "jiao", "火": "zhi", "土": "gong", "金": "shang", "水": "yu"}
KE_CYCLE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
KE_BY = {v: k for k, v in KE_CYCLE.items()}


def _build_plan(element: str, severity: int) -> list[dict]:
    main_tone = ELEMENT_TONE.get(element, "jiao")
    gong_elem = KE_CYCLE.get(element, "土")
    sheng_elem = KE_BY.get(element, "水")
    aux1 = ELEMENT_TONE.get(gong_elem, "gong")
    aux2 = ELEMENT_TONE.get(sheng_elem, "yu")
    mp = TONE_PARAMS[main_tone]
    ap1 = TONE_PARAMS[aux1]
    ap2 = TONE_PARAMS[aux2]

    plan = []
    for day in range(1, 8):
        mw = round(0.75 - (day - 1) * 0.04, 2)
        a1w = round(0.15 + (day - 1) * 0.03, 2)
        a2w = round(1.0 - mw - a1w, 2)
        bpm = (mp["bpm_range"][0] + mp["bpm_range"][1]) // 2 - (severity - 2) * 2
        plan.append({
            "day": day, "title": f"{mp['tone_name']}调理·第{day}天",
            "tone_weights": [
                {"tone_id": main_tone, "tone_name": mp["tone_name"], "note": mp["note"],
                 "element": element, "organ": mp["organ"], "weight": mw, "role": "主调"},
                {"tone_id": aux1, "tone_name": ap1["tone_name"], "note": ap1["note"],
                 "element": gong_elem, "organ": "脾" if gong_elem == "土" else "肺", "weight": a1w, "role": "辅调"},
                {"tone_id": aux2, "tone_name": ap2["tone_name"], "note": ap2["note"],
                 "element": sheng_elem, "organ": "肾" if sheng_elem == "水" else "肝", "weight": a2w, "role": "辅调"},
            ],
            "strategy": f"{mp['tone_name']}为主，{ap1['tone_name']}辅调，{ap2['tone_name']}滋养",
            "bpm": bpm, "duration_minutes": 15 + day,
            "instruments": mp["instruments"],
            "ambient_sound": mp["ambient"],
            "mood": mp["mood"], "scenario": mp["scenario"],
        })
    return plan


@router.post("/prescription", summary="Agent 3 — 音乐处方Agent")
async def prescription(body: dict, db: Session = Depends(get_db)):
    """接收证型诊断 → 返回 7 天处方 + Prompt 参数。"""
    start = datetime.now(timezone.utc)
    run_id = make_run_id("rx")
    session_id = body.get("session_id")
    user_id = body.get("user_id", "u_001")
    syndrome_diagnosis = body.get("syndrome_diagnosis", {})
    primary = syndrome_diagnosis.get("primary", {})
    upstream_degraded = body.get("_upstream_degraded", False)
    upstream_warnings = body.get("_upstream_warnings", [])

    warnings = []
    if upstream_degraded:
        warnings.append(WarningInfo(code="UPSTREAM_DEGRADED",
                           message="上游辨证Agent已降级，处方基于低可信度证型"))

    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    element = primary.get("element", "木")
    organ = primary.get("organ", "肝")
    severity = primary.get("severity_level", 2)

    main_tone_id = ELEMENT_TONE.get(element, "jiao")
    mp = TONE_PARAMS[main_tone_id]
    daily_plan = _build_plan(element, severity)
    today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    rx_id = f"rx_{today_str}_001"

    summary = f"{primary.get('emotion','怒')}→{element}→{organ}→{mp['tone_name']}。辅以护脾胃，滋养调理。"
    user_facing = (
        f"为您推荐{mp['tone_name']}式音乐。{organ}属{element}，对应{mp['note']}音。"
        f"{mp['tone_name']}音乐清新舒缓，帮助您疏解郁结。"
        f"依据：《黄帝内经·素问·阴阳应象大论》"
    )

    output_data = {
        "prescription_id": rx_id,
        "daily_plan": daily_plan,
        "prompt_template": {
            "template_id": "CN_V1", "template_version": "1.0.0",
            "parameters": daily_plan[0],
        },
        "explanation": {
            "summary": summary, "user_facing": user_facing,
            "warnings": ["本系统可信度仅供参考", "如有持续不适，建议咨询专业中医师"],
        },
    }

    status = AgentStatus.DEGRADED if upstream_degraded else AgentStatus.SUCCESS

    db_rx = Prescription(
        user_id=1, session_id=session_id, prescription_id=rx_id,
        daily_plan=json.dumps(daily_plan, ensure_ascii=False),
        prompt_template_id="CN_V1", prompt_template_version="1.0.0",
        prompt_parameters=json.dumps(daily_plan[0], ensure_ascii=False),
        explanation_summary=summary, explanation_user_facing=user_facing,
        audio_url=None, audio_duration_seconds=None,
        audio_format="mp3", audio_bitrate_kbps=320,
        actual_bpm=daily_plan[0]["bpm"], provider_name=None, provider_cost_cny=None,
        confidence=0.71,
        reason=json.dumps([f"主调{mp['tone_name']}"], ensure_ascii=False),
        processing_time_ms=0,
    )
    db.add(db_rx)
    db.query(Session).filter(Session.session_id == session_id).update(
        {"current_agent": "prescription"}
    )
    db.commit()

    processing_time = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

    return UniversalOutput(
        agent_id="prescription_agent", agent_name="处方Agent",
        agent_layer=AgentLayer.KNOWLEDGE_MAPPING,
        run_id=run_id, session_id=session_id, user_id=user_id,
        status=status, confidence=0.71,
        reason=[f"权重矩阵: {mp['tone_name']}为主调",
                f"五行生克: {element}克土→辅宫调",
                f"BPM={daily_plan[0]['bpm']}"],
        warnings=warnings,
        input={"syndrome_diagnosis": syndrome_diagnosis},
        output=output_data,
        processing_time_ms=processing_time,
        upstream_degraded=upstream_degraded,
        upstream_warnings=upstream_warnings,
    ).model_dump(mode="json")
