"""Agent 4 — generation_agent: POST /api/v1/generation

Integrated with AI Engine (钟睿宸) agent_stubs.generation_stub().
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.prescription import Prescription
from backend.app.models.session import Session
from backend.ai_engine.agent_stubs import generation_stub
from backend.app.schemas.common import make_run_id

router = APIRouter()


@router.post("/generation", summary="Agent 4 — 音乐生成Agent")
async def generation(body: dict, db: Session = Depends(get_db)):
    """接收处方 → AI引擎生成 → 返回音频。"""
    session_id = body.get("session_id")
    user_id = body.get("user_id", "u_001")
    run_id = body.get("run_id", make_run_id("gen"))
    prescription_envelope = body.get("prescription", body.get("prescription_result", {}))

    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    # Call AI Engine stub
    result = generation_stub({
        "run_id": run_id, "session_id": session_id,
        "user_id": user_id,
        "prescription": prescription_envelope or {
            "confidence": 0.71,
            "output": {"music_feature": {"tone_id": "jiao", "bpm": 68}},
        },
    })

    envelope = result["generation"]

    # Persist
    audio = envelope.get("output", {}).get("audio", {})
    db_rx = db.query(Prescription).filter(Prescription.session_id == session_id).first()
    if db_rx:
        db_rx.audio_url = audio.get("url")
        db_rx.audio_format = audio.get("format", "mp3")
        db_rx.provider_name = audio.get("url", "").split("://")[0] if audio.get("url") else "local"
    db.query(Session).filter(Session.session_id == session_id).update(
        {"current_agent": "generation", "updated_at": datetime.now(timezone.utc)}
    )
    db.commit()

    return envelope
