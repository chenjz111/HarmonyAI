"""Frozen Sprint 4 Assessment follow-up, confirmation and revision APIs."""
from datetime import datetime, timezone
import logging
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.ai_engine.comfort_audio import select_comfort_audio
from backend.app.core.database import get_db
from backend.app.core.music_catalog import load_music_catalog
from backend.app.schemas.assessment_revision import (
    AssessmentConfirmationRequest,
    ComfortAudioRequest,
    FollowUpSubmitRequest,
    SafetyVerificationRequest,
)
from backend.app.schemas.v2 import v2_err, v2_ok
from backend.app.services.assessment_revision_service import (
    AssessmentContractError,
    MAX_FOLLOWUPS,
    confirm_assessment_revision,
    require_current_revision,
    revision_history,
    resolve_safety_verification,
    snapshot_of,
    submit_follow_up_answers,
)


router = APIRouter()
logger = logging.getLogger(__name__)


def _request_id() -> str:
    return f"req-{datetime.now(timezone.utc).strftime('%H%M%S')}-{uuid4().hex[:6]}"


def _contract_error(error: AssessmentContractError, request_id: str) -> dict:
    return v2_err(
        error.code,
        error.message,
        request_id,
        retryable=False,
    )


@router.post(
    "/assessments/{assessment_id}/follow-up",
    summary="Sprint 4 - submit Follow-Up answers (max 4)",
)
async def submit_follow_up(
    assessment_id: str,
    body: FollowUpSubmitRequest,
    db: Session = Depends(get_db),
):
    request_id = _request_id()
    try:
        result = submit_follow_up_answers(
            db,
            assessment_id=assessment_id,
            revision=body.revision,
            answers=[
                item.model_dump(mode="json")
                for item in body.answers
            ],
        )
        return v2_ok(result, request_id)
    except AssessmentContractError as error:
        db.rollback()
        return _contract_error(error, request_id)
    except Exception:
        db.rollback()
        logger.exception(
            "assessment follow-up failed",
            extra={"assessment_id": assessment_id},
        )
        return v2_err(
            "FOLLOW_UP_FAILED",
            "Follow-Up submission failed",
            request_id,
        )


@router.patch(
    "/assessments/{assessment_id}/confirmation",
    summary="Sprint 4 - confirm or correct an Assessment",
)
async def confirm_assessment(
    assessment_id: str,
    body: AssessmentConfirmationRequest,
    db: Session = Depends(get_db),
):
    request_id = _request_id()
    try:
        result = confirm_assessment_revision(
            db,
            assessment_id=assessment_id,
            revision=body.revision,
            confirmation_level=body.confirmation_level,
            corrections=[
                item.model_dump(mode="json", by_alias=True)
                for item in body.corrections
            ],
        )
        return v2_ok(result, request_id)
    except AssessmentContractError as error:
        db.rollback()
        return _contract_error(error, request_id)
    except Exception:
        db.rollback()
        logger.exception(
            "assessment confirmation failed",
            extra={"assessment_id": assessment_id},
        )
        return v2_err(
            "CONFIRM_FAILED",
            "Assessment confirmation failed",
            request_id,
        )


@router.patch(
    "/assessments/{assessment_id}/safety-verification",
    summary="Sprint 4 - resolve a pending Safety Signal",
)
async def verify_assessment_safety(
    assessment_id: str,
    body: SafetyVerificationRequest,
    db: Session = Depends(get_db),
):
    request_id = _request_id()
    try:
        result = resolve_safety_verification(
            db,
            assessment_id=assessment_id,
            revision=body.revision,
            resolution=body.resolution,
        )
        return v2_ok(result, request_id)
    except AssessmentContractError as error:
        db.rollback()
        return _contract_error(error, request_id)
    except Exception:
        db.rollback()
        logger.exception(
            "assessment safety verification failed",
            extra={"assessment_id": assessment_id},
        )
        return v2_err(
            "SAFETY_VERIFICATION_FAILED",
            "Safety verification failed",
            request_id,
        )


@router.post(
    "/assessments/{assessment_id}/comfort-audio",
    summary="Sprint 4 - user-initiated non-prescription comfort audio",
)
async def request_comfort_audio(
    assessment_id: str,
    body: ComfortAudioRequest,
    db: Session = Depends(get_db),
):
    request_id = _request_id()
    try:
        snapshot = snapshot_of(
            require_current_revision(db, assessment_id, body.revision)
        )
        safety_status = snapshot.get("safety_status")
        if safety_status == "needs_verification":
            raise AssessmentContractError(
                "SAFETY_VERIFICATION_REQUIRED",
                "Safety verification must be completed first",
            )
        if (
            safety_status != "confirmed_mental_health_risk"
            or not snapshot.get("comfort_audio_allowed")
        ):
            raise AssessmentContractError(
                "COMFORT_AUDIO_NOT_ALLOWED",
                "Comfort audio is not available for this safety state",
            )
        if not body.user_initiated:
            raise AssessmentContractError(
                "COMFORT_AUDIO_CONSENT_REQUIRED",
                "Comfort audio requires explicit user initiation",
            )
        return v2_ok(select_comfort_audio(load_music_catalog()), request_id)
    except AssessmentContractError as error:
        return _contract_error(error, request_id)
    except Exception:
        logger.exception(
            "comfort audio request failed",
            extra={"assessment_id": assessment_id},
        )
        return v2_err(
            "COMFORT_AUDIO_FAILED",
            "Comfort audio is temporarily unavailable",
            request_id,
        )


@router.get(
    "/assessments/{assessment_id}/revisions",
    summary="Sprint 4 - get immutable Assessment revision history",
)
async def get_revisions(
    assessment_id: str,
    db: Session = Depends(get_db),
):
    request_id = _request_id()
    try:
        revisions = revision_history(db, assessment_id)
        return v2_ok(
            {
                "assessment_id": assessment_id,
                "revisions": revisions,
                "total": len(revisions),
            },
            request_id,
        )
    except AssessmentContractError as error:
        return _contract_error(error, request_id)
