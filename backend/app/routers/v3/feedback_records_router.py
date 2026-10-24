"""Owner-approved R1 feedback endpoints; learning/policy admission stays closed."""
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.database import get_db
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.schemas.v3.feedback_v31 import FeedbackV31, EvidenceMutationRequest, EvidenceMutationResult
from backend.app.services.v3.auth_service import get_current_v3_principal
from backend.app.services.v3 import feedback_v31_service as service
from backend.app.services.v3 import feedback_v31_contract as errors
from backend.app.services.v3.feedback_v31_transactions import save_feedback, delete_feedback, FeedbackCommitUnknown
from backend.app.services.v3.feedback_clear_service import clear_with_commit
from backend.app.services.v3.feedback_v31_reads import read_page, read_detail, FeedbackCursorStale
from backend.app.services.v3.music_library_service import LibraryCursorConfigError
from .transport import V3APIError, v3_success

router = APIRouter()


def _error(error):
    mappings = (
        (service.FeedbackNotFound,404,'FEEDBACK_NOT_FOUND'),
        (errors.PlaybackProofUnavailable,404,'FEEDBACK_SOURCE_NOT_FOUND'),
        (errors.FeedbackGone,410,'FEEDBACK_DELETED'),
        (errors.FeedbackFingerprintConflict,409,'IDEMPOTENCY_CONFLICT'),
        (errors.LegacyFingerprintUnavailable,409,'LEGACY_FINGERPRINT_UNAVAILABLE'),
        (errors.FeedbackContentUnverified,409,'FEEDBACK_CONTENT_UNVERIFIED'),
        (errors.EvidenceEpochConflict,409,'FEEDBACK_EPOCH_CONFLICT'),
        (FeedbackCursorStale,409,'FEEDBACK_CURSOR_STALE'),
        (service.ConsentNotEnabled,503,'CONSENT_POLICY_UNAVAILABLE'),
        (FeedbackCommitUnknown,503,'FEEDBACK_COMMIT_UNVERIFIED'),
        (LibraryCursorConfigError,503,'LIBRARY_CURSOR_UNAVAILABLE'),
    )
    for kind,status,code in mappings:
        if isinstance(error,kind):
            return V3APIError(status,code,'反馈操作未完成，请按当前状态重试。',
                              retryable=status == 503 or code.endswith('STALE'))
    raise error


def _key(value):
    if not isinstance(value,str) or not 1 <= len(value.strip()) <= 128:
        raise V3APIError(400,'IDEMPOTENCY_KEY_REQUIRED','需要提供合法幂等键。')
    return value.strip()


def _factory(db):
    return sessionmaker(bind=db.get_bind(),autoflush=False,expire_on_commit=False)


@router.post('/feedback-records',status_code=201)
def create_record(body: FeedbackV31, response: Response,
    idempotency_key: Annotated[str | None,Header(alias='Idempotency-Key')]=None,
    principal: AuthPrincipal=Depends(get_current_v3_principal), db: Session=Depends(get_db)):
    key = _key(idempotency_key)
    factory = _factory(db)
    try:
        result = save_feedback(factory,verification_factory=factory,principal=principal,
                               request=body,idempotency_key=key,now_utc=datetime.now(timezone.utc))
    except Exception as error:
        raise _error(error) from None
    response.status_code = 200 if result.replayed else 201
    return v3_success(result)


@router.get('/feedback-records')
def list_records(limit: Annotated[int,Query(ge=1,le=100)]=20,
    cursor: Annotated[str | None,Query(max_length=4096)]=None,
    music_id: Annotated[str | None,Query(min_length=1,max_length=64)]=None,
    principal: AuthPrincipal=Depends(get_current_v3_principal),db: Session=Depends(get_db)):
    try:
        with _factory(db)() as reader:
            return v3_success(read_page(reader,principal=principal,limit=limit,cursor=cursor,music_id=music_id))
    except Exception as error:
        raise _error(error) from None


@router.get('/feedback-records/{feedback_id}')
def get_record(feedback_id: str,principal: AuthPrincipal=Depends(get_current_v3_principal),db: Session=Depends(get_db)):
    try:
        with _factory(db)() as reader:
            return v3_success(read_detail(reader,principal=principal,feedback_id=feedback_id))
    except Exception as error:
        raise _error(error) from None


@router.delete('/feedback-records/{feedback_id}')
def delete_record(feedback_id: str, body: EvidenceMutationRequest,
    principal: AuthPrincipal=Depends(get_current_v3_principal),db: Session=Depends(get_db)):
    factory = _factory(db)
    try:
        return v3_success(delete_feedback(factory,verification_factory=factory,principal=principal,
            feedback_id=feedback_id,expected_epoch=body.expected_evidence_epoch,now_utc=datetime.now(timezone.utc)))
    except Exception as error:
        raise _error(error) from None


@router.post('/me/feedback-evidence/clear')
def clear_evidence(body: EvidenceMutationRequest,
    idempotency_key: Annotated[str | None,Header(alias='Idempotency-Key')]=None,
    principal: AuthPrincipal=Depends(get_current_v3_principal),db: Session=Depends(get_db)):
    key = _key(idempotency_key)
    factory = _factory(db)
    try:
        result = clear_with_commit(factory,verification_factory=factory,principal=principal,
            request=body,idempotency_key=key,now_utc=datetime.now(timezone.utc))
        return v3_success(result)
    except Exception as error:
        raise _error(error) from None
