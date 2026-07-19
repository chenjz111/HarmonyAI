"""MVP API: GET /api/prescription — consolidated Agent ③ + ④.

Returns prescription (daily plan) + generated audio info.
Agents ③-④ run server-side; frontend just calls GET with session_id.
"""
from datetime import datetime, timezone
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.session import Session
from backend.app.models.prescription import Prescription
from backend.app.models.syndrome_diagnosis import SyndromeDiagnosis

router = APIRouter()

# Five-tone parameter table (from project plan §3.2)
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
              "instruments": [{"id": "erhu", "name": "二胡", "role": "primary", "weight": 0.65},
                              {"id": "bo", "name": "钹", "role": "secondary", "weight": 0.25}],
              "ambient": {"id": "autumn_wind", "name": "秋风", "volume": 0.10},
              "mood": "清肃、深沉，如秋风萧瑟", "scenario": "傍晚静思"},
    "zhi":  {"tone_name": "徵调", "note": "Sol", "element": "火", "organ": "心",
             "bpm_range": (70, 80),
             "instruments": [{"id": "pipa", "name": "琵琶", "role": "primary", "weight": 0.65},
                             {"id": "tongling", "name": "铜铃", "role": "secondary", "weight": 0.25}],
             "ambient": {"id": "birds", "name": "鸟鸣", "volume": 0.12},
             "mood": "明亮、欢快，如夏日暖阳", "scenario": "晨间唤醒"},
    "yu":   {"tone_name": "羽调", "note": "La", "element": "水", "organ": "肾",
             "bpm_range": (55, 65),
             "instruments": [{"id": "guqin", "name": "古琴", "role": "primary", "weight": 0.65},
                             {"id": "qing", "name": "磬", "role": "secondary", "weight": 0.25}],
             "ambient": {"id": "rain_ocean", "name": "雨声/海洋", "volume": 0.18},
             "mood": "安宁、深邃，如深海潜流", "scenario": "深度放松"},
}

ELEMENT_TONE = {"木": "jiao", "火": "zhi", "土": "gong", "金": "shang", "水": "yu"}
KE_CYCLE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
KE_BY = {v: k for k, v in KE_CYCLE.items()}


def _build_7day_plan(primary_element: str, severity: int) -> list[dict]:
    """Generate 7-day prescription with gradually changing tone weights."""
    main_tone = ELEMENT_TONE.get(primary_element, "jiao")
    gong_element = KE_CYCLE.get(primary_element, "土")
    sheng_element = KE_BY.get(primary_element, "水")
    aux1_tone = ELEMENT_TONE.get(gong_element, "gong")
    aux2_tone = ELEMENT_TONE.get(sheng_element, "yu")

    main_p = TONE_PARAMS[main_tone]
    aux1_p = TONE_PARAMS[aux1_tone]
    aux2_p = TONE_PARAMS[aux2_tone]

    plan = []
    for day in range(1, 8):
        main_w = round(0.75 - (day - 1) * 0.04, 2)
        aux1_w = round(0.15 + (day - 1) * 0.03, 2)
        aux2_w = round(1.0 - main_w - aux1_w, 2)
        bpm_min, bpm_max = main_p["bpm_range"]
        bpm = (bpm_min + bpm_max) // 2 - (severity - 2) * 2

        plan.append({
            "day": day,
            "title": f"{main_p['tone_name']}调理 · 第{day}天",
            "tone_weights": [
                {"tone_id": main_tone, "tone_name": main_p["tone_name"], "note": main_p["note"],
                 "element": primary_element, "organ": main_p["organ"], "weight": main_w, "role": "主调"},
                {"tone_id": aux1_tone, "tone_name": aux1_p["tone_name"], "note": aux1_p["note"],
                 "element": gong_element, "organ": "脾" if gong_element == "土" else "肺", "weight": aux1_w, "role": "辅调"},
                {"tone_id": aux2_tone, "tone_name": aux2_p["tone_name"], "note": aux2_p["note"],
                 "element": sheng_element, "organ": "肾" if sheng_element == "水" else "肝", "weight": aux2_w, "role": "辅调"},
            ],
            "strategy": f"{main_p['tone_name']}为主，{aux1_p['tone_name']}护脾胃，{aux2_p['tone_name']}滋养",
            "bpm": bpm,
            "duration_minutes": 15 + day,
            "instruments": main_p["instruments"],
            "ambient_sound": main_p["ambient"],
            "mood": main_p["mood"],
            "scenario": main_p["scenario"],
        })
    return plan


# ---------------------------------------------------------------------------
# GET /api/prescription
# ---------------------------------------------------------------------------

@router.get("/prescription/{session_id}", summary="MVP — 获取音乐处方+音频")
async def get_prescription(
    session_id: str,
    db: Session = Depends(get_db),
):
    """前端传入 session_id → 返回处方 JSON + 音频 URL（Mock）。"""
    start_time = datetime.now(timezone.utc)

    # Try existing prescription for this session
    existing = db.query(Prescription).filter(
        Prescription.session_id == session_id
    ).first()

    if existing:
        daily_plan = json.loads(existing.daily_plan or "[]")
        return {
            "agent_id": existing.agent_id,
            "agent_version": existing.agent_version,
            "user_id": str(existing.user_id),
            "session_id": existing.session_id,
            "prescription_id": existing.prescription_id,
            "daily_plan": daily_plan,
            "prompt_template": {
                "template_id": existing.prompt_template_id,
                "template_version": existing.prompt_template_version,
                "parameters": json.loads(existing.prompt_parameters or "{}"),
            },
            "explanation": {
                "summary": existing.explanation_summary,
                "user_facing": existing.explanation_user_facing,
            },
            "audio": {
                "url": existing.audio_url,
                "duration_seconds": existing.audio_duration_seconds,
                "format": existing.audio_format,
            } if existing.audio_url else None,
            "confidence": existing.confidence,
            "reason": json.loads(existing.reason or "[]"),
            "processing_time_ms": 0,
            "timestamp": existing.timestamp.isoformat() if existing.timestamp else None,
        }

    # ── Generate new prescription ──
    # Find the syndrome diagnosis for this session
    syndrome = db.query(SyndromeDiagnosis).filter(
        SyndromeDiagnosis.session_id == session_id
    ).first()

    if not syndrome:
        raise HTTPException(status_code=404, detail="No diagnosis found. Call POST /api/assess first.")

    element = syndrome.primary_element or "木"
    severity = syndrome.primary_severity_level or 2
    main_tone_id = ELEMENT_TONE.get(element, "jiao")
    main_p = TONE_PARAMS[main_tone_id]

    daily_plan = _build_7day_plan(element, severity)
    today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    rx_id = f"rx_{today_str}_001"

    # Mock audio URL
    audio_url = f"https://oss.example.com/music/{rx_id}_day1.mp3"

    summary = f"{syndrome.primary_emotion or '怒'}→{element}→{syndrome.primary_organ}→{main_p['tone_name']}。辅以护脾胃，滋养调理。"
    user_facing = (
        f"为您推荐{main_p['tone_name']}式音乐\n\n"
        f"{syndrome.primary_organ}属{element}，对应{main_p['note']}音。"
        f"{main_p['tone_name']}音乐清新舒缓，帮助您疏解郁结。\n\n"
        f"依据：《黄帝内经·素问·阴阳应象大论》"
    )

    # Persist
    db_rx = Prescription(
        user_id=1, session_id=session_id, prescription_id=rx_id,
        daily_plan=json.dumps(daily_plan, ensure_ascii=False),
        prompt_template_id="CN_V1", prompt_template_version="1.0.0",
        prompt_parameters=json.dumps(daily_plan[0], ensure_ascii=False),
        explanation_summary=summary, explanation_user_facing=user_facing,
        audio_url=audio_url, audio_duration_seconds=daily_plan[0]["duration_minutes"] * 60,
        audio_format="mp3", audio_bitrate_kbps=320,
        actual_bpm=daily_plan[0]["bpm"], provider_name="skymusic", provider_cost_cny=0.20,
        confidence=0.71,
        reason=json.dumps([f"主调{main_p['tone_name']}", f"辅调护脾胃", f"BPM={daily_plan[0]['bpm']}"]),
        processing_time_ms=0,
    )
    db.add(db_rx)
    db.query(Session).filter(Session.session_id == session_id).update(
        {"current_agent": "generation", "updated_at": datetime.now(timezone.utc)}
    )
    db.commit()
    db.refresh(db_rx)

    processing_time = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

    return {
        "agent_id": db_rx.agent_id,
        "agent_version": db_rx.agent_version,
        "user_id": str(db_rx.user_id),
        "session_id": db_rx.session_id,
        "prescription_id": db_rx.prescription_id,
        "daily_plan": daily_plan,
        "prompt_template": {
            "template_id": "CN_V1",
            "template_version": "1.0.0",
            "parameters": daily_plan[0],
        },
        "explanation": {
            "summary": summary,
            "user_facing": user_facing,
            "warnings": ["本系统可信度仅供参考", "如有持续不适，建议咨询专业中医师"],
        },
        "audio": {
            "url": audio_url,
            "duration_seconds": daily_plan[0]["duration_minutes"] * 60,
            "file_size_bytes": 7340032,
            "format": "mp3",
            "bitrate_kbps": 320,
            "provider": "skymusic",
        },
        "confidence": 0.71,
        "reason": [f"主调{main_p['tone_name']}", f"BPM={daily_plan[0]['bpm']}"],
        "processing_time_ms": processing_time,
        "timestamp": start_time.isoformat(),
    }
