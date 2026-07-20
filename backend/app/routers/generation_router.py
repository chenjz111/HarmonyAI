"""Agent 4 — generation_agent: POST /api/v1/generation

Per agent-schemas.md Agent 4 + agent-architecture.md Universal Shell.
Music generation is STUB — returns mock audio URL.
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

# Provider fallback chain (Chapter 3.2)
PROVIDER_CHAIN = ["skymusic", "musicmini", "funmusic", "local_library"]


@router.post("/generation", summary="Agent 4 — 音乐生成Agent")
async def generation(body: dict, db: Session = Depends(get_db)):
    """接收处方 daily_plan[day] + prompt_template → 返回音频 URL (stub)。"""
    start = datetime.now(timezone.utc)
    run_id = make_run_id("gen")
    session_id = body.get("session_id")
    user_id = body.get("user_id", "u_001")
    prescription_id = body.get("prescription_id", "")
    day = body.get("day", 1)
    daily_plan_entry = body.get("daily_plan_entry", {})
    upstream_degraded = body.get("_upstream_degraded", False)
    upstream_warnings = body.get("_upstream_warnings", [])

    warnings = []
    if upstream_degraded:
        warnings.append(WarningInfo(code="UPSTREAM_DEGRADED", message="上游处方Agent已降级，音乐参数可能不是最优"))

    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    bpm = daily_plan_entry.get("bpm", 68)
    instruments = daily_plan_entry.get("instruments", [])
    duration = daily_plan_entry.get("duration_minutes", 15)
    tone_weights = daily_plan_entry.get("tone_weights", [])

    # Stub: always succeed with mock audio
    provider = "skymusic"
    audio_url = f"https://oss.example.com/music/{prescription_id}_day{day}.mp3"
    degradation_triggered = False

    # Simulate degradation for generation agent (Chapter 3.2)
    if body.get("_simulate_api_failure"):
        provider = "local_library"
        audio_url = f"https://oss.example.com/local_library/{tone_weights[0]['tone_id']}_default.mp3"
        degradation_triggered = True
        warnings.append(WarningInfo(code="API_FAILOVER", message="SkyMusic/MiniMax/Fun-Music all failed, using local library"))

    output_data = {
        "prescription_id": prescription_id,
        "day": day,
        "audio": {
            "url": audio_url,
            "duration_seconds": duration * 60,
            "file_size_bytes": 7340032,
            "format": "mp3",
            "bitrate_kbps": 320,
        },
        "actual_params": {
            "bpm": bpm,
            "instruments_used": instruments,
            "prompt_template_used": "CN_V1",
            "prompt_sent": f"请生成{duration}分钟中国民族风纯音乐...",
            "prompt_truncated": False,
        },
        "provider": {
            "name": provider,
            "attempt_order": 1,
            "retry_count": 0,
            "degradation_triggered": degradation_triggered,
            "api_response_time_ms": 8234,
            "cost_cny": 0.20,
        },
        "degradation_log": [{"attempt": 1, "provider": provider, "status": "success", "latency_ms": 8234}],
    }

    status = AgentStatus.DEGRADED if (upstream_degraded or degradation_triggered) else AgentStatus.SUCCESS

    # Update prescription record with audio URL
    db_rx = db.query(Prescription).filter(Prescription.session_id == session_id).first()
    if db_rx:
        db_rx.audio_url = audio_url
        db_rx.audio_duration_seconds = duration * 60
        db_rx.audio_format = "mp3"
        db_rx.audio_bitrate_kbps = 320
        db_rx.actual_bpm = bpm
        db_rx.provider_name = provider
        db_rx.provider_cost_cny = 0.20
    db.query(Session).filter(Session.session_id == session_id).update(
        {"current_agent": "generation", "updated_at": datetime.now(timezone.utc)}
    )
    db.commit()

    processing_time = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

    return UniversalOutput(
        agent_id="generation_agent", agent_name="生成Agent",
        agent_layer=AgentLayer.AI_GENERATION,
        run_id=run_id, session_id=session_id, user_id=user_id,
        status=status, confidence=1.0 if not degradation_triggered else 0.6,
        reason=[f"{provider}调用成功" if not degradation_triggered else f"降级到{provider}"],
        warnings=warnings,
        input={"daily_plan_entry": daily_plan_entry, "day": day},
        output=output_data,
        processing_time_ms=processing_time,
        upstream_degraded=upstream_degraded,
        upstream_warnings=upstream_warnings,
    ).model_dump(mode="json")
