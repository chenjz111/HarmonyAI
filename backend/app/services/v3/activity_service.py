"""Owner Flow Amendment 001 session active-input transitions (蔡子鑫 #79).

Implements `POST /api/v3/sessions/{id}/input-transitions` with the three
actions (select_mode / replace_document / discard_document), each guarded by
authentication, Idempotency-Key, ownership, and an optimistic
expected_input_revision CAS. Every accepted transition bumps input_revision
and writes an immutable `session_input_revisions` snapshot in the same
transaction as the live pointer update.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import uuid

from sqlalchemy import update
from sqlalchemy.orm import Session

from backend.app.models.document import Document
from backend.app.models.session import Session as SessionModel
from backend.app.models.v3.document import DocumentSet
from backend.app.models.v3.session import (
    SessionInputRevision,
    V3IdempotencyRecord,
)
from backend.app.models.v3.understanding import (
    QuestionnaireSubmissionV3,
    UnderstandingRevision,
    UnderstandingRun,
)
from backend.app.schemas.v3.assessment import QuestionnaireRef, UnderstandingRef
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.schemas.v3.session import (
    InputTransitionRequest,
    SessionActivityReadModel,
)
from backend.app.services.v3.session_service import (
    FLOW_CONTRACT_V3_OWNER,
    OwnedResourceNotFound,
    get_owned_session_row,
)


_OPERATION_PREFIX = "transition_v3_session"


class IdempotencyConflict(RuntimeError):
    pass


class InputRevisionConflict(RuntimeError):
    pass


class InvalidTransition(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class FlowContractMismatch(RuntimeError):
    pass


class AssessmentInputNotReady(RuntimeError):
    """Raised when a new-flow session lacks valid assessment inputs."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


_QUESTIONNAIRE_COMPLETE = 10
_QUESTIONNAIRE_QUESTION_IDS = frozenset(
    f"q{index:02d}" for index in range(1, _QUESTIONNAIRE_COMPLETE + 1)
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _request_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def build_activity_read_model(
    db: Session,
    session_row: SessionModel,
    *,
    input_mode: str | None,
    input_revision: int,
    active_document_id: str | None,
    active_understanding_id: str | None,
    active_understanding_revision: int | None,
    active_questionnaire_submission_id: str | None,
) -> SessionActivityReadModel:
    understanding_ref = None
    if active_understanding_id is not None and active_understanding_revision is not None:
        understanding_ref = UnderstandingRef(
            understanding_id=active_understanding_id,
            revision=active_understanding_revision,
        )
    questionnaire_ref = None
    if active_questionnaire_submission_id is not None:
        submission = (
            db.query(QuestionnaireSubmissionV3)
            .filter(
                QuestionnaireSubmissionV3.questionnaire_submission_id
                == active_questionnaire_submission_id
            )
            .one_or_none()
        )
        if submission is not None:
            questionnaire_ref = QuestionnaireRef(
                questionnaire_submission_id=submission.questionnaire_submission_id,
                schema_id=submission.schema_id,
                schema_version=submission.schema_version,
                manifest_version=submission.manifest_version,
                content_checksum=submission.content_checksum,
            )
    return SessionActivityReadModel(
        session_id=session_row.session_id,
        flow_contract_version=FLOW_CONTRACT_V3_OWNER,
        input_mode=input_mode,
        input_revision=input_revision,
        active_document_id=active_document_id,
        understanding_ref=understanding_ref,
        questionnaire_ref=questionnaire_ref,
    )


def _from_snapshot(
    db: Session,
    session_row: SessionModel,
    snapshot: SessionInputRevision,
) -> SessionActivityReadModel:
    return build_activity_read_model(
        db,
        session_row,
        input_mode=snapshot.input_mode,
        input_revision=snapshot.input_revision,
        active_document_id=snapshot.active_document_id,
        active_understanding_id=snapshot.active_understanding_id,
        active_understanding_revision=snapshot.active_understanding_revision,
        active_questionnaire_submission_id=snapshot.active_questionnaire_submission_id,
    )


def _from_live(db: Session, session_row: SessionModel) -> SessionActivityReadModel:
    return build_activity_read_model(
        db,
        session_row,
        input_mode=session_row.input_mode,
        input_revision=session_row.input_revision or 1,
        active_document_id=session_row.active_document_id,
        active_understanding_id=session_row.active_understanding_id,
        active_understanding_revision=session_row.active_understanding_revision,
        active_questionnaire_submission_id=session_row.active_questionnaire_submission_id,
    )


def get_session_activity(
    db: Session,
    principal: AuthPrincipal,
    session_id: str,
) -> SessionActivityReadModel:
    session_row = get_owned_session_row(db, principal, session_id)
    if session_row.flow_contract_version != FLOW_CONTRACT_V3_OWNER:
        raise FlowContractMismatch
    return _from_live(db, session_row)


def _validate_document(
    db: Session,
    principal: AuthPrincipal,
    session_row: SessionModel,
    document_id: str,
) -> None:
    document = (
        db.query(Document)
        .filter(
            Document.document_id == document_id,
            Document.user_id == principal.internal_user_pk,
            Document.session_id == session_row.session_id,
            Document.status != "deleted",
        )
        .one_or_none()
    )
    if document is None:
        raise InvalidTransition(
            "DOCUMENT_NOT_FOUND",
            "未找到可用的上传资料，请重新上传。",
        )
    if document.ocr_error_code or not (document.ocr_text or "").strip():
        raise InvalidTransition(
            "DOCUMENT_OCR_NOT_READY",
            "资料尚未成功识别，请重新上传或改用描述与问卷。",
        )


def _next_state(
    db: Session,
    principal: AuthPrincipal,
    session_row: SessionModel,
    request: InputTransitionRequest,
) -> tuple[str, str | None, str | None, int | None, str | None]:
    """Return (input_mode, active_document_id, active_understanding_id,
    active_understanding_revision, active_questionnaire_submission_id)."""
    if request.action == "select_mode":
        if session_row.input_mode is not None:
            raise InvalidTransition(
                "INPUT_MODE_ALREADY_SELECTED",
                "入口已选择，无法重复选择。",
            )
        return request.input_mode, None, None, None, None
    if request.action == "replace_document":
        _validate_document(db, principal, session_row, request.document_id)
        return "with_document", request.document_id, None, None, None
    # discard_document
    return "without_document", None, None, None, None


def apply_input_transition(
    db: Session,
    principal: AuthPrincipal,
    session_id: str,
    request: InputTransitionRequest,
    idempotency_key: str,
) -> tuple[SessionActivityReadModel, bool]:
    session_row = get_owned_session_row(db, principal, session_id)
    if session_row.flow_contract_version != FLOW_CONTRACT_V3_OWNER:
        raise FlowContractMismatch

    operation = f"{_OPERATION_PREFIX}:{session_id}"
    request_hash = _request_hash(request.model_dump(mode="json"))
    record = (
        db.query(V3IdempotencyRecord)
        .filter(
            V3IdempotencyRecord.internal_user_pk == principal.internal_user_pk,
            V3IdempotencyRecord.operation == operation,
            V3IdempotencyRecord.idempotency_key == idempotency_key,
        )
        .one_or_none()
    )
    if record is not None and _as_utc(record.expires_at) <= _utc_now():
        db.delete(record)
        db.flush()
        record = None
    if record is not None:
        if record.request_hash != request_hash:
            raise IdempotencyConflict
        if record.status == "succeeded" and record.resource_id:
            revision = _revision_from_record(record.resource_id)
            snapshot = (
                db.query(SessionInputRevision)
                .filter(
                    SessionInputRevision.session_row_id == session_row.id,
                    SessionInputRevision.input_revision == revision,
                )
                .one_or_none()
            )
            if snapshot is not None:
                return _from_snapshot(db, session_row, snapshot), True

    (
        input_mode,
        active_document_id,
        active_understanding_id,
        active_understanding_revision,
        active_questionnaire_submission_id,
    ) = _next_state(db, principal, session_row, request)

    if record is None:
        record = V3IdempotencyRecord(
            idempotency_record_id=f"idem_{uuid.uuid4().hex}",
            internal_user_pk=principal.internal_user_pk,
            operation=operation,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            status="processing",
            expires_at=_utc_now() + timedelta(hours=24),
        )
        db.add(record)

    # Discarding the document path must invalidate the active document set so
    # it can no longer be returned as active or block document deletion.
    if request.action == "discard_document" and session_row.active_document_set_id:
        set_row = (
            db.query(DocumentSet)
            .filter(
                DocumentSet.document_set_id == session_row.active_document_set_id,
                DocumentSet.status == "active",
            )
            .one_or_none()
        )
        if set_row is not None:
            set_row.status = "discarded"

    # Atomic compare-and-swap: bump input_revision and swap the active refs in
    # one UPDATE guarded by the expected revision (no read-then-write race).
    next_revision = _cas_apply_transition(
        db,
        session_row,
        request.expected_input_revision,
        input_mode=input_mode,
        active_document_id=active_document_id,
        active_document_set_id=(
            None if request.action == "discard_document" else session_row.active_document_set_id
        ),
        active_understanding_id=active_understanding_id,
        active_understanding_revision=active_understanding_revision,
        active_questionnaire_submission_id=active_questionnaire_submission_id,
    )
    db.add(
        SessionInputRevision(
            session_row_id=session_row.id,
            input_revision=next_revision,
            input_mode=input_mode,
            active_document_id=active_document_id,
            active_understanding_id=active_understanding_id,
            active_understanding_revision=active_understanding_revision,
            active_questionnaire_submission_id=active_questionnaire_submission_id,
            action=request.action,
        )
    )

    record.resource_type = "session_input_revision"
    record.resource_id = f"{session_id}:rev:{next_revision}"
    record.status = "succeeded"
    record.response_code = 201
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return _from_live(db, session_row), False


def _cas_apply_transition(
    db: Session,
    session_row: SessionModel,
    expected: int,
    *,
    input_mode: str | None,
    active_document_id: str | None,
    active_document_set_id: str | None,
    active_understanding_id: str | None,
    active_understanding_revision: int | None,
    active_questionnaire_submission_id: str | None,
) -> int:
    result = db.execute(
        update(SessionModel)
        .where(
            SessionModel.id == session_row.id,
            SessionModel.input_revision == expected,
        )
        .values(
            input_revision=expected + 1,
            input_mode=input_mode,
            active_document_id=active_document_id,
            active_document_set_id=active_document_set_id,
            active_understanding_id=active_understanding_id,
            active_understanding_revision=active_understanding_revision,
            active_questionnaire_submission_id=active_questionnaire_submission_id,
        )
        .execution_options(synchronize_session="fetch")
    )
    if result.rowcount != 1:
        raise InputRevisionConflict
    return expected + 1


def _approved_questionnaire_manifest() -> dict | None:
    """Read the canonical approved questionnaire manifest (PR #89 medical
    signoff) — the single source of truth for schema_id / schema_version /
    manifest_version / content_checksum. No local copy of any constant is
    maintained. Returns None only if the knowledge assets are absent from the
    deployment (which the caller treats as not-ready)."""
    from pathlib import Path

    manifest_path = (
        Path(__file__).resolve().parents[4]
        / "knowledge" / "v3" / "questionnaire-v3.0.json"
    )
    if not manifest_path.is_file():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def validate_assessment_input_readiness(
    db: Session,
    session_row: SessionModel,
) -> None:
    """Enforce the v3-owner-flow-1 input rules before creating an assessment.

    with_document → a confirmed, session-owned case summary must be active;
    without_document → a complete, session-owned, approved-schema 10-question
    submission must be active. Legacy sessions are not subject to these rules.
    This is the backend gate Agent 1 calls before consuming assessment inputs;
    it must not rely on the frontend hiding buttons.
    """
    if session_row.flow_contract_version != FLOW_CONTRACT_V3_OWNER:
        return
    if session_row.input_mode is None:
        raise AssessmentInputNotReady(
            "INPUT_MODE_NOT_SELECTED", "尚未选择输入方式。"
        )
    if session_row.input_mode == "with_document":
        if (
            session_row.active_understanding_id is None
            or session_row.active_understanding_revision is None
        ):
            raise AssessmentInputNotReady(
                "UNDERSTANDING_NOT_CONFIRMED", "资料摘要尚未确认。"
            )
        revision = (
            db.query(UnderstandingRevision)
            .filter(
                UnderstandingRevision.understanding_id
                == session_row.active_understanding_id,
                UnderstandingRevision.revision
                == session_row.active_understanding_revision,
            )
            .one_or_none()
        )
        if revision is None or revision.status != "confirmed":
            raise AssessmentInputNotReady(
                "UNDERSTANDING_NOT_CONFIRMED", "资料摘要尚未确认。"
            )
        run = (
            db.query(UnderstandingRun)
            .filter(
                UnderstandingRun.understanding_id
                == session_row.active_understanding_id,
                UnderstandingRun.session_row_id == session_row.id,
                UnderstandingRun.internal_user_pk == session_row.user_id,
            )
            .one_or_none()
        )
        if run is None:
            raise AssessmentInputNotReady(
                "UNDERSTANDING_NOT_OWNED", "资料摘要不属于当前会话。"
            )
        snapshot = (run.degradation_json or {}).get("input_snapshot") or {}
        if not snapshot:
            raise AssessmentInputNotReady(
                "DOCUMENT_SET_NOT_READY", "资料集版本尚未绑定。"
            )
        # The confirmation bind advances input_revision once. Any later
        # source transition must invalidate the old Understanding even if a
        # stale active-understanding pointer is restored.
        if session_row.input_revision not in {
            run.input_revision,
            (run.input_revision or 0) + 1,
        }:
            raise AssessmentInputNotReady(
                "DOCUMENT_SET_NOT_ACTIVE", "资料集已被替换或丢弃。"
            )
        from backend.app.services.v3.understanding_service import (
            InvalidChange as UnderstandingInvalidChange,
            _load_active_document_set,
        )

        try:
            active_set = _load_active_document_set(
                db, session_row.user_id, session_row
            )
        except UnderstandingInvalidChange as error:
            raise AssessmentInputNotReady(error.code, error.message) from None
        if (
            active_set.row.document_set_id != snapshot.get("document_set_id")
            or active_set.row.revision != snapshot.get("document_set_revision")
            or list(active_set.document_ids) != snapshot.get("document_ids")
            or active_set.relevance_fingerprint
            != snapshot.get("relevance_fingerprint")
        ):
            raise AssessmentInputNotReady(
                "DOCUMENT_SET_NOT_ACTIVE", "资料集版本已发生变化。"
            )
        valid_document_ids = {
            document_id
            for document_id, relevance in active_set.relevance_by_document.items()
            if relevance.outcome == "VALID"
        }
        normalized_facts = (revision.presentation_json or {}).get(
            "normalized_facts"
        ) or []
        for fact in normalized_facts:
            for source_ref in fact.get("source_refs") or []:
                if (
                    source_ref.get("source_type") == "document"
                    and source_ref.get("source_id") not in valid_document_ids
                ):
                    raise AssessmentInputNotReady(
                        "DOCUMENT_RELEVANCE_INVALID",
                        "评估输入包含不可用资料。",
                    )
        return
    submission_id = session_row.active_questionnaire_submission_id
    if submission_id is None:
        raise AssessmentInputNotReady(
            "QUESTIONNAIRE_REQUIRED", "请先完成10道状态问卷。"
        )
    submission = (
        db.query(QuestionnaireSubmissionV3)
        .filter(
            QuestionnaireSubmissionV3.questionnaire_submission_id == submission_id,
            QuestionnaireSubmissionV3.internal_user_pk == session_row.user_id,
            QuestionnaireSubmissionV3.session_row_id == session_row.id,
        )
        .one_or_none()
    )
    if submission is None:
        raise AssessmentInputNotReady(
            "QUESTIONNAIRE_NOT_OWNED", "问卷提交不属于当前会话。"
        )
    # A complete submission must answer exactly 10 unique canonical question
    # IDs (q01..q10); duplicates, missing or unknown/old-V2 questions are all
    # rejected (a longer array with a duplicated ID is not a valid submission).
    answers = submission.answers_json or []
    if len(answers) != _QUESTIONNAIRE_COMPLETE:
        raise AssessmentInputNotReady(
            "QUESTIONNAIRE_INCOMPLETE", "需要完整提交10道状态问卷。"
        )
    answer_ids = {
        item.get("question_id") for item in answers if isinstance(item, dict)
    }
    if answer_ids != _QUESTIONNAIRE_QUESTION_IDS:
        raise AssessmentInputNotReady(
            "QUESTIONNAIRE_INCOMPLETE", "需要完整提交10道状态问卷（唯一题号）。"
        )
    # Precise schema/version/manifest/checksum validation against the canonical
    # approved manifest (PR #89). Reject if the manifest is unavailable rather
    # than skip validation — a checksum is never hard-coded locally.
    manifest = _approved_questionnaire_manifest()
    if manifest is None:
        raise AssessmentInputNotReady(
            "QUESTIONNAIRE_MANIFEST_UNAVAILABLE", "问卷清单暂不可用。"
        )
    if submission.schema_id != manifest.get("schema_id"):
        raise AssessmentInputNotReady(
            "QUESTIONNAIRE_INVALID_SCHEMA", "问卷 schema 无效。"
        )
    if submission.schema_version != manifest.get("schema_version"):
        raise AssessmentInputNotReady(
            "QUESTIONNAIRE_INVALID_SCHEMA_VERSION", "问卷 schema 版本无效。"
        )
    if submission.manifest_version != manifest.get("manifest_version"):
        raise AssessmentInputNotReady(
            "QUESTIONNAIRE_INVALID_MANIFEST", "问卷 manifest 版本无效。"
        )
    if submission.content_checksum != manifest.get("content_checksum"):
        raise AssessmentInputNotReady(
            "QUESTIONNAIRE_INVALID_CHECKSUM", "问卷内容校验无效。"
        )


def _revision_from_record(resource_id: str) -> int | None:
    prefix = "rev:"
    if prefix not in resource_id:
        return None
    marker = resource_id.split(prefix, 1)[1]
    try:
        return int(marker)
    except ValueError:
        return None
