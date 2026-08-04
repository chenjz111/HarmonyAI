"""Session Router V2 — Sprint 3 per api-contract-v2.md.

POST /api/v2/sessions — create new session
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.session import Session as SessionModel
from backend.app.schemas.v2 import v2_ok, v2_err

router = APIRouter()


@router.post("/sessions", summary="V2 — 创建会话")
async def create_session(body: dict, db: Session = Depends(get_db)):
    req_id = f"req_{datetime.now(timezone.utc).strftime('%H%M%S')}"
    user_id = body.get("user_id", "demo_user_001")
    entry_mode = body.get("entry_mode", "full")
    ts = datetime.now(timezone.utc)
    session_id = f"sess_{ts.strftime('%Y%m%d')}_{ts.strftime('%H%M%S')[-4:]}"

    try:
        db.add(SessionModel(
            user_id=1 if user_id.startswith("demo") else int(user_id.replace("u_", "")),
            session_id=session_id,
            status="active",
            current_agent="document",
        ))
        db.commit()

        return v2_ok({
            "session_id": session_id,
            "status": "active",
            "current_step": "document",
            "created_at": ts.isoformat(),
        }, req_id)

    except Exception as e:
        db.rollback()
        return v2_err("SESSION_CREATE_FAILED", str(e), req_id, retryable=True)
