"""Persistence service for immutable Assessment revision history."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.app.models.assessment_followup import AssessmentFollowUp
from backend.app.models.assessment_revision import AssessmentRevision
from backend.app.schemas.assessment_revision import AssessmentRevisionContract


MAX_FOLLOWUPS = 4

_SAFETY_BLOCKING_STATES = frozenset(
    {
        "needs_verification",
        "confirmed_mental_health_risk",
        "confirmed_acute_physical_risk",
    }
)


class AssessmentContractError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def persist_initial_revision(
    db: Session,
    *,
    assessment: dict[str, Any],
) -> dict[str, Any]:
    assessment_id = str(assessment["assessment_id"])
    existing = _latest(db, assessment_id)
    if existing is not None:
        return revision_contract(existing)

    snapshot = deepcopy(assessment)
    snapshot["revision"] = 1
    snapshot["previous_revision"] = None
    row = _new_revision_row(
        session_id=str(snapshot["session_id"]),
        assessment_id=assessment_id,
        revision=1,
        previous_revision=None,
        change_summary="Initial assessment",
        changes=[],
        snapshot=snapshot,
        confirmation_level=None,
        source="initial_assessment",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return revision_contract(row)


def submit_follow_up_answers(
    db: Session,
    *,
    assessment_id: str,
    revision: int,
    answers: list[dict[str, Any]],
) -> dict[str, Any]:
    current = require_current_revision(db, assessment_id, revision)
    snapshot = snapshot_of(current)
    questions = {
        str(item.get("follow_up_id")): item
        for item in snapshot.get("follow_up_questions", [])
        if isinstance(item, dict) and item.get("follow_up_id")
    }
    already_answered = db.query(AssessmentFollowUp).filter(
        AssessmentFollowUp.assessment_id == assessment_id,
        AssessmentFollowUp.status == "answered",
    ).count()
    if already_answered + len(answers) > MAX_FOLLOWUPS:
        raise AssessmentContractError("MAX_FOLLOWUPS", "Follow-Up answers cannot exceed 4")

    evidence = list(snapshot.get("evidence_items") or [])
    changes: list[dict[str, Any]] = []
    answered_ids: set[str] = set()
    next_revision = revision + 1
    for index, answer_item in enumerate(answers, start=1):
        follow_up_id = str(answer_item["follow_up_id"])
        question = questions.get(follow_up_id)
        if question is None:
            raise AssessmentContractError(
                "FOLLOW_UP_NOT_FOUND",
                f"Follow-Up {follow_up_id} does not belong to this assessment",
            )
        value = answer_item.get("answer")
        question_id = str(question.get("question_id") or follow_up_id)
        db.add(
            AssessmentFollowUp(
                session_id=current.session_id,
                assessment_id=assessment_id,
                followup_id=f"{follow_up_id}-r{next_revision}",
                question_id=question_id,
                question=str(question.get("text") or question_id),
                category=str(question.get("trigger_reason") or "clarification"),
                priority=int(question.get("priority") or index),
                status="answered",
                answer=json.dumps(value, ensure_ascii=False),
                answer_value=value,
                source_type="user_follow_up",
                revision_submitted=next_revision,
            )
        )
        evidence.append(
            evidence_for_value(
                evidence_id=f"ev-follow-up-{uuid4().hex[:12]}",
                label=question_id,
                value=value,
                source_type="user_follow_up",
                source_ref=f"user_follow_up:{follow_up_id}",
                display_name=str(question.get("text") or question_id),
            )
        )
        changes.append(
            {
                "field": f"follow_up.{follow_up_id}.answer",
                "from": None,
                "to": value,
            }
        )
        answered_ids.add(follow_up_id)

    snapshot["evidence_items"] = evidence
    snapshot["follow_up_questions"] = [
        item
        for item in snapshot.get("follow_up_questions", [])
        if not isinstance(item, dict) or item.get("follow_up_id") not in answered_ids
    ]
    snapshot["revision"] = next_revision
    snapshot["previous_revision"] = revision
    snapshot["requires_user_confirmation"] = True
    snapshot["status"] = (
        "needs_follow_up" if snapshot["follow_up_questions"] else "awaiting_confirmation"
    )
    row = append_revision(
        db,
        current=current,
        snapshot=snapshot,
        change_summary=f"User answered {len(answers)} Follow-Up question(s)",
        changes=changes,
        source="user_follow_up",
    )
    return {"assessment": snapshot, "revision": revision_contract(row)}


def confirm_assessment_revision(
    db: Session,
    *,
    assessment_id: str,
    revision: int,
    confirmation_level: str,
    corrections: list[dict[str, Any]],
) -> dict[str, Any]:
    current = require_current_revision(db, assessment_id, revision)
    snapshot = snapshot_of(current)
    evidence = list(snapshot.get("evidence_items") or [])
    changes: list[dict[str, Any]] = [
        {
            "field": "confirmation_level",
            "from": snapshot.get("confirmation_level"),
            "to": confirmation_level,
        }
    ]
    for correction in corrections:
        change = {
            "field": correction["field"],
            "from": correction.get("from"),
            "to": correction.get("to"),
        }
        changes.append(change)
        label = str(correction["field"]).replace(".value", "").rsplit(".", 1)[-1]
        evidence.append(
            evidence_for_value(
                evidence_id=f"ev-correction-{uuid4().hex[:12]}",
                label=label,
                value=correction.get("to"),
                source_type="user_correction",
                source_ref=f"user_correction:{len(changes) - 1}",
                display_name=label,
            )
        )

    next_revision = revision + 1
    snapshot["evidence_items"] = evidence
    snapshot["revision"] = next_revision
    snapshot["previous_revision"] = revision
    snapshot["confirmation_level"] = confirmation_level
    snapshot["confirmation_status"] = confirmation_level
    safety_blocks = snapshot.get("safety_status") in _SAFETY_BLOCKING_STATES
    if safety_blocks:
        snapshot["status"] = "blocked_safety"
        snapshot["requires_user_confirmation"] = False
    else:
        snapshot["requires_user_confirmation"] = confirmation_level != "fully_accurate"
        snapshot["status"] = (
            "confirmed"
            if confirmation_level == "fully_accurate"
            else "awaiting_confirmation"
        )
    row = append_revision(
        db,
        current=current,
        snapshot=snapshot,
        change_summary=f"User confirmation: {confirmation_level}",
        changes=changes,
        source="user_correction" if corrections else "user_confirmation",
        confirmation_level=confirmation_level,
    )
    return {"assessment": snapshot, "revision": revision_contract(row)}


def revision_history(db: Session, assessment_id: str) -> list[dict[str, Any]]:
    rows = db.query(AssessmentRevision).filter(
        AssessmentRevision.assessment_id == assessment_id,
        AssessmentRevision.revision.is_not(None),
    ).order_by(AssessmentRevision.revision.asc()).all()
    if not rows:
        raise AssessmentContractError(
            "ASSESSMENT_NOT_FOUND",
            f"Assessment {assessment_id} does not exist",
        )
    return [revision_contract(row) for row in rows]


def require_current_revision(
    db: Session,
    assessment_id: str,
    revision: int,
) -> AssessmentRevision:
    current = _latest(db, assessment_id)
    if current is None:
        raise AssessmentContractError(
            "ASSESSMENT_NOT_FOUND",
            f"Assessment {assessment_id} does not exist",
        )
    if current.revision != revision:
        raise AssessmentContractError(
            "REVISION_CONFLICT",
            f"Current revision is {current.revision}, not {revision}",
        )
    return current


def current_confirmed_snapshot(db: Session, assessment_id: str, revision: int) -> dict[str, Any]:
    current = require_current_revision(db, assessment_id, revision)
    snapshot = snapshot_of(current)
    if snapshot.get("safety_status") in _SAFETY_BLOCKING_STATES:
        raise AssessmentContractError(
            "SAFETY_REQUIRES_ACTION", "Safety state must be handled before workflow"
        )
    if snapshot.get("status") != "confirmed" or snapshot.get("confirmation_level") != "fully_accurate":
        raise AssessmentContractError("ASSESSMENT_NOT_CONFIRMED", "Latest assessment revision is not confirmed")
    return snapshot
def append_revision(
    db: Session,
    *,
    current: AssessmentRevision,
    snapshot: dict[str, Any],
    change_summary: str,
    changes: list[dict[str, Any]],
    source: str,
    confirmation_level: str | None = None,
) -> AssessmentRevision:
    row = _new_revision_row(
        session_id=current.session_id,
        assessment_id=str(current.assessment_id),
        revision=int(current.revision) + 1,
        previous_revision=int(current.revision),
        change_summary=change_summary,
        changes=changes,
        snapshot=snapshot,
        confirmation_level=confirmation_level,
        source=source,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def revision_contract(row: AssessmentRevision) -> dict[str, Any]:
    payload = {
        "assessment_id": row.assessment_id,
        "revision": row.revision,
        "previous_revision": row.previous_revision,
        "created_at": _isoformat(row.created_at),
        "change_summary": row.change_summary,
        "changes": row.changes or [],
    }
    return AssessmentRevisionContract.model_validate(payload).model_dump(
        mode="json",
        by_alias=True,
    )


def snapshot_of(row: AssessmentRevision) -> dict[str, Any]:
    value = row.assessment_snapshot
    if not isinstance(value, dict):
        raise AssessmentContractError(
            "ASSESSMENT_STATE_INVALID",
            "Assessment revision has no valid snapshot",
        )
    return deepcopy(value)


def evidence_for_value(
    *,
    evidence_id: str,
    label: str,
    value: Any,
    source_type: str,
    source_ref: str,
    display_name: str,
) -> dict[str, Any]:
    if isinstance(value, dict) and {"direction", "severity"} <= set(value):
        category = "appetite"
    elif isinstance(value, list):
        category = "physical"
        value = [str(item) for item in value] or ["none"]
    elif type(value) in {int, float}:
        category = "emotion"
        value = max(0, min(4, int(value)))
    else:
        category = "life_event"
        value = str(value)
    severity = "none"
    if type(value) is int:
        severity = ("none", "mild", "moderate", "severe", "severe")[value]
    return {
        "evidence_id": evidence_id,
        "category": category,
        "label": label,
        "display_name": display_name,
        "value": value,
        "polarity": "present",
        "severity": severity,
        "severity_display": "User supplied",
        "time_window": "current",
        "source_type": source_type,
        "source_ref": source_ref,
        "confirmed": True,
        "dimension_score": value * 25 if type(value) is int else None,
    }


def _latest(db: Session, assessment_id: str) -> AssessmentRevision | None:
    return db.query(AssessmentRevision).filter(
        AssessmentRevision.assessment_id == assessment_id,
        AssessmentRevision.revision.is_not(None),
    ).order_by(AssessmentRevision.revision.desc()).first()


def _new_revision_row(
    *,
    session_id: str,
    assessment_id: str,
    revision: int,
    previous_revision: int | None,
    change_summary: str,
    changes: list[dict[str, Any]],
    snapshot: dict[str, Any],
    confirmation_level: str | None,
    source: str,
) -> AssessmentRevision:
    return AssessmentRevision(
        session_id=session_id,
        assessment_id=assessment_id,
        revision_id=f"rev-{assessment_id}-{revision}-{uuid4().hex[:6]}",
        revision=revision,
        previous_revision=previous_revision,
        change_summary=change_summary,
        changes=changes,
        assessment_snapshot=snapshot,
        confirmation_level=confirmation_level,
        field_changed="__revision__",
        old_value=json.dumps(previous_revision),
        new_value=json.dumps(snapshot, ensure_ascii=False),
        source=source,
    )


def _isoformat(value: Any) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if getattr(value, "tzinfo", None) is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()
