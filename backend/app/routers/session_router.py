"""Session Router V2 — Sprint 3 per api-contract-v2.md.

POST /api/v2/sessions — create new session
"""
from datetime import datetime, timezone
import json
import logging
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.document import Document
from backend.app.models.emotion_assessment import EmotionAssessment
from backend.app.models.feedback import Feedback
from backend.app.models.prescription import Prescription
from backend.app.models.session import Session as SessionModel
from backend.app.schemas.v2 import v2_ok, v2_err

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/sessions", summary="V2 — 创建会话")
async def create_session(body: dict, db: Session = Depends(get_db)):
    req_id = f"req_session_{uuid.uuid4().hex[:10]}"
    user_id = body.get("user_id", "demo_user_001")
    entry_mode = body.get("entry_mode", "full")
    ts = datetime.now(timezone.utc)
    session_id = (
        f"sess_{ts.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    )

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

    except Exception:
        db.rollback()
        logger.exception(
            "session creation failed",
            extra={"request_id": req_id},
        )
        return v2_err(
            "SESSION_CREATE_FAILED",
            "会话创建失败，请稍后重试",
            req_id,
            retryable=True,
            next_actions=["retry_session"],
        )


@router.get("/sessions/{session_id}", summary="V2 — 查询会话状态")
async def get_session(session_id: str, db: Session = Depends(get_db)):
    req_id = f"req_session_{uuid.uuid4().hex[:10]}"
    try:
        session = db.query(SessionModel).filter(
            SessionModel.session_id == session_id
        ).first()
        if session is None:
            return v2_err(
                "SESSION_NOT_FOUND",
                "未找到对应会话",
                req_id,
                retryable=False,
                next_actions=["create_session"],
            )

        metadata = {}
        if session.metadata_json:
            try:
                parsed = json.loads(session.metadata_json)
                if isinstance(parsed, dict):
                    metadata = parsed
            except (TypeError, ValueError):
                logger.warning(
                    "invalid session metadata",
                    extra={"session_id": session_id},
                )

        document_ids = [
            row.document_id
            for row in db.query(Document).filter(
                Document.session_id == session_id,
                Document.status != "deleted",
            ).all()
        ]
        assessment = db.query(EmotionAssessment).filter(
            EmotionAssessment.session_id == session_id
        ).order_by(EmotionAssessment.id.desc()).first()
        prescription = db.query(Prescription).filter(
            Prescription.session_id == session_id
        ).order_by(Prescription.id.desc()).first()
        feedback = db.query(Feedback).filter(
            Feedback.session_id == session_id
        ).order_by(Feedback.id.desc()).first()

        return v2_ok({
            "session_id": session.session_id,
            "status": session.status,
            "current_step": session.current_agent,
            "document_ids": document_ids,
            "assessment_id": metadata.get("assessment_id") or (
                str(assessment.id) if assessment is not None else None
            ),
            "prescription_id": (
                prescription.prescription_id
                if prescription is not None
                else None
            ),
            "workflow_result_id": metadata.get("workflow_result_id"),
            "music_id": metadata.get("music_id") or (
                prescription.audio_url
                if prescription is not None
                else None
            ),
            "feedback_id": (
                feedback.feedback_id if feedback is not None else None
            ),
            "agent_statuses": metadata.get("agent_statuses", {}),
            "created_at": (
                session.created_at.isoformat()
                if session.created_at is not None
                else None
            ),
        }, req_id)
    except Exception:
        logger.exception(
            "session query failed",
            extra={"session_id": session_id},
        )
        return v2_err(
            "SESSION_QUERY_FAILED",
            "会话查询暂时不可用，请稍后重试",
            req_id,
            next_actions=["retry_session_query"],
        )