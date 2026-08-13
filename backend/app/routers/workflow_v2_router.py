"""Sprint 3 Assessment, workflow and local music HTTP endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.ai_engine.assessment_v2 import (
    AssessmentValidationError,
    run_assessment_v2,
    run_assessment_v21,
)
from backend.ai_engine.music_agent import match_music_v2
from backend.ai_engine.providers import async_qwen_provider_from_env
from backend.ai_engine.real_workflow import run_real_workflow_v2, continue_real_workflow_v21
from backend.app.core.database import get_db
from backend.app.core.music_catalog import load_music_catalog
from backend.app.models.session import Session as SessionModel
from backend.app.schemas.assessment_v2 import AssessmentV2Request
from backend.app.schemas.v2 import v2_err, v2_ok
from backend.app.schemas.workflow_v2 import MusicV2Request, WorkflowV2Request
from backend.app.services.assessment_revision_service import persist_initial_revision, current_confirmed_snapshot


router = APIRouter()
logger = logging.getLogger(__name__)


def _request_id(kind: str) -> str:
    return f"req_{kind}_{uuid.uuid4().hex[:10]}"


def _result_id(prefix: str) -> str:
    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"{prefix}_{date}_{uuid.uuid4().hex[:8]}"


def _numeric_user_id(user_id: str) -> int:
    if user_id.startswith("u_") and user_id[2:].isdigit():
        return int(user_id[2:])
    return 1


def _persist_workflow_summary(
    db: Session,
    *,
    session_id: str,
    user_id: str,
    result: dict[str, object],
) -> None:
    session = db.query(SessionModel).filter(
        SessionModel.session_id == session_id
    ).first()
    if session is None:
        session = SessionModel(
            user_id=_numeric_user_id(user_id),
            session_id=session_id,
            status="active",
        )
        db.add(session)

    assessment = result.get("assessment")
    music = result.get("music")
    agent_statuses = result.get("agent_statuses")
    summary = {
        "workflow_result_id": result.get("result_id"),
        "assessment_id": (
            assessment.get("assessment_id")
            if isinstance(assessment, dict)
            else None
        ),
        "music_id": music.get("music_id") if isinstance(music, dict) else None,
        "agent_statuses": agent_statuses if isinstance(agent_statuses, dict) else {},
    }
    session.metadata_json = json.dumps(summary, ensure_ascii=False)
    confirmation = result.get("confirmation")
    needs_confirmation = (
        isinstance(confirmation, dict)
        and confirmation.get("status") == "needs_confirmation"
    )
    session.current_agent = "assessment_confirmation" if needs_confirmation else "feedback"
    session.status = "active" if needs_confirmation else "completed"
    db.commit()


@router.post("/assessments", summary="V2 — 多源状态评估")
async def create_assessment(body: AssessmentV2Request, db: Session = Depends(get_db)):
    request_id = _request_id("assessment")
    try:
        payload = body.model_dump(mode="python")
        assessment_id = _result_id("asmt")
        questionnaire = payload["questionnaire_answers"]
        if questionnaire["schema_version"] == "questionnaire_v2.1":
            result = await asyncio.to_thread(run_assessment_v21,
                {
                    **payload,
                    "assessment_id": assessment_id,
                    "document_confirmed": bool(payload.get("document_text")),
                    "confirmation_status": "pending",
                },
                provider=async_qwen_provider_from_env(),
            )
        else:
            result = run_assessment_v2(payload)
            result["assessment_id"] = assessment_id
            result.setdefault("revision", 1)
            result.setdefault("previous_revision", None)
        persist_initial_revision(db, assessment=result)
        return v2_ok(result, request_id)
    except AssessmentValidationError:
        return v2_err(
            "ASSESSMENT_INVALID",
            "状态评估数据不完整，请检查问卷后重试",
            request_id,
            retryable=False,
            next_actions=["review_questionnaire"],
        )
    except Exception:
        logger.exception("assessment v2 endpoint failed")
        return v2_err(
            "ASSESSMENT_FAILED",
            "状态评估暂时不可用，请稍后重试",
            request_id,
            next_actions=["retry_assessment"],
        )


@router.post("/workflows", summary="V2 — 五 Agent 工作流")
async def run_workflow(body: WorkflowV2Request, db: Session = Depends(get_db)):
    request_id = _request_id("workflow")
    try:
        payload = body.model_dump(mode="python")
        if payload.get('assessment_id') and payload.get('assessment_revision'):
            snapshot = current_confirmed_snapshot(db, payload['assessment_id'], payload['assessment_revision'])
            if snapshot.get('session_id') != payload['session_id']:
                raise ValueError('Assessment session mismatch')
            result = continue_real_workflow_v21(assessment=snapshot, music_catalog=load_music_catalog())
        else:
            result = run_real_workflow_v2(
                user_id=payload["user_id"],
                session_id=payload["session_id"],
                questionnaire_answers=payload["questionnaire_answers"],
                assessment_confirmed=payload["assessment_confirmed"],
                document_id=payload.get("document_id"),
                document_text=payload.get("document_text"),
                narrative_text=payload.get("narrative_text"),
                music_catalog=load_music_catalog(),
                feedback_payload=payload.get("feedback_payload"),
            )
        assessment = result.get("assessment")
        if isinstance(assessment, dict):
            assessment["assessment_id"] = _result_id("asmt")
        _persist_workflow_summary(
            db,
            session_id=payload["session_id"],
            user_id=payload["user_id"],
            result=result,
        )
        return v2_ok(result, request_id)
    except AssessmentValidationError:
        db.rollback()
        return v2_err(
            "WORKFLOW_INPUT_INVALID",
            "工作流输入不完整，请检查问卷后重试",
            request_id,
            retryable=False,
            next_actions=["review_questionnaire"],
        )
    except Exception:
        db.rollback()
        logger.exception(
            "workflow v2 endpoint failed",
            extra={"session_id": body.session_id},
        )
        return v2_err(
            "WORKFLOW_FAILED",
            "工作流暂时不可用，请稍后重试",
            request_id,
            next_actions=["retry_workflow"],
        )


@router.post("/music", summary="V2 — 本地曲库匹配")
async def match_music(body: MusicV2Request):
    request_id = _request_id("music")
    try:
        result = match_music_v2(body.prescription, load_music_catalog())
        return v2_ok(result, request_id)
    except Exception:
        logger.exception("music v2 endpoint failed")
        return v2_err(
            "MUSIC_MATCH_FAILED",
            "音乐匹配暂时不可用，请稍后重试",
            request_id,
            next_actions=["retry_music"],
        )
