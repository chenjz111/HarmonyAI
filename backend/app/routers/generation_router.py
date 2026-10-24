"""Agent 4 — generation_agent: POST /api/v1/generation

Integrated with AI Engine + exception/degradation handling (Chapter 3).
"""
from datetime import datetime, timezone
import traceback

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.prescription import Prescription
from backend.app.models.session import Session
from backend.ai_engine.agent_stubs import generation_stub
from backend.app.schemas.common import make_run_id, AgentLayer
from backend.app.core.exceptions import build_error_response

router = APIRouter()


@router.post("/generation", summary="Agent 4 — 音乐生成Agent")
async def generation(body: dict, db: Session = Depends(get_db)):
    """接收处方 → AI引擎生成 → 返回音频。异常时返回 Universal Shell 而非 500。"""
    session_id = body.get("session_id")
    user_id = body.get("user_id", "u_001")
    run_id = body.get("run_id", make_run_id("gen"))
    prescription_envelope = body.get("prescription", body.get("prescription_result", {}))

    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    try:
        # Call AI Engine
        result = generation_stub({
            "run_id": run_id, "session_id": session_id,
            "user_id": user_id,
            "prescription": prescription_envelope or {
                "confidence": 0.71,
                "output": {"music_feature": {"tone_id": "jiao", "bpm": 68}},
            },
        })
        envelope = result["generation"]

        # Persist to DB
        try:
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
        except Exception as db_err:
            db.rollback()
            envelope["warnings"] = envelope.get("warnings", []) + [
                {"code": "DB_WRITE_FAILED", "message": f"数据库写入失败(已回滚): {db_err}"}
            ]

        return envelope

    except Exception as e:
        traceback.print_exc()
        return build_error_response(
            agent_id="generation_agent", agent_name="生成Agent",
            agent_layer=AgentLayer.AI_GENERATION,
            session_id=session_id, user_id=user_id, error=e, run_id=run_id,
        )
