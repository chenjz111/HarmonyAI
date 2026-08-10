"""Assessment V2 extensions — Sprint 4:
POST /api/v2/assessments/{id}/follow-up
PATCH /api/v2/assessments/{id}/confirmation
GET /api/v2/assessments/{id}/revisions
"""
from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.assessment_followup import AssessmentFollowUp
from backend.app.models.assessment_revision import AssessmentRevision
from backend.app.schemas.v2 import v2_ok, v2_err

router = APIRouter()


MAX_FOLLOWUPS = 4  # Sprint 4 frozen contract limit


class FollowUpCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    question: str = Field(min_length=1)
    category: str = Field(default="clarification", min_length=1)
    priority: int = Field(default=1, ge=1)
    max_questions_total: int = Field(default=MAX_FOLLOWUPS, ge=1, le=MAX_FOLLOWUPS)


class AssessmentConfirmationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    confirmed: bool
    changes: dict[
        str,
        str | int | float | bool | list[str] | None,
    ] = Field(default_factory=dict)


@router.post("/assessments/{session_id}/follow-up", summary="Sprint 4 — 追问缺失信息 (max 4)")
async def create_followup(
    session_id: str,
    body: FollowUpCreateRequest,
    db: Session = Depends(get_db),
):
    """提交追问问题。每个 session 最多 4 题。"""
    req_id = f"req_{datetime.now(timezone.utc).strftime('%H%M%S')}_{uuid.uuid4().hex[:4]}"
    try:
        # Enforce max 4
        existing = db.query(AssessmentFollowUp).filter(
            AssessmentFollowUp.session_id == session_id,
        ).count()
        if existing >= MAX_FOLLOWUPS:
            return v2_err("MAX_FOLLOWUPS", f"最多{MAX_FOLLOWUPS}题追问", req_id, retryable=False)

        fuid = f"fu_{datetime.now(timezone.utc).strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}"
        fu = AssessmentFollowUp(
            session_id=session_id, followup_id=fuid,
            question=body.question,
            category=body.category,
            priority=body.priority,
            status="pending",
        )
        db.add(fu)
        db.commit()
        return v2_ok({"followup_id": fuid, "status": "pending", "remaining": MAX_FOLLOWUPS - existing - 1}, req_id)
    except Exception:
        db.rollback()
        return v2_err(
            "FOLLOWUP_FAILED",
            "追问保存失败，请稍后重试",
            req_id,
        )


@router.patch("/assessments/{session_id}/confirmation", summary="Sprint 4 — 确认评估结果")
async def confirm_assessment(
    session_id: str,
    body: AssessmentConfirmationRequest,
    db: Session = Depends(get_db),
):
    """用户确认或修改评估结果，记录 revision。"""
    req_id = f"req_{datetime.now(timezone.utc).strftime('%H%M%S')}_{uuid.uuid4().hex[:4]}"
    try:
        # Record revision for each changed field
        revisions = []
        for field, new_val in body.changes.items():
            previous = db.query(AssessmentRevision).filter(
                AssessmentRevision.session_id == session_id,
                AssessmentRevision.field_changed == field,
            ).order_by(AssessmentRevision.id.desc()).first()
            rev_id = f"rev_{datetime.now(timezone.utc).strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}"
            rev = AssessmentRevision(
                session_id=session_id, revision_id=rev_id,
                field_changed=field,
                old_value=previous.new_value if previous else None,
                new_value=str(new_val),
                source="user_confirmation",
            )
            db.add(rev)
            revisions.append(rev_id)
        db.commit()
        return v2_ok({"session_id": session_id, "confirmed": body.confirmed, "revisions": revisions}, req_id)
    except Exception:
        db.rollback()
        return v2_err(
            "CONFIRM_FAILED",
            "评估确认保存失败，请稍后重试",
            req_id,
        )


@router.get("/assessments/{session_id}/revisions", summary="Sprint 4 — 获取评估修订历史")
async def get_revisions(session_id: str, db: Session = Depends(get_db)):
    """返回指定 session 的所有 revision 记录。"""
    req_id = f"req_{datetime.now(timezone.utc).strftime('%H%M%S')}_{uuid.uuid4().hex[:4]}"
    revisions = db.query(AssessmentRevision).filter(
        AssessmentRevision.session_id == session_id
    ).order_by(AssessmentRevision.created_at.desc()).limit(50).all()
    items = [{
        "revision_id": r.revision_id,
        "field": r.field_changed,
        "old_value": r.old_value,
        "new_value": r.new_value,
        "source": r.source,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in revisions]
    return v2_ok({"session_id": session_id, "revisions": items, "total": len(items)}, req_id)
